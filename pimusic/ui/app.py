"""
Pi Music - Application Controller & Main UI Loop
Coordinates Pygame rendering, touchscreen input, background services,
and view lifecycle.
"""

import concurrent.futures
import os
import sys
import threading
import time
from typing import Dict, Optional
import pygame

from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_SIZE, FPS_ACTIVE, FPS_IDLE,
    STATUS_BAR_HEIGHT, NAV_BAR_HEIGHT, CONTENT_Y, CONTENT_HEIGHT,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_LIGHT, COLOR_SURFACE_BORDER,
    COLOR_ACCENT, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    DEFAULT_VOLUME, WEB_HOST, WEB_PORT, init_directories
)
from pimusic.core.mpv_player import MPVPlayer
from pimusic.core.playlist import PlaylistManager
from pimusic.core.youtube import YouTubeService, Track
from pimusic.core.wifi import WifiManager
from pimusic.core.bluetooth import BluetoothManager
from pimusic.core.system_info import SystemInfo
from pimusic.utils.cache import ThumbnailCache
from pimusic.utils.logger import get_logger
from pimusic.web.server import WebServer
from pimusic.ui.theme import Theme
from pimusic.ui.components.button import Button
from pimusic.ui.components.status_bar import StatusBar
from pimusic.ui.views.base_view import BaseView
from pimusic.ui.views.player_view import PlayerView
from pimusic.ui.views.search_view import SearchView
from pimusic.ui.views.queue_view import QueueView
from pimusic.ui.views.wifi_view import WifiView
from pimusic.ui.views.bluetooth_view import BluetoothView
from pimusic.ui.views.settings_view import SettingsView

logger = get_logger("App")

