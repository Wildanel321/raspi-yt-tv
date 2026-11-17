"""
Pi Music - Touchscreen Button Component
Large, finger-friendly touch target with visual feedback on press.
"""

from typing import Callable, Optional, Tuple
import pygame

from config import (
    COLOR_SURFACE, COLOR_SURFACE_LIGHT, COLOR_SURFACE_BORDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED, COLOR_ACCENT
)
from pimusic.ui.theme import Theme

class Button:
    """Touchscreen button supporting icons, text, states, and callbacks."""

    def __init__(
        self,
        rect: pygame.Rect,
        text: str = "",
        icon: str = "",
        callback: Optional[Callable[[], None]] = None,
        bg_color: Tuple[int, int, int] = COLOR_SURFACE,
        hover_color: Tuple[int, int, int] = COLOR_SURFACE_LIGHT,
        text_color: Tuple[int, int, int] = COLOR_TEXT_PRIMARY,
        icon_size: int = 18,
        font_size: int = 15,
        radius: int = 6,
        is_toggle: bool = False,
        border_color: Optional[Tuple[int, int, int]] = COLOR_SURFACE_BORDER
    ):
        self.rect = rect
        self.text = text
        self.icon = icon
        self.callback = callback
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.icon_size = icon_size
        self.font_size = font_size
        self.radius = radius
        self.is_toggle = is_toggle
        self.is_active = False
        self.is_pressed = False
        self.is_disabled = False
        self.border_color = border_color
        self.badge_count: Optional[int] = None

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Processes touch / mouse input. Returns True if clicked."""
        if self.is_disabled:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.is_pressed = True
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.is_pressed:
                self.is_pressed = False
                if self.rect.collidepoint(event.pos):
                    if self.is_toggle:
                        self.is_active = not self.is_active
                    if self.callback:
                        self.callback()
                    return True
        return False

    def draw(self, surface: pygame.Surface):
        """Renders the button to the screen surface."""
        # Determine background color
        if self.is_disabled:
            bg = (self.bg_color[0] // 2, self.bg_color[1] // 2, self.bg_color[2] // 2)
            txt_col = COLOR_TEXT_MUTED
            border = None
        elif self.is_pressed or self.is_active:
            bg = self.hover_color
            txt_col = COLOR_ACCENT if self.is_active else COLOR_TEXT_PRIMARY
            border = COLOR_ACCENT if self.is_active else self.border_color
        else:
            bg = self.bg_color
            txt_col = self.text_color
            border = self.border_color

        Theme.draw_rounded_rect(
            surface,
            self.rect,
            bg,
            radius=self.radius,
            border_color=border,
            border_width=1 if border else 0
        )

        cx = self.rect.centerx
        cy = self.rect.centery

        # Render Icon
        if self.icon and not self.text:
            Theme.draw_icon(surface, self.icon, cx, cy, size=self.icon_size, color=txt_col)
        elif self.icon and self.text:
            # Icon on left, text on right
            icon_x = self.rect.left + 16
            Theme.draw_icon(surface, self.icon, icon_x, cy, size=self.icon_size, color=txt_col)
            font = Theme.get_font(self.font_size, bold=self.is_active)
            rendered_text = font.render(self.text, True, txt_col)
            text_rect = rendered_text.get_rect(midleft=(icon_x + self.icon_size // 2 + 8, cy))
            surface.blit(rendered_text, text_rect)
        elif self.text:
            font = Theme.get_font(self.font_size, bold=self.is_active)
            rendered_text = font.render(self.text, True, txt_col)
            text_rect = rendered_text.get_rect(center=(cx, cy))
            surface.blit(rendered_text, text_rect)

        # Render optional badge (e.g. number of items in queue)
        if self.badge_count is not None and self.badge_count > 0:
            badge_str = str(self.badge_count) if self.badge_count <= 99 else "99+"
            badge_font = Theme.get_font(10, bold=True)
            badge_text = badge_font.render(badge_str, True, (255, 255, 255))
            bw = max(14, badge_text.get_width() + 6)
            badge_rect = pygame.Rect(self.rect.right - bw - 2, self.rect.top + 2, bw, 13)
            pygame.draw.rect(surface, COLOR_ACCENT, badge_rect, border_radius=6)
            surface.blit(badge_text, badge_text.get_rect(center=badge_rect.center))
