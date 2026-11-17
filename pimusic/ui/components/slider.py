"""
Pi Music - Touchscreen Slider Component
Used for audio seek bar and volume adjustment.
"""

from typing import Callable, Optional, Tuple
import pygame

from config import COLOR_SURFACE_LIGHT, COLOR_ACCENT, COLOR_TEXT_PRIMARY
from pimusic.ui.theme import Theme

class Slider:
    """Touchscreen slider with smooth dragging and value mapping."""

    def __init__(
        self,
        rect: pygame.Rect,
        min_val: float = 0.0,
        max_val: float = 100.0,
        initial_val: float = 0.0,
        callback: Optional[Callable[[float], None]] = None,
        track_color: Tuple[int, int, int] = COLOR_SURFACE_LIGHT,
        fill_color: Tuple[int, int, int] = COLOR_ACCENT,
        knob_color: Tuple[int, int, int] = COLOR_TEXT_PRIMARY,
        knob_radius: int = 7
    ):
        self.rect = rect
        self.min_val = min_val
        self.max_val = max_val
        self.value = initial_val
        self.callback = callback
        self.track_color = track_color
        self.fill_color = fill_color
        self.knob_color = knob_color
        self.knob_radius = knob_radius
        self.is_dragging = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handles touch events for seeking/sliding."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Expand touch hit box vertically by 10px to accommodate fingers
            hit_box = self.rect.inflate(0, 20)
            if hit_box.collidepoint(event.pos):
                self.is_dragging = True
                self._update_val_from_x(event.pos[0])
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.is_dragging:
                self.is_dragging = False
                self._update_val_from_x(event.pos[0])
                if self.callback:
                    self.callback(self.value)
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self.is_dragging:
                self._update_val_from_x(event.pos[0])
                return True

        return False

    def _update_val_from_x(self, x: int):
        """Calculates slider value based on x coordinate."""
        clamped_x = max(self.rect.left, min(self.rect.right, x))
        ratio = (clamped_x - self.rect.left) / max(1, self.rect.width)
        self.value = self.min_val + ratio * (self.max_val - self.min_val)

    def set_value(self, val: float):
        """Sets value without triggering drag callback."""
        if not self.is_dragging:
            self.value = max(self.min_val, min(self.max_val, val))

    def draw(self, surface: pygame.Surface):
        """Draws the slider track, fill, and knob."""
        track_y = self.rect.centery
        track_h = 4

        # Background track
        track_rect = pygame.Rect(self.rect.left, track_y - track_h // 2, self.rect.width, track_h)
        pygame.draw.rect(surface, self.track_color, track_rect, border_radius=2)

        # Active filled track
        span = self.max_val - self.min_val
        ratio = (self.value - self.min_val) / span if span > 0 else 0
        ratio = max(0.0, min(1.0, ratio))
        fill_width = int(self.rect.width * ratio)

        if fill_width > 0:
            fill_rect = pygame.Rect(self.rect.left, track_y - track_h // 2, fill_width, track_h)
            pygame.draw.rect(surface, self.fill_color, fill_rect, border_radius=2)

        # Circular knob
        knob_x = self.rect.left + fill_width
        pygame.draw.circle(surface, self.knob_color, (knob_x, track_y), self.knob_radius)
        if self.is_dragging:
            # Highlight ring around knob when dragging
            pygame.draw.circle(surface, self.fill_color, (knob_x, track_y), self.knob_radius + 3, 2)
