"""
Pi Music - Queue View
Displays active playlist/queue, current playing item, removal and clear controls.
"""

from typing import TYPE_CHECKING
import pygame

from config import (
    CONTENT_Y, CONTENT_HEIGHT, SCREEN_WIDTH, COLOR_SURFACE,
    COLOR_SURFACE_LIGHT, COLOR_SURFACE_BORDER, COLOR_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_DANGER, THUMBNAIL_SIZE_SMALL
)
from pimusic.core.youtube import Track
from pimusic.ui.theme import Theme
from pimusic.ui.components.button import Button
from pimusic.ui.components.list_view import ListView
from pimusic.ui.views.base_view import BaseView

if TYPE_CHECKING:
    from pimusic.ui.app import App

class QueueView(BaseView):
    """Manages viewing and modifying the playback queue."""

    def __init__(self, app: "App"):
        super().__init__(app)

        # Header controls
        self.btn_clear = Button(
            pygame.Rect(SCREEN_WIDTH - 110, CONTENT_Y + 6, 100, 32),
            text="Clear All",
            font_size=12,
            icon="trash",
            icon_size=14,
            bg_color=COLOR_SURFACE_LIGHT,
            callback=self._on_clear_queue
        )

        # Queue List View
        list_y = CONTENT_Y + 44
        list_h = CONTENT_HEIGHT - 48
        self.list_view = ListView(
            pygame.Rect(10, list_y, SCREEN_WIDTH - 20, list_h),
            item_height=50,
            on_item_click=self._on_item_clicked
        )

    def on_enter(self):
        """Refresh queue list whenever entering this view."""
        self._sync_queue()

    def _sync_queue(self):
        self.list_view.set_items(list(self.app.playlist.queue))
        self.list_view.selected_index = self.app.playlist.current_index

    def _on_clear_queue(self):
        self.app.playlist.clear()
        self.app.player.stop()
        self._sync_queue()

    def _on_item_clicked(self, index: int, track: Track):
        """Jump to tapped track and start playback."""
        self.app.playlist.jump_to(index)
        self.app.play_track_now(track)
        self._sync_queue()

    def handle_event(self, event: pygame.event.Event) -> bool:
        # Check remove button clicks inside individual row bounds
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Check if clicked on a trash icon in the list
            list_rect = self.list_view.rect
            if list_rect.collidepoint(event.pos):
                relative_y = event.pos[1] - list_rect.top + self.list_view.scroll_y
                clicked_idx = int(relative_y // self.list_view.item_height)
                # If clicked on right 40px (where trash icon sits)
                if 0 <= clicked_idx < len(self.app.playlist.queue):
                    if event.pos[0] >= list_rect.right - 44:
                        self.app.playlist.remove_at(clicked_idx)
                        self._sync_queue()
                        return True

        if self.btn_clear.handle_event(event):
            return True

        if self.list_view.handle_event(event):
            return True

        return False

    def update(self):
        # Keep selected index in sync with active playing track
        if self.list_view.selected_index != self.app.playlist.current_index:
            self.list_view.selected_index = self.app.playlist.current_index

    def draw(self, surface: pygame.Surface):
        # Header: Queue Title & Item Count
        queue_len = len(self.app.playlist.queue)
        title_font = Theme.get_font(15, bold=True)
        title_surf = title_font.render(f"Up Next ({queue_len})", True, COLOR_TEXT_PRIMARY)
        surface.blit(title_surf, (14, CONTENT_Y + 12))

        # Clear All Button
        if queue_len > 0:
            self.btn_clear.draw(surface)

        # Queue List or Empty State
        if queue_len == 0:
            empty_font = Theme.get_font(14, bold=True)
            empty_surf = empty_font.render("Queue is Empty", True, COLOR_TEXT_SECONDARY)
            hint_surf = Theme.get_font(12).render("Search and tap songs to add them here", True, COLOR_TEXT_MUTED)
            surface.blit(empty_surf, (SCREEN_WIDTH // 2 - empty_surf.get_width() // 2, CONTENT_Y + 100))
            surface.blit(hint_surf, (SCREEN_WIDTH // 2 - hint_surf.get_width() // 2, CONTENT_Y + 126))
        else:
            self.list_view.draw(surface, self._draw_queue_item)

    def _draw_queue_item(self, surface: pygame.Surface, rect: pygame.Rect, index: int, track: Track, is_selected: bool):
        is_current = (index == self.app.playlist.current_index)

        # Background card
        bg = (40, 20, 20) if is_current else (COLOR_SURFACE_LIGHT if is_selected else COLOR_SURFACE)
        border_col = COLOR_ACCENT if is_current else None
        Theme.draw_rounded_rect(surface, rect.inflate(-2, -4), bg, radius=6,
                                border_color=border_col, border_width=1 if border_col else 0)

        # Track number / Play badge
        tx = rect.left + 12
        if is_current:
            Theme.draw_icon(surface, "play", tx + 6, rect.centery, size=14, color=COLOR_ACCENT)
        else:
            num_font = Theme.get_font(12, bold=True)
            num_surf = num_font.render(f"{index + 1}", True, COLOR_TEXT_MUTED)
            surface.blit(num_surf, (tx, rect.centery - num_surf.get_height() // 2))

        # Thumbnail (40x40)
        thumb_rect = pygame.Rect(tx + 22, rect.top + 5, 40, 40)
        thumb = self.app.cache.get(track.thumbnail_url, THUMBNAIL_SIZE_SMALL)
        if thumb:
            surface.blit(thumb, (thumb_rect.x, thumb_rect.y))
        else:
            pygame.draw.rect(surface, COLOR_SURFACE_LIGHT, thumb_rect, border_radius=4)
            Theme.draw_icon(surface, "music", thumb_rect.centerx, thumb_rect.centery, size=16, color=COLOR_TEXT_MUTED)
            self.app.load_thumbnail_async(track.thumbnail_url, THUMBNAIL_SIZE_SMALL)

        # Title & Artist
        meta_x = thumb_rect.right + 10
        title_font = Theme.get_font(13, bold=is_current)
        title_col = COLOR_ACCENT if is_current else COLOR_TEXT_PRIMARY
        title_surf = title_font.render(track.title, True, title_col)

        max_w = rect.width - 150
        if title_surf.get_width() > max_w:
            surface.blit(title_surf, (meta_x, rect.top + 7), area=pygame.Rect(0, 0, max_w, title_surf.get_height()))
        else:
            surface.blit(title_surf, (meta_x, rect.top + 7))

        artist_surf = Theme.get_font(11).render(f"{track.artist}  •  {track.duration_str}", True, COLOR_TEXT_SECONDARY)
        surface.blit(artist_surf, (meta_x, rect.top + 26))

        # Remove (Trash) Icon
        Theme.draw_icon(surface, "trash", rect.right - 24, rect.centery, size=16, color=COLOR_TEXT_MUTED)
