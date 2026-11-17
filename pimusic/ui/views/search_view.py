"""
Pi Music - YouTube Search View
Allows searching songs via virtual touchscreen keyboard and lists results.
"""

from typing import TYPE_CHECKING, List, Optional
import pygame

from config import (
    CONTENT_Y, CONTENT_HEIGHT, SCREEN_WIDTH, COLOR_SURFACE,
    COLOR_SURFACE_LIGHT, COLOR_SURFACE_BORDER, COLOR_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_SUCCESS, THUMBNAIL_SIZE_SMALL
)
from pimusic.core.youtube import Track
from pimusic.ui.theme import Theme
from pimusic.ui.components.button import Button
from pimusic.ui.components.list_view import ListView
from pimusic.ui.components.keyboard import VirtualKeyboard
from pimusic.ui.views.base_view import BaseView

if TYPE_CHECKING:
    from pimusic.ui.app import App

class SearchView(BaseView):
    """Search YouTube music and browse results with touch-friendly controls."""

    def __init__(self, app: "App"):
        super().__init__(app)

        self.query = ""
        self.results: List[Track] = []
        self.is_searching = False
        self.error_message = ""
        self.keyboard: Optional[VirtualKeyboard] = None

        # Search bar header button (tapping opens virtual keyboard)
        self.search_bar_rect = pygame.Rect(10, CONTENT_Y + 6, SCREEN_WIDTH - 20, 36)
        self.btn_search_trigger = Button(
            self.search_bar_rect,
            text="",
            icon="search",
            icon_size=18,
            callback=self._open_keyboard
        )

        # Quick action popup / confirmation
        self.active_track_popup: Optional[Track] = None

        # Results List View (item height 50px)
        list_y = CONTENT_Y + 48
        list_h = CONTENT_HEIGHT - 52
        self.list_view = ListView(
            pygame.Rect(10, list_y, SCREEN_WIDTH - 20, list_h),
            item_height=52,
            on_item_click=self._on_item_clicked
        )

    def _open_keyboard(self):
        """Open on-screen virtual keyboard."""
        self.keyboard = VirtualKeyboard(
            title="Search YouTube Music",
            initial_text=self.query,
            on_submit=self._on_search_submit,
            on_cancel=self._on_keyboard_cancel
        )

    def _on_keyboard_cancel(self):
        self.keyboard = None

    def _on_search_submit(self, text: str):
        self.keyboard = None
        text = text.strip()
        if text:
            self.query = text
            self._execute_search()

    def _execute_search(self):
        """Triggers asynchronous search via YouTubeService."""
        self.is_searching = True
        self.error_message = ""
        self.results.clear()
        self.list_view.set_items([])

        def _on_results(tracks: List[Track]):
            self.is_searching = False
            self.results = tracks
            self.list_view.set_items(tracks)
            if not tracks:
                self.error_message = "No tracks found. Try different keywords."

        def _on_error(err: str):
            self.is_searching = False
            self.error_message = f"Search failed: {err}"

        self.app.youtube.search_async(self.query, _on_results, _on_error)

    def _on_item_clicked(self, index: int, track: Track):
        """When an item is clicked, show Play / Add to Queue action buttons."""
        self.active_track_popup = track

    def handle_event(self, event: pygame.event.Event) -> bool:
        # 1. Virtual keyboard takes highest priority if open
        if self.keyboard and self.keyboard.is_active:
            return self.keyboard.handle_event(event)

        # 2. Track action popup (Play Now vs Add to Queue)
        if self.active_track_popup:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Popup bounds
                popup_rect = pygame.Rect(60, CONTENT_Y + 50, 360, 140)
                btn_play_rect = pygame.Rect(80, CONTENT_Y + 125, 140, 42)
                btn_queue_rect = pygame.Rect(240, CONTENT_Y + 125, 160, 42)
                btn_close_rect = pygame.Rect(popup_rect.right - 36, popup_rect.top + 8, 28, 28)

                if btn_play_rect.collidepoint(event.pos):
                    track = self.active_track_popup
                    self.active_track_popup = None
                    self.app.play_track_now(track)
                    self.app.switch_tab("player")
                    return True
                elif btn_queue_rect.collidepoint(event.pos):
                    track = self.active_track_popup
                    self.active_track_popup = None
                    self.app.playlist.add_track(track)
                    return True
                elif btn_close_rect.collidepoint(event.pos) or not popup_rect.collidepoint(event.pos):
                    self.active_track_popup = None
                    return True
            return True

        # 3. Search Bar Button
        if self.btn_search_trigger.handle_event(event):
            return True

        # 4. Results List View
        if self.list_view.handle_event(event):
            return True

        return False

    def update(self):
        pass

    def draw(self, surface: pygame.Surface):
        # 1. Search Bar
        Theme.draw_rounded_rect(
            surface,
            self.search_bar_rect,
            COLOR_SURFACE,
            radius=6,
            border_color=COLOR_SURFACE_BORDER,
            border_width=1
        )
        Theme.draw_icon(surface, "search", self.search_bar_rect.left + 20, self.search_bar_rect.centery, size=16, color=COLOR_ACCENT)

        display_text = self.query if self.query else "Tap to search YouTube..."
        txt_color = COLOR_TEXT_PRIMARY if self.query else COLOR_TEXT_MUTED
        query_surf = Theme.get_font(14).render(display_text, True, txt_color)
        surface.blit(query_surf, (self.search_bar_rect.left + 40, self.search_bar_rect.centery - query_surf.get_height() // 2))

        # 2. Results List or Status Messages
        if self.is_searching:
            loading_font = Theme.get_font(15, bold=True)
            loading_surf = loading_font.render("Searching YouTube...", True, COLOR_ACCENT)
            surface.blit(loading_surf, (SCREEN_WIDTH // 2 - loading_surf.get_width() // 2, CONTENT_Y + 110))
            hint_surf = Theme.get_font(12).render("Fetching metadata and stream info", True, COLOR_TEXT_MUTED)
            surface.blit(hint_surf, (SCREEN_WIDTH // 2 - hint_surf.get_width() // 2, CONTENT_Y + 134))

        elif self.error_message:
            err_surf = Theme.get_font(13).render(self.error_message, True, COLOR_TEXT_MUTED)
            surface.blit(err_surf, (SCREEN_WIDTH // 2 - err_surf.get_width() // 2, CONTENT_Y + 120))

        elif not self.results:
            empty_title = Theme.get_font(15, bold=True).render("Find Music", True, COLOR_TEXT_SECONDARY)
            empty_hint = Theme.get_font(12).render("Tap the search bar above to search YouTube", True, COLOR_TEXT_MUTED)
            surface.blit(empty_title, (SCREEN_WIDTH // 2 - empty_title.get_width() // 2, CONTENT_Y + 100))
            surface.blit(empty_hint, (SCREEN_WIDTH // 2 - empty_hint.get_width() // 2, CONTENT_Y + 126))

        else:
            # Draw Results List
            self.list_view.draw(surface, self._draw_track_item)

        # 3. Action Popup Dialog (if user tapped a track)
        if self.active_track_popup:
            self._draw_action_popup(surface, self.active_track_popup)

        # 4. Virtual Keyboard Overlay (if open)
        if self.keyboard and self.keyboard.is_active:
            self.keyboard.draw(surface)

    def _draw_track_item(self, surface: pygame.Surface, rect: pygame.Rect, index: int, track: Track, is_selected: bool):
        """Renders an individual search result row."""
        # Background card
        bg = COLOR_SURFACE_LIGHT if is_selected else COLOR_SURFACE
        Theme.draw_rounded_rect(surface, rect.inflate(-2, -4), bg, radius=6)

        # Thumbnail (44x44)
        thumb_rect = pygame.Rect(rect.left + 6, rect.top + 4, 44, 44)
        thumb = self.app.cache.get(track.thumbnail_url, THUMBNAIL_SIZE_SMALL)
        if thumb:
            surface.blit(thumb, (thumb_rect.x, thumb_rect.y))
        else:
            pygame.draw.rect(surface, COLOR_SURFACE_LIGHT, thumb_rect, border_radius=4)
            Theme.draw_icon(surface, "music", thumb_rect.centerx, thumb_rect.centery, size=18, color=COLOR_TEXT_MUTED)
            # Async download thumbnail
            self.app.load_thumbnail_async(track.thumbnail_url, THUMBNAIL_SIZE_SMALL)

        # Track Title & Channel
        tx = rect.left + 56
        title_font = Theme.get_font(13, bold=True)
        channel_font = Theme.get_font(11)

        title_text = track.title
        max_title_w = rect.width - 120
        title_surf = title_font.render(title_text, True, COLOR_TEXT_PRIMARY)
        if title_surf.get_width() > max_title_w:
            surface.blit(title_surf, (tx, rect.top + 8), area=pygame.Rect(0, 0, max_title_w, title_surf.get_height()))
        else:
            surface.blit(title_surf, (tx, rect.top + 8))

        channel_text = f"{track.artist}  •  {track.duration_str}"
        channel_surf = channel_font.render(channel_text, True, COLOR_TEXT_SECONDARY)
        surface.blit(channel_surf, (tx, rect.top + 28))

        # Play hint icon on right
        Theme.draw_icon(surface, "play", rect.right - 24, rect.centery, size=16, color=COLOR_ACCENT)

    def _draw_action_popup(self, surface: pygame.Surface, track: Track):
        """Draws modal popup with 'Play Now' and 'Add to Queue' options."""
        # Backdrop
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))

        # Modal Box
        popup_rect = pygame.Rect(50, CONTENT_Y + 30, 380, 160)
        Theme.draw_rounded_rect(surface, popup_rect, COLOR_SURFACE, radius=10,
                                border_color=COLOR_ACCENT, border_width=1)

        # Close X button
        Theme.draw_icon(surface, "cross", popup_rect.right - 20, popup_rect.top + 20, size=14, color=COLOR_TEXT_MUTED)

        # Title
        t_font = Theme.get_font(14, bold=True)
        t_text = track.title
        if len(t_text) > 36:
            t_text = t_text[:34] + "..."
        t_surf = t_font.render(t_text, True, COLOR_TEXT_PRIMARY)
        surface.blit(t_surf, (popup_rect.left + 20, popup_rect.top + 20))

        # Artist
        a_surf = Theme.get_font(12).render(track.artist, True, COLOR_TEXT_SECONDARY)
        surface.blit(a_surf, (popup_rect.left + 20, popup_rect.top + 46))

        # Action Buttons
        btn_play_rect = pygame.Rect(popup_rect.left + 20, popup_rect.bottom - 60, 160, 42)
        Theme.draw_rounded_rect(surface, btn_play_rect, COLOR_ACCENT, radius=6)
        Theme.draw_icon(surface, "play", btn_play_rect.left + 24, btn_play_rect.centery, size=18, color=(255, 255, 255))
        p_txt = Theme.get_font(13, bold=True).render("Play Now", True, (255, 255, 255))
        surface.blit(p_txt, (btn_play_rect.left + 48, btn_play_rect.centery - p_txt.get_height() // 2))

        btn_queue_rect = pygame.Rect(popup_rect.right - 180, popup_rect.bottom - 60, 160, 42)
        Theme.draw_rounded_rect(surface, btn_queue_rect, COLOR_SURFACE_LIGHT, radius=6,
                                border_color=COLOR_SURFACE_BORDER, border_width=1)
        Theme.draw_icon(surface, "queue", btn_queue_rect.left + 24, btn_queue_rect.centery, size=18, color=COLOR_TEXT_PRIMARY)
        q_txt = Theme.get_font(13, bold=True).render("Add to Queue", True, COLOR_TEXT_PRIMARY)
        surface.blit(q_txt, (btn_queue_rect.left + 48, btn_queue_rect.centery - q_txt.get_height() // 2))