class App:
    """The central application coordinator."""

    def __init__(
        self,
        fullscreen: bool = False,
        headless: bool = False,
        enable_web: bool = True,
        web_port: int = WEB_PORT,
        alsa_device: str = "alsa/default",
    ):
        init_directories()

        self.is_running = True
        self.headless = headless
        self._pygame_initialized = False
        self._shutdown_done = False

        # Core Services (initialized identically for both HDMI GUI and Headless Web mode)
        self.cache = ThumbnailCache()
        self.playlist = PlaylistManager()
        self.youtube = YouTubeService()
        self.wifi = WifiManager()
        self.bluetooth = BluetoothManager()
        self.player = MPVPlayer(alsa_device=alsa_device)

        # Route audio according to saved preference (jack vs bluetooth)
        init_mode = self.bluetooth.audio_output_mode
        init_dev = self.bluetooth.get_connected_device()
        self.player.set_audio_output(init_mode, init_dev.mac if init_dev else None)

        # Hook MPV track end event to advance queue
        self.player.on_track_end = self._handle_track_finished

        # Async Thumbnail Executor
        self._thumb_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        # Lightweight Web Remote Server (always available when enabled, with or without HDMI)
        self.web_server: Optional[WebServer] = None
        if enable_web:
            self.web_server = WebServer(self, host=WEB_HOST, port=web_port)
            self.web_server.start()

        # Display & GUI components (skipped in headless mode or if no display is available)
        self.screen = None
        self.canvas = None
        self.clock = None
        self.real_w, self.real_h = SCREEN_SIZE
        self.status_bar = None
        self.active_tab = "player"
        self.nav_buttons: Dict[str, Button] = {}
        self.views: Dict[str, BaseView] = {}
        self.last_interaction_time = time.time()

        if not self.headless:
            self._init_gui(fullscreen=fullscreen)
        else:
            logger.info("Running in Headless Mode (no HDMI/GUI). Control via Web Remote.")

    def _init_gui(self, fullscreen: bool = False):
        """Initialize Pygame display and views; fall back cleanly to headless if unavailable."""
        try:
            # Prevent Pygame from touching ALSA (MPV handles all audio playback)
            os.environ["SDL_AUDIODRIVER"] = "dummy"

            # Initialize Pygame subsystems (Display and Font only)
            pygame.display.init()
            pygame.font.init()
            try:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
            except Exception:
                pass

            # Claim full physical resolution (0, 0) in minimal Xorg without a window manager
            # so the window fills 100% of the HDMI display instead of floating as a 480x320 box.
            flags = pygame.DOUBLEBUF
            if fullscreen:
                flags |= pygame.FULLSCREEN
            mode_size = (0, 0) if fullscreen else SCREEN_SIZE
            self.screen = pygame.display.set_mode(mode_size, flags)
            self.real_w, self.real_h = self.screen.get_size()
            pygame.display.set_caption("Pi Music")
            logger.info(f"Display mode initialized: physical={self.real_w}x{self.real_h}, virtual=480x320")

            # Virtual Canvas for responsive scaling across any HDMI TV / Monitor
            self.canvas = pygame.Surface(SCREEN_SIZE)
            self.clock = pygame.time.Clock()
            self._pygame_initialized = True

            # Components
            self.status_bar = StatusBar()
            self._setup_navigation_bar()

            # Views
            self.views = {
                "player": PlayerView(self),
                "search": SearchView(self),
                "queue": QueueView(self),
                "wifi": WifiView(self),
                "bluetooth": BluetoothView(self),
                "settings": SettingsView(self)
            }
            self.last_interaction_time = pygame.time.get_ticks() / 1000.0
        except Exception as e:
            logger.warning(f"Display unavailable ({e}). Falling back to Headless Web Mode.")
            self.headless = True
            self._pygame_initialized = False
            try:
                pygame.quit()
            except Exception:
                pass

    def _setup_navigation_bar(self):
        """Construct the 6 bottom navigation buttons."""
        nav_y = SCREEN_HEIGHT - NAV_BAR_HEIGHT
        tab_defs = [
            ("player", "Player", "music"),
            ("search", "Search", "search"),
            ("queue", "Queue", "queue"),
            ("wifi", "Wi-Fi", "wifi"),
            ("bluetooth", "Bluetooth", "bluetooth"),
            ("settings", "Settings", "settings"),
        ]

        btn_w = SCREEN_WIDTH // len(tab_defs)  # 80px per tab
        for i, (tab_id, label, icon) in enumerate(tab_defs):
            rect = pygame.Rect(i * btn_w, nav_y, btn_w, NAV_BAR_HEIGHT)
            self.nav_buttons[tab_id] = Button(
                rect,
                icon=icon,
                icon_size=18,
                radius=0,
                bg_color=COLOR_SURFACE,
                hover_color=COLOR_SURFACE_LIGHT,
                border_color=None,
                callback=lambda tid=tab_id: self.switch_tab(tid)
            )

    def switch_tab(self, tab_id: str):
        """Switch active view and trigger lifecycle hooks."""
        if tab_id in self.views and tab_id != self.active_tab:
            self.views[self.active_tab].on_leave()
            self.active_tab = tab_id
            self.views[self.active_tab].on_enter()
            self.last_interaction_time = pygame.time.get_ticks() / 1000.0

    def play_track_now(self, track: Track):
        """Immediately resolve and play the track."""
        self.playlist.play_now(track)
        self._resolve_and_stream(track)

    def play_index(self, index: int) -> Optional[Track]:
        """Jump to a specific queue index and start playing it."""
        track = self.playlist.jump_to(index)
        if track:
            self._resolve_and_stream(track)
        return track

    def set_audio_output_mode(self, mode: str, bluetooth_mac: Optional[str] = None):
        """Switch audio output between 'jack', 'hdmi', and 'bluetooth' and update MPV."""
        if mode not in ("jack", "hdmi", "bluetooth"):
            mode = "jack"
        self.bluetooth.save_audio_output_pref(mode)
        if mode == "bluetooth":
            mac = bluetooth_mac
            if not mac:
                dev = self.bluetooth.get_connected_device()
                mac = dev.mac if dev else None
            self.player.set_audio_output("bluetooth", mac)
        elif mode == "hdmi":
            self.player.set_audio_output("hdmi", None)
        else:
            self.player.set_audio_output("jack", None)

    def play_next(self):
        """Advance to next track in queue."""
        track = self.playlist.next_track()
        if track:
            self._resolve_and_stream(track)
        else:
            self.player.stop()

    def play_previous(self):
        """Return to previous track in queue."""
        track = self.playlist.previous_track()
        if track:
            self._resolve_and_stream(track)
        else:
            self.player.stop()

    def toggle_play_pause(self):
        """Toggle playback state."""
        if not self.player.is_playing:
            track = self.playlist.current_track
            if track:
                self._resolve_and_stream(track)
        else:
            self.player.toggle_pause()

    def stop(self):
        """Stop playback completely."""
        self.player.stop()

    def set_volume(self, val: int):
        """Adjust playback volume via MPV (keeps ALSA PCM at clean 0dB line-level)."""
        self.player.set_volume(val)

    def _resolve_and_stream(self, track: Track):
        """Asynchronously resolve direct audio stream and send to MPV."""
        def _on_resolved(t: Track, stream_url: Optional[str]):
            if stream_url:
                self.player.play_url(stream_url)
            else:
                logger.error(f"Cannot play track: {t.title}")

        self.youtube.resolve_audio_stream_async(track, _on_resolved)

    def _handle_track_finished(self):
        """Called when MPV reports EOF or track end."""
        logger.info("Track finished. Advancing to next track in queue...")
        self.play_next()

    def load_thumbnail_async(self, url: str, size: tuple[int, int]):
        """Download thumbnail in background and inject into cache."""
        if not url:
            return

        def _worker():
            self.cache.download_and_cache(url, size)

        self._thumb_executor.submit(_worker)

    def run(self):
        """Main application execution loop."""
        logger.info("Pi Music started successfully.")

        if self.headless:
            while self.is_running:
                time.sleep(0.5)
            self.shutdown()
            return

        while self.is_running:
            # 1. Process Input Events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    # Do not terminate when HDMI cable is disconnected; continue audio playback
                    logger.info("Window/Display disconnect event received. Playback continues uninterrupted.")
                    continue

                # Scale mouse/touch coordinates if running on a scaled HDMI screen
                if self.real_w != SCREEN_WIDTH or self.real_h != SCREEN_HEIGHT:
                    if hasattr(event, "pos"):
                        orig_x, orig_y = event.pos
                        scaled_pos = (
                            int(orig_x * SCREEN_WIDTH / self.real_w),
                            int(orig_y * SCREEN_HEIGHT / self.real_h)
                        )
                        event.__dict__["pos"] = scaled_pos

                self.last_interaction_time = pygame.time.get_ticks() / 1000.0

                # Delegate event to active view
                handled = self.views[self.active_tab].handle_event(event)
                if handled:
                    continue

                # Delegate to Bottom Navigation Tabs
                for tab_id, btn in self.nav_buttons.items():
                    if btn.handle_event(event):
                        break

            # 2. Update Application State
            current_track = self.playlist.current_track
            title = current_track.title if current_track else ""
            self.status_bar.update(
                wifi_connected=self.wifi.is_connected(),
                is_playing=self.player.is_playing and not self.player.is_paused,
                current_title=title,
                portal_detected=self.wifi.last_status.get("portal_detected", False),
                bt_connected=self.bluetooth.is_connected()
            )

            # Update queue badge count
            self.nav_buttons["queue"].badge_count = len(self.playlist.queue)

            # Update active view
            self.views[self.active_tab].update()

            # 3. Render Frame to Virtual Canvas
            self.canvas.fill(COLOR_BG)

            # Render active view content
            self.views[self.active_tab].draw(self.canvas)

            # Render top Status Bar
            self.status_bar.draw(self.canvas)

            # Render bottom Navigation Bar
            nav_y = SCREEN_HEIGHT - NAV_BAR_HEIGHT
            pygame.draw.line(self.canvas, COLOR_SURFACE_BORDER, (0, nav_y), (SCREEN_WIDTH, nav_y), 1)
            for tab_id, btn in self.nav_buttons.items():
                btn.is_active = (tab_id == self.active_tab)
                btn.draw(self.canvas)

            # Blit virtual canvas to physical HDMI screen with scaling
            if self.real_w == SCREEN_WIDTH and self.real_h == SCREEN_HEIGHT:
                self.screen.blit(self.canvas, (0, 0))
            else:
                scaled_surface = pygame.transform.scale(self.canvas, (self.real_w, self.real_h))
                self.screen.blit(scaled_surface, (0, 0))

            try:
                pygame.display.flip()
            except Exception:
                # Catch display surface loss during HDMI hotplug
                time.sleep(0.1)

            # 4. CPU-aware Framerate Throttling for Pi 3
            now = pygame.time.get_ticks() / 1000.0
            is_active = (now - self.last_interaction_time) < 4.0 or self.player.is_playing
            target_fps = FPS_ACTIVE if is_active else FPS_IDLE
            self.clock.tick(target_fps)

        self.shutdown()

    def shutdown(self):
        """Clean up all services and shutdown."""
        if self._shutdown_done:
            return
        self._shutdown_done = True
        logger.info("Shutting down Pi Music...")
        if self.web_server:
            self.web_server.stop()
        self.playlist.save_queue()
        self.player.shutdown()
        self.youtube.shutdown()
        self._thumb_executor.shutdown(wait=False)
        if self._pygame_initialized:
            pygame.quit()
