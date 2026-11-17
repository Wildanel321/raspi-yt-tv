"""
Pi Music - Wi-Fi Configuration & Manager View
Integrates with NetworkManager (nmcli) for scanning, connecting, disconnecting,
reconnecting, real-time status/signal monitoring, and captive portal detection.
All operations run asynchronously in background threads.
"""

from typing import TYPE_CHECKING, List, Optional
import pygame

from config import (
    CONTENT_Y, CONTENT_HEIGHT, SCREEN_WIDTH, COLOR_SURFACE,
    COLOR_SURFACE_LIGHT, COLOR_SURFACE_BORDER, COLOR_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER, COLOR_INFO
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
    """Touchscreen Wi-Fi manager with captive portal detection and full controls."""

    def __init__(self, app: "App"):
        super().__init__(app)

        self.networks: List[WifiNetwork] = []
        self.is_scanning = False
        self.is_connecting = False
        self.is_checking_portal = False
        self.status_message = "Ready"
        self.keyboard: Optional[VirtualKeyboard] = None

        # Modal action dialog for selected network
        self.selected_network: Optional[WifiNetwork] = None
        self.show_network_modal = False

        # 1. Action Buttons in Top Header
        header_btn_y = CONTENT_Y + 8
        self.btn_scan = Button(
            pygame.Rect(SCREEN_WIDTH - 84, header_btn_y, 74, 30),
            text="Scan",
            icon="refresh",
            icon_size=13,
            font_size=12,
            bg_color=COLOR_SURFACE_LIGHT,
            callback=self._start_scan
        )

        self.btn_reconnect = Button(
            pygame.Rect(SCREEN_WIDTH - 84, header_btn_y + 34, 74, 28),
            text="Reconn",
            font_size=11,
            bg_color=COLOR_SURFACE_LIGHT,
            callback=self._reconnect_wifi
        )

        # Captive Portal Action Button (appears when portal is detected)
        self.btn_open_portal = Button(
            pygame.Rect(10, CONTENT_Y + 70, SCREEN_WIDTH - 20, 32),
            text="Open Login Portal",
            icon="portal",
            icon_size=16,
            font_size=12,
            bg_color=(140, 80, 10),
            hover_color=(180, 100, 15),
            border_color=COLOR_WARNING,
            callback=self._open_captive_portal
        )

        # 2. Networks List View
        # If captive portal button is shown, list shifts down slightly
        self.list_y_normal = CONTENT_Y + 72
        self.list_y_portal = CONTENT_Y + 106
        self.list_view = ListView(
            pygame.Rect(10, self.list_y_normal, SCREEN_WIDTH - 20, CONTENT_HEIGHT - 76),
            item_height=48,
            on_item_click=self._on_network_row_clicked
        )

        # 3. Network Action Modal Buttons
        self.btn_modal_connect = Button(
            pygame.Rect(60, CONTENT_Y + 120, 110, 38),
            text="Connect",
            font_size=13,
            bg_color=COLOR_ACCENT,
            callback=self._modal_action_connect
        )
        self.btn_modal_disconnect = Button(
            pygame.Rect(185, CONTENT_Y + 120, 110, 38),
            text="Disconnect",
            font_size=13,
            bg_color=(90, 20, 20),
            hover_color=(130, 30, 30),
            callback=self._modal_action_disconnect
        )
        self.btn_modal_cancel = Button(
            pygame.Rect(310, CONTENT_Y + 120, 100, 38),
            text="Close",
            font_size=13,
            bg_color=COLOR_SURFACE_LIGHT,
            callback=self._close_modal
        )

        # Periodic portal checker timer
        self._last_portal_check = 0.0

    def on_enter(self):
        """Called when entering Wi-Fi tab: scan if empty and check portal."""
        self.app.wifi.get_status()
        self._check_portal()
        if not self.networks and not self.is_scanning:
            self._start_scan()

    def _start_scan(self):
        """Triggers asynchronous network scan."""
        if self.is_scanning:
            return
        self.is_scanning = True
        self.status_message = "Scanning Wi-Fi..."

        def _on_scan_done(nets: List[WifiNetwork]):
            self.is_scanning = False
            self.networks = nets
            self.list_view.set_items(nets)
            self.status_message = f"Found {len(nets)} networks" if nets else "No networks found"

        self.app.wifi.scan_networks_async(_on_scan_done)

    def _check_portal(self):
        """Asynchronously probe for captive portal."""
        if self.is_checking_portal:
            return
        self.is_checking_portal = True

        def _on_portal_checked(detected: bool, url: str):
            self.is_checking_portal = False
            if detected:
                self.status_message = "Captive Portal detected!"
            self._update_list_view_layout()

        self.app.wifi.check_captive_portal_async(_on_portal_checked)

    def _update_list_view_layout(self):
        """Adjust list position depending on whether captive portal banner is active."""
        portal_active = self.app.wifi.last_status.get("portal_detected", False)
        target_y = self.list_y_portal if portal_active else self.list_y_normal
        target_h = CONTENT_HEIGHT - (110 if portal_active else 76)

        if self.list_view.rect.top != target_y:
            self.list_view.rect.top = target_y
            self.list_view.rect.height = target_h
            self.list_view.clamp_scroll()

    def _on_network_row_clicked(self, index: int, net: WifiNetwork):
        """Tapping a network opens the action dialog."""
        self.selected_network = net
        self.show_network_modal = True

    def _modal_action_connect(self):
        """Connect button in modal."""
        net = self.selected_network
        self.show_network_modal = False
        if not net:
            return

        if net.is_open:
            self._connect_to_network(net.ssid, "")
        else:
            # Open virtual keyboard for password entry
            self.keyboard = VirtualKeyboard(
                title=f"Password for {net.ssid}",
                initial_text="",
                is_password=True,
                on_submit=lambda pwd: self._connect_to_network(net.ssid, pwd),
                on_cancel=lambda: setattr(self, "keyboard", None)
            )

    def _modal_action_disconnect(self):
        """Disconnect button in modal."""
        self.show_network_modal = False
        self.status_message = "Disconnecting..."
        self.app.wifi.disconnect_async(self._on_disconnect_done)

    def _close_modal(self):
        self.show_network_modal = False
        self.selected_network = None

    def _connect_to_network(self, ssid: str, password: str):
        self.keyboard = None
        self.is_connecting = True
        self.status_message = f"Connecting to {ssid}..."

        def _on_connect_done(success: bool, msg: str):
            self.is_connecting = False
            self.status_message = msg
            self._check_portal()
            self._start_scan()

        self.app.wifi.connect_async(ssid, password, _on_connect_done)

    def _disconnect_wifi(self):
        self.status_message = "Disconnecting..."
        self.app.wifi.disconnect_async(self._on_disconnect_done)

    def _on_disconnect_done(self, success: bool, msg: str):
        self.status_message = msg
        self._update_list_view_layout()
        self._start_scan()

    def _reconnect_wifi(self):
        self.status_message = "Reconnecting..."
        self.app.wifi.reconnect_async(self._on_reconnect_done)

    def _on_reconnect_done(self, success: bool, msg: str):
        self.status_message = msg
        self._check_portal()
        self._start_scan()

    def _open_captive_portal(self):
        """Launch lightweight browser for captive portal without saving credentials."""
        self.status_message = "Opening portal..."
        portal_url = self.app.wifi.last_status.get("portal_url", "")
        success, msg = self.app.wifi.open_portal_browser(portal_url)
        self.status_message = msg
        # Re-check portal after a brief delay
        pygame.time.delay(100)
        self._check_portal()

    def handle_event(self, event: pygame.event.Event) -> bool:
        # 1. Virtual Keyboard has highest priority
        if self.keyboard and self.keyboard.is_active:
            return self.keyboard.handle_event(event)

        # 2. Network Action Modal Dialog
        if self.show_network_modal:
            if self.btn_modal_connect.handle_event(event):
                return True
            if self.btn_modal_disconnect.handle_event(event):
                return True
            if self.btn_modal_cancel.handle_event(event):
                return True
            # Tap outside dialog closes modal
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                dialog_rect = pygame.Rect(40, CONTENT_Y + 40, 400, 130)
                if not dialog_rect.collidepoint(event.pos):
                    self._close_modal()
                    return True
            return True

        # 3. Header Action Buttons
        if self.btn_scan.handle_event(event):
            return True

        if self.btn_reconnect.handle_event(event):
            return True

        # 4. Captive Portal Button (if visible)
        if self.app.wifi.last_status.get("portal_detected", False):
            if self.btn_open_portal.handle_event(event):
                return True

        # 5. List View
        if self.list_view.handle_event(event):
            return True

        return False

    def update(self):
        # Periodically refresh captive portal check every 15 seconds
        now = pygame.time.get_ticks() / 1000.0
        if now - self._last_portal_check > 15.0:
            self._last_portal_check = now
            if self.app.wifi.is_connected() and not self.is_checking_portal:
                self._check_portal()

    def draw(self, surface: pygame.Surface):
        status = self.app.wifi.get_status()
        is_conn = status.get("connected", False)
        portal_detected = status.get("portal_detected", False)
        ssid = status.get("ssid", "Disconnected")
        ip = status.get("ip", "No IP")
        signal = status.get("signal", 0)

        # 1. Connection Status Card (Top 60px)
        card_rect = pygame.Rect(10, CONTENT_Y + 6, SCREEN_WIDTH - 104, 58)
        Theme.draw_rounded_rect(surface, card_rect, COLOR_SURFACE, radius=6,
                                border_color=COLOR_SURFACE_BORDER, border_width=1)

        # State Indicator & Badge
        if portal_detected:
            dot_color = COLOR_WARNING
            state_label = "Portal Login Required"
            state_color = COLOR_WARNING
        elif is_conn:
            dot_color = COLOR_SUCCESS
            state_label = "Connected"
            state_color = COLOR_SUCCESS
        elif self.is_connecting:
            dot_color = COLOR_INFO
            state_label = "Connecting..."
            state_color = COLOR_INFO
        else:
            dot_color = COLOR_DANGER
            state_label = "Disconnected"
            state_color = COLOR_DANGER

        # Dot & SSID Title
        pygame.draw.circle(surface, dot_color, (card_rect.left + 16, card_rect.top + 16), 5)
        title_font = Theme.get_font(13, bold=True)
        title_surf = title_font.render(ssid, True, COLOR_TEXT_PRIMARY)
        max_title_w = card_rect.width - 120
        if title_surf.get_width() > max_title_w:
            surface.blit(title_surf, (card_rect.left + 28, card_rect.top + 8),
                         area=pygame.Rect(0, 0, max_title_w, title_surf.get_height()))
        else:
            surface.blit(title_surf, (card_rect.left + 28, card_rect.top + 8))

        # Status Badge on right of card
        badge_surf = Theme.get_font(10, bold=True).render(state_label, True, state_color)
        surface.blit(badge_surf, (card_rect.right - badge_surf.get_width() - 10, card_rect.top + 10))

        # Subtitle: IP & Signal
        info_font = Theme.get_font(11)
        info_text = f"IP: {ip}  •  Signal: {signal}%  •  {self.app.wifi.active_interface}"
        info_surf = info_font.render(info_text, True, COLOR_TEXT_SECONDARY)
        surface.blit(info_surf, (card_rect.left + 28, card_rect.top + 32))

        # 2. Header Buttons (Scan & Reconnect)
        self.btn_scan.draw(surface)
        self.btn_reconnect.draw(surface)

        # 3. Captive Portal Banner Button (if detected)
        if portal_detected:
            self.btn_open_portal.draw(surface)

        # 4. Networks List
        self._update_list_view_layout()
        self.list_view.draw(surface, self._draw_network_item)

        # 5. Network Selection Modal (Dialog)
        if self.show_network_modal and self.selected_network:
            self._draw_network_modal(surface, self.selected_network)

        # 6. Virtual Keyboard Overlay (if active)
        if self.keyboard and self.keyboard.is_active:
            self.keyboard.draw(surface)

    def _draw_network_item(self, surface: pygame.Surface, rect: pygame.Rect, index: int, net: WifiNetwork, is_selected: bool):
        bg = (40, 25, 25) if net.in_use else (COLOR_SURFACE_LIGHT if is_selected else COLOR_SURFACE)
        border_col = COLOR_ACCENT if net.in_use else None
        Theme.draw_rounded_rect(surface, rect.inflate(-2, -4), bg, radius=6,
                                border_color=border_col, border_width=1 if border_col else 0)

        # Signal Icon & Color
        if net.signal >= 65:
            sig_col = COLOR_SUCCESS
        elif net.signal >= 35:
            sig_col = COLOR_WARNING
        else:
            sig_col = COLOR_DANGER
        Theme.draw_icon(surface, "wifi", rect.left + 18, rect.centery, size=16, color=sig_col)

        # SSID
        ssid_font = Theme.get_font(13, bold=net.in_use)
        ssid_col = COLOR_ACCENT if net.in_use else COLOR_TEXT_PRIMARY
        ssid_surf = ssid_font.render(net.ssid, True, ssid_col)
        max_w = rect.width - 160
        if ssid_surf.get_width() > max_w:
            surface.blit(ssid_surf, (rect.left + 40, rect.top + 7), area=pygame.Rect(0, 0, max_w, ssid_surf.get_height()))
        else:
            surface.blit(ssid_surf, (rect.left + 40, rect.top + 7))

        # Security & Signal Meta
        sec_text = f"{net.security}  •  {net.signal}%"
        sec_surf = Theme.get_font(11).render(sec_text, True, COLOR_TEXT_SECONDARY)
        surface.blit(sec_surf, (rect.left + 40, rect.top + 26))

        # Lock icon if secured
        if not net.is_open:
            Theme.draw_icon(surface, "lock", rect.right - 45, rect.centery, size=13, color=COLOR_TEXT_MUTED)

        # Connected Checkmark
        if net.in_use:
            Theme.draw_icon(surface, "check", rect.right - 22, rect.centery, size=15, color=COLOR_SUCCESS)

    def _draw_network_modal(self, surface: pygame.Surface, net: WifiNetwork):
        """Renders popup dialog for connecting or disconnecting from network."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        dialog_rect = pygame.Rect(40, CONTENT_Y + 40, 400, 134)
        Theme.draw_rounded_rect(surface, dialog_rect, COLOR_SURFACE, radius=10,
                                border_color=COLOR_ACCENT, border_width=1)

        # Title
        t_font = Theme.get_font(14, bold=True)
        t_surf = t_font.render(f"Wi-Fi: {net.ssid}", True, COLOR_TEXT_PRIMARY)
        surface.blit(t_surf, (dialog_rect.left + 20, dialog_rect.top + 16))

        # Details
        meta_text = f"Security: {net.security}  •  Signal: {net.signal}%  •  {'Connected' if net.in_use else 'Available'}"
        meta_surf = Theme.get_font(11).render(meta_text, True, COLOR_TEXT_SECONDARY)
        surface.blit(meta_surf, (dialog_rect.left + 20, dialog_rect.top + 40))

        # Buttons
        self.btn_modal_connect.rect = pygame.Rect(dialog_rect.left + 20, dialog_rect.bottom - 50, 110, 36)
        self.btn_modal_disconnect.rect = pygame.Rect(dialog_rect.left + 140, dialog_rect.bottom - 50, 110, 36)
        self.btn_modal_cancel.rect = pygame.Rect(dialog_rect.right - 120, dialog_rect.bottom - 50, 100, 36)

        # Disable disconnect if not in use
        self.btn_modal_disconnect.is_disabled = not net.in_use

        self.btn_modal_connect.draw(surface)
        self.btn_modal_disconnect.draw(surface)
        self.btn_modal_cancel.draw(surface)
