"""
Pi Music - Application Controller & Main UI Loop
Coordinates Pygame rendering, touchscreen input, background services,
and view lifecycle.
"""

import concurrent.futures
import os
import sys
import threading
from typing import Dict, Optional
import pygame

from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_SIZE, FPS_ACTIVE, FPS_IDLE,
    STATUS_BAR_HEIGHT, NAV_BAR_HEIGHT, CONTENT_Y, CONTENT_HEIGHT,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_LIGHT, COLOR_SURFACE_BORDER,
    COLOR_ACCENT, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    DEFAULT_VOLUME, init_directories
)
from pimusic.core.mpv_player import MPVPlayer
from pimusic.core.playlist import PlaylistManager
from pimusic.core.youtube import YouTubeService, Track
from pimusic.core.wifi import WifiManager
from pimusic.core.bluetooth import BluetoothManager
from pimusic.core.system_info import SystemInfo
from pimusic.utils.cache import ThumbnailCache
from pimusic.utils.logger import get_logger
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

    def __init__(self, fullscreen: bool = False):
        init_directories()

        # Initialize Pygame
        pygame.init()
        pygame.font.init()
        try:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
        except Exception:
            pass

        # Display Setup
        flags = pygame.DOUBLEBUF
        if fullscreen:
            flags |= pygame.FULLSCREEN

        self.screen = pygame.display.set_mode(SCREEN_SIZE, flags)
        pygame.display.set_caption("Pi Music")
        self.clock = pygame.time.Clock()
        self.is_running = True

        # Core Services
        self.cache = ThumbnailCache()
        self.playlist = PlaylistManager()
        self.youtube = YouTubeService()
        self.wifi = WifiManager()
        self.bluetooth = BluetoothManager()
        self.player = MPVPlayer()

        # Route audio according to saved preference (jack vs bluetooth)
        init_mode = self.bluetooth.audio_output_mode
        init_dev = self.bluetooth.get_connected_device()
        self.player.set_audio_output(init_mode, init_dev.mac if init_dev else None)

        # Hook MPV track end event to advance queue
        self.player.on_track_end = self._handle_track_finished

        # Async Thumbnail Executor
        self._thumb_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        # Components
        self.status_bar = StatusBar()

        # Bottom Navigation Bar (6 tabs across 480px width)
        self.active_tab = "player"
        self.nav_buttons: Dict[str, Button] = {}
        self._setup_navigation_bar()

        # Views
        self.views: Dict[str, BaseView] = {
            "player": PlayerView(self),
            "search": SearchView(self),
            "queue": QueueView(self),
            "wifi": WifiView(self),
            "bluetooth": BluetoothView(self),
            "settings": SettingsView(self)
        }

        # Idle timer for CPU throttling
        self.last_interaction_time = pygame.time.get_ticks() / 1000.0

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
        """Adjust volume on MPV and ALSA."""
        self.player.set_volume(val)
        SystemInfo.set_alsa_volume(val)

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

        while self.is_running:
            # 1. Process Input Events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.is_running = False
                    break

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

            # 3. Render Frame
            self.screen.fill(COLOR_BG)

            # Render active view content
            self.views[self.active_tab].draw(self.screen)

            # Render top Status Bar
            self.status_bar.draw(self.screen)

            # Render bottom Navigation Bar
            nav_y = SCREEN_HEIGHT - NAV_BAR_HEIGHT
            pygame.draw.line(self.screen, COLOR_SURFACE_BORDER, (0, nav_y), (SCREEN_WIDTH, nav_y), 1)
            for tab_id, btn in self.nav_buttons.items():
                btn.is_active = (tab_id == self.active_tab)
                btn.draw(self.screen)

            pygame.display.flip()

            # 4. CPU-aware Framerate Throttling for Pi 3
            now = pygame.time.get_ticks() / 1000.0
            is_active = (now - self.last_interaction_time) < 4.0 or self.player.is_playing
            target_fps = FPS_ACTIVE if is_active else FPS_IDLE
            self.clock.tick(target_fps)

        self.shutdown()

    def shutdown(self):
        """Clean up all services and shutdown."""
        logger.info("Shutting down Pi Music...")
        self.playlist.save_queue()
        self.player.shutdown()
        self.youtube.shutdown()
        self._thumb_executor.shutdown(wait=False)
        pygame.quit()
