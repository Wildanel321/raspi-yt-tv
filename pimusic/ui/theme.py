"""
Pi Music - UI Theme and Icon Rendering Engine
Colors, typography, and procedural vector icon drawing for Pygame.
Optimized for 480x320 TFT displays with crisp contrast.
"""

import math
import pygame
from typing import Dict, Tuple

from config import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_LIGHT, COLOR_SURFACE_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED, COLOR_SUCCESS,
    COLOR_WARNING, COLOR_DANGER
)

class Theme:
    """Manages fonts, colors, and graphics rendering."""

    _fonts: Dict[str, pygame.font.Font] = {}

    @classmethod
    def get_font(cls, size: int, bold: bool = False) -> pygame.font.Font:
        """Retrieves or caches a pygame font at the specified size."""
        key = f"{size}_{bold}"
        if key not in cls._fonts:
            try:
                # Prefer clean sans-serif system fonts
                font_name = pygame.font.match_font("dejavusans", bold=bold) or \
                            pygame.font.match_font("liberationsans", bold=bold) or \
                            pygame.font.match_font("arial", bold=bold)
                if font_name:
                    cls._fonts[key] = pygame.font.Font(font_name, size)
                else:
                    cls._fonts[key] = pygame.font.SysFont(None, size, bold=bold)
            except Exception:
                cls._fonts[key] = pygame.font.SysFont(None, size, bold=bold)
        return cls._fonts[key]

    @staticmethod
    def draw_rounded_rect(
        surface: pygame.Surface,
        rect: pygame.Rect,
        color: Tuple[int, int, int],
        radius: int = 6,
        border_color: Tuple[int, int, int] = None,
        border_width: int = 1
    ):
        """Draws a smooth rounded rectangle with optional border."""
        pygame.draw.rect(surface, color, rect, border_radius=radius)
        if border_color and border_width > 0:
            pygame.draw.rect(surface, border_color, rect, width=border_width, border_radius=radius)

    @staticmethod
    def draw_icon(
        surface: pygame.Surface,
        icon_name: str,
        center_x: int,
        center_y: int,
        size: int = 20,
        color: Tuple[int, int, int] = COLOR_TEXT_PRIMARY
    ):
        """Procedurally draws vector icons with clean geometric shapes."""
        hs = size // 2

        if icon_name == "play":
            # Right-pointing triangle
            points = [
                (center_x - hs + 2, center_y - hs),
                (center_x - hs + 2, center_y + hs),
                (center_x + hs, center_y)
            ]
            pygame.draw.polygon(surface, color, points)

        elif icon_name == "pause":
            # Two vertical bars
            bw = max(3, size // 4)
            gap = max(2, size // 4)
            r1 = pygame.Rect(center_x - bw - gap // 2, center_y - hs, bw, size)
            r2 = pygame.Rect(center_x + gap // 2, center_y - hs, bw, size)
            pygame.draw.rect(surface, color, r1)
            pygame.draw.rect(surface, color, r2)

        elif icon_name == "stop":
            # Solid square
            r = pygame.Rect(center_x - hs, center_y - hs, size, size)
            pygame.draw.rect(surface, color, r)

        elif icon_name == "next":
            # Triangle + bar
            bw = max(2, size // 6)
            tri_pts = [
                (center_x - hs, center_y - hs),
                (center_x - hs, center_y + hs),
                (center_x + hs - bw - 2, center_y)
            ]
            pygame.draw.polygon(surface, color, tri_pts)
            bar_rect = pygame.Rect(center_x + hs - bw, center_y - hs, bw, size)
            pygame.draw.rect(surface, color, bar_rect)

        elif icon_name == "prev":
            # Bar + left-pointing triangle
            bw = max(2, size // 6)
            bar_rect = pygame.Rect(center_x - hs, center_y - hs, bw, size)
            pygame.draw.rect(surface, color, bar_rect)
            tri_pts = [
                (center_x + hs, center_y - hs),
                (center_x + hs, center_y + hs),
                (center_x - hs + bw + 2, center_y)
            ]
            pygame.draw.polygon(surface, color, tri_pts)

        elif icon_name == "search":
            # Magnifying glass
            rad = max(4, hs - 3)
            cx, cy = center_x - 2, center_y - 2
            pygame.draw.circle(surface, color, (cx, cy), rad, 2)
            pygame.draw.line(surface, color, (cx + rad - 1, cy + rad - 1), (center_x + hs, center_y + hs), 3)

        elif icon_name == "queue":
            # 3 horizontal list lines with small dots
            gap = size // 3
            for i in range(-1, 2):
                y = center_y + (i * gap)
                pygame.draw.circle(surface, color, (center_x - hs + 2, y), 2)
                pygame.draw.line(surface, color, (center_x - hs + 8, y), (center_x + hs, y), 2)

        elif icon_name == "wifi":
            # Arcs or dot + bars
            base_y = center_y + hs - 2
            pygame.draw.circle(surface, color, (center_x, base_y), 2)
            for r in (6, 12):
                if hs >= r:
                    arc_rect = pygame.Rect(center_x - r, base_y - r, r * 2, r * 2)
                    pygame.draw.arc(surface, color, arc_rect, 0.785, 2.356, 2)

        elif icon_name == "settings":
            # Gear / Cog
            pygame.draw.circle(surface, color, (center_x, center_y), hs - 2, 2)
            pygame.draw.circle(surface, color, (center_x, center_y), 3)
            for angle in range(0, 360, 45):
                rad = math.radians(angle)
                x1 = int(center_x + (hs - 4) * math.cos(rad))
                y1 = int(center_y + (hs - 4) * math.sin(rad))
                x2 = int(center_x + hs * math.cos(rad))
                y2 = int(center_y + hs * math.sin(rad))
                pygame.draw.line(surface, color, (x1, y1), (x2, y2), 2)

        elif icon_name == "music":
            # Musical Eighth Note
            pygame.draw.circle(surface, color, (center_x - 3, center_y + 4), 3)
            pygame.draw.line(surface, color, (center_x, center_y + 4), (center_x, center_y - hs), 2)
            pygame.draw.line(surface, color, (center_x, center_y - hs), (center_x + 5, center_y - hs + 3), 2)

        elif icon_name == "volume":
            # Speaker cone
            pts = [
                (center_x - hs, center_y - 3),
                (center_x - hs + 4, center_y - 3),
                (center_x - hs + 8, center_y - hs),
                (center_x - hs + 8, center_y + hs),
                (center_x - hs + 4, center_y + 3),
                (center_x - hs, center_y + 3),
            ]
            pygame.draw.polygon(surface, color, pts)
            # Sound waves
            arc_rect = pygame.Rect(center_x - 2, center_y - 6, 8, 12)
            pygame.draw.arc(surface, color, arc_rect, -1.0, 1.0, 2)

        elif icon_name == "trash":
            # Bin
            tw = max(8, size - 4)
            th = size - 4
            pygame.draw.rect(surface, color, pygame.Rect(center_x - tw // 2, center_y - th // 2 + 3, tw, th - 3), 2)
            pygame.draw.line(surface, color, (center_x - hs, center_y - th // 2 + 2), (center_x + hs, center_y - th // 2 + 2), 2)

        elif icon_name == "refresh":
            # Circular arrow
            arc_rect = pygame.Rect(center_x - hs + 2, center_y - hs + 2, size - 4, size - 4)
            pygame.draw.arc(surface, color, arc_rect, 0.5, 5.5, 2)
            pygame.draw.polygon(surface, color, [
                (center_x + hs - 4, center_y - 1),
                (center_x + hs, center_y - 6),
                (center_x + hs + 3, center_y - 1)
            ])

        elif icon_name == "backspace":
            # Keyboard backspace
            pts = [
                (center_x - hs, center_y),
                (center_x - hs + 6, center_y - hs + 2),
                (center_x + hs, center_y - hs + 2),
                (center_x + hs, center_y + hs - 2),
                (center_x - hs + 6, center_y + hs - 2),
            ]
            pygame.draw.polygon(surface, color, pts, 2)
            pygame.draw.line(surface, color, (center_x - 1, center_y - 3), (center_x + 5, center_y + 3), 2)
            pygame.draw.line(surface, color, (center_x + 5, center_y - 3), (center_x - 1, center_y + 3), 2)

        elif icon_name == "check":
            # Checkmark
            pts = [
                (center_x - hs + 2, center_y),
                (center_x - 1, center_y + hs - 3),
                (center_x + hs - 1, center_y - hs + 3)
            ]
            pygame.draw.lines(surface, color, False, pts, 2)

        elif icon_name == "cross":
            # X mark
            pygame.draw.line(surface, color, (center_x - hs + 3, center_y - hs + 3), (center_x + hs - 3, center_y + hs - 3), 2)
            pygame.draw.line(surface, color, (center_x + hs - 3, center_y - hs + 3), (center_x - hs + 3, center_y + hs - 3), 2)
