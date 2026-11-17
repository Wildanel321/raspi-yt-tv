"""
Pi Music - Now Playing View
Displays album art, track information, seek bar, transport controls,
and volume slider.
"""

from typing import TYPE_CHECKING, Optional
import pygame

from config import (
    CONTENT_Y, CONTENT_HEIGHT, SCREEN_WIDTH, COLOR_SURFACE,
    COLOR_SURFACE_LIGHT, COLOR_SURFACE_BORDER, COLOR_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_WARNING, THUMBNAIL_SIZE_LARGE
)
from pimusic.core.youtube import Track
from pimusic.ui.theme import Theme
from pimusic.ui.components.button import Button
from pimusic.ui.components.slider import Slider
from pimusic.ui.views.base_view import BaseView

if TYPE_CHECKING:
    from pimusic.ui.app import App

class PlayerView(BaseView):
    """The primary playback screen with transport controls and track metadata."""

    def __init__(self, app: "App"):
        super().__init__(app)

        # Thumbnail cache reference
        self.cached_thumbnail: Optional[pygame.Surface] = None
        self.cached_thumb_url: str = ""

        # Title scrolling animation
        self.marquee_offset = 0.0
        self.marquee_pause = 0.0

        # UI Controls
        # 1. Transport Buttons
        btn_y = CONTENT_Y + 116
        self.btn_prev = Button(pygame.Rect(144, btn_y, 48, 42), icon="prev", icon_size=20,
                               callback=self._on_prev)
        self.btn_play = Button(pygame.Rect(200, btn_y, 64, 42), icon="play", icon_size=24,
                               bg_color=COLOR_ACCENT, hover_color=(255, 60, 60),
                               callback=self._on_toggle_play)
        self.btn_next = Button(pygame.Rect(272, btn_y, 48, 42), icon="next", icon_size=20,
                               callback=self._on_next)
        self.btn_stop = Button(pygame.Rect(328, btn_y, 44, 42), icon="stop", icon_size=18,
                               callback=self._on_stop)
        self.btn_queue = Button(pygame.Rect(380, btn_y, 44, 42), icon="queue", icon_size=18,
                                callback=self._on_open_queue)

        # 2. Seek Bar Slider
        self.seek_slider = Slider(
            pygame.Rect(144, CONTENT_Y + 68, 320, 20),
            min_val=0.0,
            max_val=100.0,
            initial_val=0.0,
            callback=self._on_seek
        )

        # 3. Repeat & Shuffle Buttons (under album art)
        self.btn_repeat = Button(
            pygame.Rect(10, CONTENT_Y + 148, 56, 32),
            text="Loop",
            font_size=11,
            is_toggle=True,
            callback=self._on_toggle_repeat
        )
        self.btn_shuffle = Button(
            pygame.Rect(72, CONTENT_Y + 148, 58, 32),
            text="Shuff",
            font_size=11,
            is_toggle=True,
            callback=self._on_toggle_shuffle
        )

        # 4. Volume Controls
        vol_y = CONTENT_Y + 180
        self.volume_slider = Slider(
            pygame.Rect(180, vol_y, 220, 20),
            min_val=0.0,
            max_val=100.0,
            initial_val=float(self.app.player.volume),
            callback=self._on_volume_change
        )

    def _on_prev(self):
        self.app.play_previous()

    def _on_next(self):
        self.app.play_next()

    def _on_toggle_play(self):
        self.app.toggle_play_pause()

    def _on_stop(self):
        self.app.stop()

    def _on_open_queue(self):
        self.app.switch_tab("queue")

    def _on_seek(self, target_pct: float):
        track = self.app.playlist.current_track
        if track and track.duration > 0:
            target_sec = (target_pct / 100.0) * track.duration
            self.app.player.seek(target_sec)

    def _on_toggle_repeat(self):
        modes = ["off", "all", "one"]
        cur_idx = modes.index(self.app.playlist.repeat_mode)
        next_mode = modes[(cur_idx + 1) % len(modes)]
        self.app.playlist.repeat_mode = next_mode
        self.btn_repeat.text = "1-Loop" if next_mode == "one" else ("Loop" if next_mode == "all" else "Off")
        self.btn_repeat.is_active = (next_mode != "off")

    def _on_toggle_shuffle(self):
        self.app.playlist.shuffle = not self.app.playlist.shuffle
        self.btn_shuffle.is_active = self.app.playlist.shuffle

    def _on_volume_change(self, val: float):
        self.app.set_volume(int(val))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.btn_prev.handle_event(event):
            return True
        if self.btn_play.handle_event(event):
            return True
        if self.btn_next.handle_event(event):
            return True
        if self.btn_stop.handle_event(event):
            return True
        if self.btn_queue.handle_event(event):
            return True
        if self.btn_repeat.handle_event(event):
            return True
        if self.btn_shuffle.handle_event(event):
            return True
        if self.seek_slider.handle_event(event):
            return True
        if self.volume_slider.handle_event(event):
            return True
        return False

    def update(self):
        """Update playback slider and buttons."""
        track = self.app.playlist.current_track
        player = self.app.player

        # Update Play/Pause button icon
        self.btn_play.icon = "pause" if (player.is_playing and not player.is_paused) else "play"

        # Update Seek slider position
        if not self.seek_slider.is_dragging:
            total_dur = track.duration if (track and track.duration > 0) else player.duration
            if total_dur > 0:
                pct = (player.current_time / total_dur) * 100.0
                self.seek_slider.set_value(pct)
            else:
                self.seek_slider.set_value(0.0)

        # Update queue badge count
        self.btn_queue.badge_count = len(self.app.playlist.queue)

        # Update thumbnail cache
        if track and track.thumbnail_url != self.cached_thumb_url:
            self.cached_thumb_url = track.thumbnail_url
            self.cached_thumbnail = self.app.cache.get(track.thumbnail_url, THUMBNAIL_SIZE_LARGE)
            if not self.cached_thumbnail:
                # Trigger async download
                self.app.load_thumbnail_async(track.thumbnail_url, THUMBNAIL_SIZE_LARGE)

    def draw(self, surface: pygame.Surface):
        track = self.app.playlist.current_track

        # 1. Album Artwork / Thumbnail Box (120x120)
        art_rect = pygame.Rect(10, CONTENT_Y + 12, 120, 120)
        Theme.draw_rounded_rect(
            surface,
            art_rect,
            COLOR_SURFACE,
            radius=8,
            border_color=COLOR_SURFACE_BORDER,
            border_width=1
        )

        if self.cached_thumbnail:
            surface.blit(self.cached_thumbnail, (art_rect.x, art_rect.y))
        else:
            # Fallback musical note icon
            Theme.draw_icon(surface, "music", art_rect.centerx, art_rect.centery, size=48, color=COLOR_SURFACE_LIGHT)

        # 2. Track Title & Artist
        title_font = Theme.get_font(16, bold=True)
        artist_font = Theme.get_font(13)

        title_text = track.title if track else "No Track Selected"
        artist_text = track.artist if track else "Use Search to find songs"

        # Render Title with clipping
        title_surf = title_font.render(title_text, True, COLOR_TEXT_PRIMARY)
        available_w = 320
        if title_surf.get_width() > available_w:
            # Marquee scroll animation
            self.marquee_offset = (self.marquee_offset + 0.5) % (title_surf.get_width() + 40)
            area_rect = pygame.Rect(int(self.marquee_offset), 0, available_w, title_surf.get_height())
            surface.blit(title_surf, (144, CONTENT_Y + 14), area=area_rect)
        else:
            surface.blit(title_surf, (144, CONTENT_Y + 14))

        artist_surf = artist_font.render(artist_text, True, COLOR_TEXT_SECONDARY)
        surface.blit(artist_surf, (144, CONTENT_Y + 36))

        # 3. Elapsed Time / Total Time
        player = self.app.player
        cur_sec = int(player.current_time)
        tot_sec = track.duration if (track and track.duration > 0) else int(player.duration)

        cur_str = f"{cur_sec // 60:02d}:{cur_sec % 60:02d}"
        tot_str = f"{tot_sec // 60:02d}:{tot_sec % 60:02d}" if tot_sec > 0 else "--:--"
        time_display = f"{cur_str} / {tot_str}"

        time_font = Theme.get_font(11)
        time_surf = time_font.render(time_display, True, COLOR_TEXT_MUTED)
        surface.blit(time_surf, (144, CONTENT_Y + 92))

        # Buffering / Loading Indicator
        if player.is_buffering:
            buf_surf = Theme.get_font(11, bold=True).render("[Buffering...]", True, COLOR_WARNING)
            surface.blit(buf_surf, (360, CONTENT_Y + 92))

        # 4. Draw Seek Slider
        self.seek_slider.draw(surface)

        # 5. Draw Transport Buttons
        self.btn_prev.draw(surface)
        self.btn_play.draw(surface)
        self.btn_next.draw(surface)
        self.btn_stop.draw(surface)
        self.btn_queue.draw(surface)

        # 6. Draw Repeat & Shuffle
        self.btn_repeat.draw(surface)
        self.btn_shuffle.draw(surface)

        # 7. Volume Row
        Theme.draw_icon(surface, "volume", 156, CONTENT_Y + 190, size=18, color=COLOR_TEXT_SECONDARY)
        self.volume_slider.draw(surface)
        vol_text = f"{int(self.volume_slider.value)}%"
        vol_surf = Theme.get_font(11).render(vol_text, True, COLOR_TEXT_SECONDARY)
        surface.blit(vol_surf, (412, CONTENT_Y + 184))
