"""
Pi Music - Touchscreen Scrollable ListView Component
Efficient scrollable list with touch drag, momentum damping,
visible item culling, and scrollbar indicator.
"""

from typing import Any, Callable, List, Optional
import pygame

from config import COLOR_SURFACE_LIGHT, COLOR_ACCENT
from pimusic.ui.theme import Theme

class ListItem:
    """Represents an item in the ListView."""
    def __init__(self, data: Any, height: int = 48):
        self.data = data
        self.height = height


class ListView:
    """Touchscreen scrollable list with item click callbacks."""

    def __init__(
        self,
        rect: pygame.Rect,
        item_height: int = 48,
        on_item_click: Optional[Callable[[int, Any], None]] = None
    ):
        self.rect = rect
        self.item_height = item_height
        self.on_item_click = on_item_click

        self.items: List[Any] = []
        self.scroll_y = 0.0
        self.target_scroll_y = 0.0

        # Drag tracking
        self.is_dragging = False
        self.drag_start_y = 0
        self.drag_start_scroll_y = 0.0
        self.drag_distance = 0
        self.selected_index = -1

    def set_items(self, items: List[Any]):
        """Update items in list and reset or clamp scroll."""
        self.items = items
        self.clamp_scroll()

    @property
    def total_height(self) -> int:
        return len(self.items) * self.item_height

    @property
    def max_scroll(self) -> float:
        return max(0, self.total_height - self.rect.height)

    def clamp_scroll(self):
        """Ensure scroll stays within list bounds."""
        self.scroll_y = max(0.0, min(self.max_scroll, self.scroll_y))
        self.target_scroll_y = self.scroll_y

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Processes touch scrolling and item taps."""
        if not self.rect.collidepoint(getattr(event, "pos", (-1, -1))):
            if event.type == pygame.MOUSEBUTTONUP:
                self.is_dragging = False
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.is_dragging = True
            self.drag_start_y = event.pos[1]
            self.drag_start_scroll_y = self.scroll_y
            self.drag_distance = 0
            return True

        elif event.type == pygame.MOUSEMOTION:
            if self.is_dragging:
                delta_y = event.pos[1] - self.drag_start_y
                self.drag_distance += abs(delta_y)
                # Invert: dragging up scrolls down
                new_scroll = self.drag_start_scroll_y - delta_y
                self.scroll_y = max(0.0, min(self.max_scroll, new_scroll))
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.is_dragging:
                self.is_dragging = False
                # If total drag was small (< 8px), it's a tap!
                if self.drag_distance < 8:
                    relative_y = event.pos[1] - self.rect.top + self.scroll_y
                    clicked_idx = int(relative_y // self.item_height)
                    if 0 <= clicked_idx < len(self.items):
                        self.selected_index = clicked_idx
                        if self.on_item_click:
                            self.on_item_click(clicked_idx, self.items[clicked_idx])
                        return True
                return True

        # Mouse wheel support
        elif event.type == pygame.MOUSEWHEEL:
            self.scroll_y -= event.y * 24
            self.clamp_scroll()
            return True

        return False

    def draw(
        self,
        surface: pygame.Surface,
        draw_item_func: Callable[[pygame.Surface, pygame.Rect, int, Any, bool], None]
    ):
        """
        Renders visible items using provided item drawing function.
        Only items within current viewport are rendered.
        """
        # Set clipping area to list rect
        old_clip = surface.get_clip()
        surface.set_clip(self.rect)

        first_visible_idx = max(0, int(self.scroll_y // self.item_height))
        visible_count = int(self.rect.height // self.item_height) + 2
        last_visible_idx = min(len(self.items), first_visible_idx + visible_count)

        for idx in range(first_visible_idx, last_visible_idx):
            item = self.items[idx]
            item_top = self.rect.top + (idx * self.item_height) - int(self.scroll_y)
            item_rect = pygame.Rect(self.rect.left, item_top, self.rect.width, self.item_height)
            is_selected = (idx == self.selected_index)
            draw_item_func(surface, item_rect, idx, item, is_selected)

        # Draw subtle scrollbar if list is scrollable
        if self.max_scroll > 0:
            sb_w = 4
            sb_x = self.rect.right - sb_w - 2
            ratio = self.rect.height / self.total_height
            thumb_h = max(20, int(self.rect.height * ratio))
            thumb_y = self.rect.top + int((self.scroll_y / self.max_scroll) * (self.rect.height - thumb_h))
            sb_rect = pygame.Rect(sb_x, thumb_y, sb_w, thumb_h)
            pygame.draw.rect(surface, COLOR_SURFACE_LIGHT, sb_rect, border_radius=2)

        # Restore previous clipping
        surface.set_clip(old_clip)
