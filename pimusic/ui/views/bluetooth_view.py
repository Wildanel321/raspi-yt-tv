"""
Pi Music - Bluetooth & Audio Output Settings View
Allows scanning, pairing, connecting, disconnecting Bluetooth audio devices,
and switching audio output between the 3.5mm headphone jack and Bluetooth.
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
from pimusic.core.bluetooth import BluetoothDevice
from pimusic.ui.theme import Theme
from pimusic.ui.components.button import Button
from pimusic.ui.components.list_view import ListView
from pimusic.ui.views.base_view import BaseView

if TYPE_CHECKING:
    from pimusic.ui.app import App


class BluetoothView(BaseView):
    """Touchscreen Bluetooth manager and Audio Output selector."""

    def __init__(self, app: "App"):
        super().__init__(app)

        self.devices: List[BluetoothDevice] = []
        self.status_message = "Ready"
        self.selected_device: Optional[BluetoothDevice] = None
        self.show_device_modal = False

        # 1. Audio Output Mode Selector Buttons (Row 1)
        btn_y = CONTENT_Y + 6
        self.btn_output_jack = Button(
            pygame.Rect(10, btn_y, 140, 30),
            text="3.5mm Jack",
            font_size=11,
            bg_color=COLOR_ACCENT if self.app.bluetooth.audio_output_mode == "jack" else COLOR_SURFACE_LIGHT,
            callback=lambda: self._select_output_mode("jack")
        )

        self.btn_output_bt = Button(
            pygame.Rect(156, btn_y, 140, 30),
            text="Bluetooth Audio",
            icon="bluetooth",
            icon_size=12,
            font_size=11,
            bg_color=COLOR_ACCENT if self.app.bluetooth.audio_output_mode == "bluetooth" else COLOR_SURFACE_LIGHT,
            callback=lambda: self._select_output_mode("bluetooth")
        )

        self.btn_scan = Button(
            pygame.Rect(SCREEN_WIDTH - 84, btn_y, 74, 30),
            text="Scan",
            icon="refresh",
            icon_size=12,
            font_size=11,
            bg_color=COLOR_SURFACE_LIGHT,
            callback=self._start_scan
        )

        # 2. Device List View
        self.list_y = CONTENT_Y + 66
        self.list_view = ListView(
            pygame.Rect(10, self.list_y, SCREEN_WIDTH - 20, CONTENT_HEIGHT - 70),
            item_height=46,
            on_item_click=self._on_device_row_clicked
        )

        # 3. Device Action Modal Buttons
        modal_btn_y = CONTENT_Y + 125
        self.btn_modal_connect = Button(
            pygame.Rect(60, modal_btn_y, 110, 38),
            text="Connect",
            font_size=12,
            bg_color=COLOR_ACCENT,
            callback=self._modal_action_connect
        )
        self.btn_modal_disconnect = Button(
            pygame.Rect(60, modal_btn_y, 110, 38),
            text="Disconnect",
            font_size=12,
            bg_color=(90, 20, 20),
            hover_color=(130, 30, 30),
            callback=self._modal_action_disconnect
        )
        self.btn_modal_unpair = Button(
            pygame.Rect(185, modal_btn_y, 110, 38),
            text="Unpair",
            font_size=12,
            bg_color=COLOR_SURFACE_LIGHT,
            callback=self._modal_action_unpair
        )
        self.btn_modal_cancel = Button(
            pygame.Rect(310, modal_btn_y, 110, 38),
            text="Cancel",
            font_size=12,
            bg_color=COLOR_SURFACE_LIGHT,
            callback=self._close_modal
        )

        # Populate initial devices
        self._refresh_device_list()

    def _select_output_mode(self, mode: str):
        """Switch audio output between 3.5mm jack and Bluetooth."""
        self.app.bluetooth.save_audio_output_pref(mode)
        conn_dev = self.app.bluetooth.get_connected_device()
        conn_mac = conn_dev.mac if conn_dev else None
        self.app.player.set_audio_output(mode, conn_mac)
        self.status_message = f"Audio Output: {'3.5mm Jack' if mode == 'jack' else 'Bluetooth'}"

        # Update button highlights
        self.btn_output_jack.bg_color = COLOR_ACCENT if mode == "jack" else COLOR_SURFACE_LIGHT
        self.btn_output_bt.bg_color = COLOR_ACCENT if mode == "bluetooth" else COLOR_SURFACE_LIGHT

    def _start_scan(self):
        """Triggers asynchronous Bluetooth scan."""
        if self.app.bluetooth.is_scanning:
            return
        self.status_message = "Scanning for Bluetooth devices..."
        self.app.bluetooth.scan_devices_async(callback=self._on_scan_completed)

    def _on_scan_completed(self, devices: List[BluetoothDevice]):
        self.status_message = f"Scan complete. {len(devices)} devices found."
        self._refresh_device_list()

    def _refresh_device_list(self):
        """Syncs the internal device list with the BluetoothManager."""
        self.devices = self.app.bluetooth.get_devices()
        items = []
        for dev in self.devices:
            status_tag = ""
            tag_color = COLOR_TEXT_MUTED
            if dev.connected:
                status_tag = "[Connected]"
                tag_color = COLOR_SUCCESS
            elif dev.paired:
                status_tag = "[Paired]"
                tag_color = COLOR_INFO

            items.append({
                "title": dev.name,
                "subtitle": f"{dev.mac}  {status_tag}",
                "tag_color": tag_color,
                "device": dev
            })
        self.list_view.set_items(items)

    def _on_device_row_clicked(self, index: int, item: dict):
        self.selected_device = item.get("device")
        if self.selected_device:
            self.show_device_modal = True

    def _close_modal(self):
        self.show_device_modal = False
        self.selected_device = None

    def _modal_action_connect(self):
        if not self.selected_device:
            return
        mac = self.selected_device.mac
        name = self.selected_device.name
        self._close_modal()
        self.status_message = f"Connecting to {name}..."

        def _cb(success: bool, msg: str):
            self.status_message = msg
            if success:
                # If audio output is set to bluetooth, route to it
                if self.app.bluetooth.audio_output_mode == "bluetooth":
                    self.app.player.set_audio_output("bluetooth", mac)
            self._refresh_device_list()

        self.app.bluetooth.connect_device_async(mac, callback=_cb)

    def _modal_action_disconnect(self):
        if not self.selected_device:
            return
        mac = self.selected_device.mac
        self._close_modal()
        self.status_message = "Disconnecting..."

        def _cb(success: bool, msg: str):
            self.status_message = msg
            self._refresh_device_list()

        self.app.bluetooth.disconnect_device_async(mac, callback=_cb)

    def _modal_action_unpair(self):
        if not self.selected_device:
            return
        mac = self.selected_device.mac
        self._close_modal()
        self.status_message = f"Unpairing {mac}..."

        def _cb(success: bool, msg: str):
            self.status_message = msg
            self._refresh_device_list()

        self.app.bluetooth.remove_device_async(mac, callback=_cb)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.show_device_modal:
            if self.selected_device and self.selected_device.connected:
                if self.btn_modal_disconnect.handle_event(event):
                    return True
            else:
                if self.btn_modal_connect.handle_event(event):
                    return True

            if self.selected_device and self.selected_device.paired:
                if self.btn_modal_unpair.handle_event(event):
                    return True

            if self.btn_modal_cancel.handle_event(event):
                return True
            return True

        # Header controls
        if self.btn_output_jack.handle_event(event):
            return True
        if self.btn_output_bt.handle_event(event):
            return True
        if self.btn_scan.handle_event(event):
            return True

        # Device list
        if self.list_view.handle_event(event):
            return True

        return False

    def update(self):
        # Update output button states
        cur_mode = self.app.bluetooth.audio_output_mode
        self.btn_output_jack.bg_color = COLOR_ACCENT if cur_mode == "jack" else COLOR_SURFACE_LIGHT
        self.btn_output_bt.bg_color = COLOR_ACCENT if cur_mode == "bluetooth" else COLOR_SURFACE_LIGHT

    def draw(self, surface: pygame.Surface):
        # 1. Output mode buttons & scan
        self.btn_output_jack.draw(surface)
        self.btn_output_bt.draw(surface)
        self.btn_scan.draw(surface)

        # 2. Status message line (Row 2)
        status_y = CONTENT_Y + 44
        status_text = self.status_message
        if self.app.bluetooth.is_scanning:
            status_text = "Scanning for devices..."

        font_sm = Theme.get_font(11)
        stat_surf = font_sm.render(status_text, True, COLOR_TEXT_SECONDARY)
        surface.blit(stat_surf, (12, status_y))

        # Output indicator badge on right
        output_mode_str = "Output: 3.5mm Jack" if cur_mode := self.app.bluetooth.audio_output_mode == "jack" else "Output: Bluetooth"
        out_badge = font_sm.render(output_mode_str, True, COLOR_INFO if cur_mode else COLOR_SUCCESS)
        surface.blit(out_badge, (SCREEN_WIDTH - out_badge.get_width() - 12, status_y))

        # Thin divider line
        pygame.draw.line(surface, COLOR_SURFACE_BORDER, (10, CONTENT_Y + 62), (SCREEN_WIDTH - 10, CONTENT_Y + 62), 1)

        # 3. Device list
        if not self.devices and not self.app.bluetooth.is_scanning:
            empty_font = Theme.get_font(12)
            empty_surf = empty_font.render("No Bluetooth devices found. Tap 'Scan' above.", True, COLOR_TEXT_MUTED)
            surface.blit(empty_surf, (SCREEN_WIDTH // 2 - empty_surf.get_width() // 2, CONTENT_Y + 110))
        else:
            self.list_view.draw(surface)

        # 4. Device Modal Dialog
        if self.show_device_modal and self.selected_device:
            self._draw_device_modal(surface)

    def _draw_device_modal(self, surface: pygame.Surface):
        """Render popup modal when a device is tapped."""
        # Backdrop dim
        overlay = pygame.Surface((SCREEN_WIDTH, CONTENT_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, CONTENT_Y))

        # Dialog Box
        dialog_rect = pygame.Rect(40, CONTENT_Y + 30, SCREEN_WIDTH - 80, 150)
        pygame.draw.rect(surface, COLOR_SURFACE, dialog_rect, border_radius=6)
        pygame.draw.rect(surface, COLOR_SURFACE_BORDER, dialog_rect, width=1, border_radius=6)

        # Dialog Title & Details
        font_lg = Theme.get_font(13, bold=True)
        title_surf = font_lg.render(self.selected_device.name[:28], True, COLOR_TEXT_PRIMARY)
        surface.blit(title_surf, (dialog_rect.x + 16, dialog_rect.y + 14))

        font_sm = Theme.get_font(11)
        mac_surf = font_sm.render(f"MAC: {self.selected_device.mac}", True, COLOR_TEXT_SECONDARY)
        surface.blit(mac_surf, (dialog_rect.x + 16, dialog_rect.y + 36))

        st_str = "Status: Connected" if self.selected_device.connected else ("Status: Paired" if self.selected_device.paired else "Status: Available")
        st_color = COLOR_SUCCESS if self.selected_device.connected else (COLOR_INFO if self.selected_device.paired else COLOR_TEXT_MUTED)
        st_surf = font_sm.render(st_str, True, st_color)
        surface.blit(st_surf, (dialog_rect.x + 16, dialog_rect.y + 56))

        # Buttons
        if self.selected_device.connected:
            self.btn_modal_disconnect.draw(surface)
        else:
            self.btn_modal_connect.draw(surface)

        if self.selected_device.paired:
            self.btn_modal_unpair.draw(surface)

        self.btn_modal_cancel.draw(surface)
