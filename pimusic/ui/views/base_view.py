"""
Pi Music - Base View Class
Interface for all application view screens.
"""

from typing import TYPE_CHECKING
import pygame

from config import CONTENT_Y, CONTENT_HEIGHT, SCREEN_WIDTH

if TYPE_CHECKING:
    from pimusic.ui.app import App

class BaseView:
    """Base class for all UI screens."""

    def __init__(self, app: "App"):
        self.app = app
        self.rect = pygame.Rect(0, CONTENT_Y, SCREEN_WIDTH, CONTENT_HEIGHT)

    def on_enter(self):
        """Called when this view becomes active."""
        pass

    def on_leave(self):
        """Called when transitioning away from this view."""
        pass

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle input event. Return True if event was handled."""
        return False

    def update(self):
        """Update animations, timers, and state."""
        pass

    def draw(self, surface: pygame.Surface):
        """Render the view onto the surface."""
        pass
