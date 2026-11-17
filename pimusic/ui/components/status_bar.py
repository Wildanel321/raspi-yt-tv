"""
Pi Music - Top Status Bar Component
Displays current time, Wi-Fi status, playback indicator, and hardware metrics.
"""

import pygame
from typing import Optional

from config import (
    SCREEN_WIDTH, STATUS_BAR_HEIGHT, COLOR_SURFACE, COLOR_SURFACE_BORDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ACCENT, COLOR_INFO
)
from pimusic.core.system_info import SystemInfo
from pimusic.ui.theme import Theme

class StatusBar:
    """Fixed top status bar with real-time indicators."""

    def __init__(self):
        self.rect = pygame.Rect(0, 0, SCREEN_WIDTH, STATUS_BAR_HEIGHT)
        self.wifi_connected = False
        self.portal_detected = False
        self.bt_connected = False
        self.is_playing = False
        self.current_title = ""
        self._last_time_str = ""
        self._cpu_temp_str = ""
        self._last_update = 0.0

    def update(
        self,
        wifi_connected: bool,
        is_playing: bool,
        current_title: str,
        portal_detected: bool = False,
        bt_connected: bool = False
    ):
        """Update status values periodically."""
        self.wifi_connected = wifi_connected
        self.portal_detected = portal_detected
        self.bt_connected = bt_connected
        self.is_playing = is_playing
        self.current_title = current_title

        # Check clock and temp every 2 seconds
        now = pygame.time.get_ticks() / 1000.0
        if now - self._last_update > 2.0:
            self._last_update = now
            self._last_time_str = SystemInfo.get_time_string()
            temp = SystemInfo.get_cpu_temp()
            self._cpu_temp_str = f"{temp:.0f}°C" if temp else ""

    def draw(self, surface: pygame.Surface):
        """Render status bar."""
        # Background and subtle bottom separator
        pygame.draw.rect(surface, COLOR_SURFACE, self.rect)
        pygame.draw.line(surface, COLOR_SURFACE_BORDER, (0, self.rect.bottom - 1),
                         (SCREEN_WIDTH, self.rect.bottom - 1), 1)

        cy = self.rect.centery
        font_sm = Theme.get_font(12, bold=True)

        # 1. Left: App title / Playing track snippet
        if self.is_playing and self.current_title:
            title_text = self.current_title
            if len(title_text) > 30:
                title_text = title_text[:28] + "..."
            title_surf = font_sm.render(title_text, True, COLOR_TEXT_PRIMARY)
        else:
            title_surf = font_sm.render("Pi Music", True, COLOR_ACCENT)
        surface.blit(title_surf, (8, cy - title_surf.get_height() // 2))

        # 2. Right: Wi-Fi, CPU Temp, Time
        right_x = SCREEN_WIDTH - 8

        # Clock
        time_text = self._last_time_str or SystemInfo.get_time_string()
        time_surf = font_sm.render(time_text, True, COLOR_TEXT_PRIMARY)
        time_rect = time_surf.get_rect(midright=(right_x, cy))
        surface.blit(time_surf, time_rect)
        right_x -= (time_surf.get_width() + 10)

        # CPU Temp
        if self._cpu_temp_str:
            temp_surf = Theme.get_font(11).render(self._cpu_temp_str, True, COLOR_TEXT_MUTED)
            temp_rect = temp_surf.get_rect(midright=(right_x, cy))
            surface.blit(temp_surf, temp_rect)
            right_x -= (temp_surf.get_width() + 10)

        # Bluetooth icon (if connected)
        if self.bt_connected:
            Theme.draw_icon(surface, "bluetooth", right_x - 8, cy, size=13, color=COLOR_INFO)
            right_x -= 18

        # Wi-Fi icon
        if self.portal_detected:
            wifi_color = COLOR_WARNING
        elif self.wifi_connected:
            wifi_color = COLOR_SUCCESS
        else:
            wifi_color = COLOR_TEXT_MUTED
        Theme.draw_icon(surface, "wifi", right_x - 8, cy, size=14, color=wifi_color)
