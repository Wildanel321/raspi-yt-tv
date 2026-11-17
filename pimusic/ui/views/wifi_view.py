"""
Pi Music - Wi-Fi Configuration View
Scan, view connection status, and connect to Wi-Fi networks using NetworkManager.
"""

from typing import TYPE_CHECKING, List, Optional
import pygame

from config import (
    CONTENT_Y, CONTENT_HEIGHT, SCREEN_WIDTH, COLOR_SURFACE,
    COLOR_SURFACE_LIGHT, COLOR_SURFACE_BORDER, COLOR_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER
)
from pimusic.core.wifi import WifiNetwork
from pimusic.ui.theme import Theme
from pimusic.ui.components.button import Button
from pimusic.ui.components.list_view import ListView
from pimusic.ui.components.keyboard import VirtualKeyboard
from pimusic.ui.views.base_view import BaseView

if TYPE_CHECKING:
    from pimusic.ui.app import App

class WifiView(BaseView):
    """Touchscreen Wi-Fi network manager and scanner."""

    def __init__(self, app: "App"):
        super().__init__(app)

        self.networks: List[WifiNetwork] = []
        self.is_scanning = False
        self.is_connecting = False
        self.status_message = ""
        self.target_network: Optional[WifiNetwork] = None
        self.keyboard: Optional[VirtualKeyboard] = None

        # Refresh / Scan Button
        self.btn_scan = Button(
            pygame.Rect(SCREEN_WIDTH - 110, CONTENT_Y + 10, 100, 32),
            text="Scan",
            icon="refresh",
            icon_size=14,
            font_size=13,
            bg_color=COLOR_SURFACE_LIGHT,
            callback=self._start_scan
        )

        # Networks List View
        list_y = CONTENT_Y + 76
        list_h = CONTENT_HEIGHT - 82
        self.list_view = ListView(
            pygame.Rect(10, list_y, SCREEN_WIDTH - 20, list_h),
            item_height=46,
            on_item_click=self._on_network_clicked
        )

    def on_enter(self):
        """Scan when entering view if network list is empty."""
        if not self.networks and not self.is_scanning:
            self._start_scan()

    def _start_scan(self):
        self.is_scanning = True
        self.status_message = "Scanning for Wi-Fi networks..."

        def _on_scan_done(nets: List[WifiNetwork]):
            self.is_scanning = False
            self.networks = nets
            self.list_view.set_items(nets)
            self.status_message = f"Found {len(nets)} networks" if nets else "No networks found"

        self.app.wifi.scan_networks_async(_on_scan_done)

    def _on_network_clicked(self, index: int, net: WifiNetwork):
        """Prompt for password if secured, or connect directly if open."""
        self.target_network = net
        if "open" in net.security.lower() or not net.security:
            self._connect_to_network(net.ssid, "")
        else:
            self.keyboard = VirtualKeyboard(
                title=f"Password for {net.ssid}",
                initial_text="",
                is_password=True,
                on_submit=lambda pwd: self._connect_to_network(net.ssid, pwd),
                on_cancel=lambda: setattr(self, "keyboard", None)
            )

    def _connect_to_network(self, ssid: str, password: str):
        self.keyboard = None
        self.is_connecting = True
        self.status_message = f"Connecting to {ssid}..."

        def _on_connect_done(success: bool, msg: str):
            self.is_connecting = False
            self.status_message = msg
            self._start_scan()

        self.app.wifi.connect_async(ssid, password, _on_connect_done)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.keyboard and self.keyboard.is_active:
            return self.keyboard.handle_event(event)

        if self.btn_scan.handle_event(event):
            return True

        if self.list_view.handle_event(event):
            return True

        return False

    def update(self):
        pass

    def draw(self, surface: pygame.Surface):
        # 1. Connection Status Card (Top 60px)
        card_rect = pygame.Rect(10, CONTENT_Y + 8, SCREEN_WIDTH - 130, 58)
        Theme.draw_rounded_rect(surface, card_rect, COLOR_SURFACE, radius=6,
                                border_color=COLOR_SURFACE_BORDER, border_width=1)

        status = self.app.wifi.get_status()
        is_conn = status.get("connected", False)
        ssid = status.get("ssid", "Disconnected")
        ip = status.get("ip", "No IP")

        # Status Dot
        dot_color = COLOR_SUCCESS if is_conn else COLOR_DANGER
        pygame.draw.circle(surface, dot_color, (card_rect.left + 16, card_rect.top + 20), 5)

        # SSID & IP
        title_surf = Theme.get_font(13, bold=True).render(ssid, True, COLOR_TEXT_PRIMARY)
        surface.blit(title_surf, (card_rect.left + 30, card_rect.top + 12))

        ip_surf = Theme.get_font(11).render(f"IP: {ip}", True, COLOR_TEXT_SECONDARY)
        surface.blit(ip_surf, (card_rect.left + 30, card_rect.top + 34))

        # 2. Scan Button
        self.btn_scan.draw(surface)

        # Status text below scan button
        stat_color = COLOR_WARNING if (self.is_scanning or self.is_connecting) else COLOR_TEXT_MUTED
        stat_surf = Theme.get_font(10).render(self.status_message, True, stat_color)
        surface.blit(stat_surf, (SCREEN_WIDTH - 120, CONTENT_Y + 48))

        # 3. Networks List
        self.list_view.draw(surface, self._draw_network_item)

        # 4. Keyboard Modal
        if self.keyboard and self.keyboard.is_active:
            self.keyboard.draw(surface)

    def _draw_network_item(self, surface: pygame.Surface, rect: pygame.Rect, index: int, net: WifiNetwork, is_selected: bool):
        bg = COLOR_SURFACE_LIGHT if is_selected else COLOR_SURFACE
        border_col = COLOR_SUCCESS if net.in_use else None
        Theme.draw_rounded_rect(surface, rect.inflate(-2, -4), bg, radius=6,
                                border_color=border_col, border_width=1 if border_col else 0)

        # Wi-Fi Icon & Signal
        sig_col = COLOR_SUCCESS if net.signal >= 65 else (COLOR_WARNING if net.signal >= 35 else COLOR_DANGER)
        Theme.draw_icon(surface, "wifi", rect.left + 20, rect.centery, size=16, color=sig_col)

        # SSID & Security
        ssid_font = Theme.get_font(13, bold=net.in_use)
        ssid_col = COLOR_SUCCESS if net.in_use else COLOR_TEXT_PRIMARY
        ssid_surf = ssid_font.render(net.ssid, True, ssid_col)
        surface.blit(ssid_surf, (rect.left + 44, rect.top + 8))

        sec_surf = Theme.get_font(10).render(f"{net.security}  •  {net.signal}%", True, COLOR_TEXT_SECONDARY)
        surface.blit(sec_surf, (rect.left + 44, rect.top + 26))

        # Connected badge
        if net.in_use:
            Theme.draw_icon(surface, "check", rect.right - 24, rect.centery, size=14, color=COLOR_SUCCESS)
