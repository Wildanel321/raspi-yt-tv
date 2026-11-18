"""
Pi Music - Settings & System Management View
Displays system statistics, hardware metrics, audio device details,
and safe power controls (reboot/shutdown) with confirmation.
"""

from typing import TYPE_CHECKING, Optional
import pygame

from config import (
    CONTENT_Y, CONTENT_HEIGHT, SCREEN_WIDTH, COLOR_SURFACE,
    COLOR_SURFACE_LIGHT, COLOR_SURFACE_BORDER, COLOR_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER, APP_VERSION
)
from pimusic.core.system_info import SystemInfo
from pimusic.ui.theme import Theme
from pimusic.ui.components.button import Button
from pimusic.ui.views.base_view import BaseView

if TYPE_CHECKING:
    from pimusic.ui.app import App

class SettingsView(BaseView):
    """System health monitoring and power management view."""

    def __init__(self, app: "App"):
        super().__init__(app)

        self.confirm_action: Optional[str] = None  # "reboot" or "shutdown"

        # Action Buttons
        btn_y = CONTENT_Y + 158
        self.btn_reboot = Button(
            pygame.Rect(20, btn_y, 130, 42),
            text="Reboot Pi",
            font_size=13,
            bg_color=COLOR_SURFACE_LIGHT,
            callback=lambda: self._prompt_confirm("reboot")
        )

        self.btn_shutdown = Button(
            pygame.Rect(165, btn_y, 140, 42),
            text="Shutdown Pi",
            font_size=13,
            bg_color=(80, 20, 20),
            hover_color=(120, 30, 30),
            callback=lambda: self._prompt_confirm("shutdown")
        )

        self.btn_exit_app = Button(
            pygame.Rect(320, btn_y, 140, 42),
            text="Exit Player",
            font_size=13,
            bg_color=COLOR_SURFACE_LIGHT,
            callback=self._exit_app
        )

        # Bluetooth Quick Access Button
        self.btn_manage_bt = Button(
            pygame.Rect(20, CONTENT_Y + 114, SCREEN_WIDTH - 40, 34),
            text="Manage Bluetooth & Audio Output",
            icon="bluetooth",
            icon_size=14,
            font_size=12,
            bg_color=COLOR_SURFACE_LIGHT,
            callback=lambda: self.app.switch_tab("bluetooth")
        )

        # Dialog buttons
        self.btn_dialog_yes = Button(
            pygame.Rect(110, CONTENT_Y + 140, 110, 38),
            text="Yes, Proceed",
            font_size=12,
            bg_color=COLOR_DANGER,
            callback=self._execute_confirmed_action
        )
        self.btn_dialog_no = Button(
            pygame.Rect(260, CONTENT_Y + 140, 110, 38),
            text="Cancel",
            font_size=12,
            bg_color=COLOR_SURFACE_LIGHT,
            callback=lambda: setattr(self, "confirm_action", None)
        )

    def _prompt_confirm(self, action: str):
        self.confirm_action = action

    def _execute_confirmed_action(self):
        act = self.confirm_action
        self.confirm_action = None
        if act == "reboot":
            self.app.shutdown()
            SystemInfo.reboot_system()
        elif act == "shutdown":
            self.app.shutdown()
            SystemInfo.shutdown_system()

    def _exit_app(self):
        self.app.is_running = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.confirm_action:
            if self.btn_dialog_yes.handle_event(event):
                return True
            if self.btn_dialog_no.handle_event(event):
                return True
            return True

        if self.btn_manage_bt.handle_event(event):
            return True
        if self.btn_reboot.handle_event(event):
            return True
        if self.btn_shutdown.handle_event(event):
            return True
        if self.btn_exit_app.handle_event(event):
            return True
        return False

    def update(self):
        pass

    def draw(self, surface: pygame.Surface):
        # 1. System Info Card (Top 96px)
        info_rect = pygame.Rect(10, CONTENT_Y + 6, SCREEN_WIDTH - 20, 98)
        Theme.draw_rounded_rect(surface, info_rect, COLOR_SURFACE, radius=8,
                                border_color=COLOR_SURFACE_BORDER, border_width=1)

        # Title
        t_surf = Theme.get_font(13, bold=True).render(f"System Health  •  Pi Music v{APP_VERSION}", True, COLOR_TEXT_PRIMARY)
        surface.blit(t_surf, (info_rect.left + 16, info_rect.top + 8))

        # Metrics
        temp = SystemInfo.get_cpu_temp()
        temp_str = f"{temp:.1f} °C" if temp else "N/A"
        used_mb, total_mb, ram_pct = SystemInfo.get_ram_usage()

        bt_dev = self.app.bluetooth.get_connected_device()
        out_mode = self.app.bluetooth.audio_output_mode
        if out_mode == "bluetooth":
            audio_out_str = f"Bluetooth ({bt_dev.name if bt_dev else 'Connecting...'})"
            audio_col = COLOR_SUCCESS if bt_dev else COLOR_WARNING
        elif out_mode == "hdmi":
            audio_out_str = "HDMI Audio (vc4-hdmi)"
            audio_col = COLOR_SUCCESS
        else:
            audio_out_str = "3.5mm Analog Jack (ALSA)"
            audio_col = COLOR_ACCENT

        web_url = self.app.web_server.get_access_url() if self.app.web_server else "Disabled"

        font_lbl = Theme.get_font(11)
        font_val = Theme.get_font(11, bold=True)

        rows = [
            ("CPU Temperature:", temp_str, COLOR_WARNING if (temp and temp > 70) else COLOR_SUCCESS),
            ("RAM Usage (Pi 3):", f"{used_mb} MB / {total_mb} MB ({ram_pct}%)", COLOR_TEXT_PRIMARY),
            ("Active Audio Output:", audio_out_str, audio_col),
            ("Web Remote URL:", web_url, COLOR_SUCCESS if self.app.web_server else COLOR_TEXT_MUTED),
        ]

        for i, (lbl, val, col) in enumerate(rows):
            y = info_rect.top + 26 + (i * 17)
            lbl_surf = font_lbl.render(lbl, True, COLOR_TEXT_SECONDARY)
            val_surf = font_val.render(val, True, col)
            surface.blit(lbl_surf, (info_rect.left + 16, y))
            surface.blit(val_surf, (info_rect.left + 160, y))

        # 2. Bluetooth quick access button
        self.btn_manage_bt.draw(surface)

        # 3. Power Management Buttons
        self.btn_reboot.draw(surface)
        self.btn_shutdown.draw(surface)
        self.btn_exit_app.draw(surface)

        # 3. Confirmation Dialog
        if self.confirm_action:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            surface.blit(overlay, (0, 0))

            dialog_rect = pygame.Rect(60, CONTENT_Y + 50, 360, 140)
            Theme.draw_rounded_rect(surface, dialog_rect, COLOR_SURFACE, radius=10,
                                    border_color=COLOR_DANGER, border_width=1)

            action_text = "Reboot Raspberry Pi?" if self.confirm_action == "reboot" else "Shutdown Raspberry Pi?"
            msg_surf = Theme.get_font(15, bold=True).render(action_text, True, COLOR_TEXT_PRIMARY)
            surface.blit(msg_surf, (dialog_rect.centerx - msg_surf.get_width() // 2, dialog_rect.top + 25))

            hint_surf = Theme.get_font(11).render("Playback will stop and system will power off.", True, COLOR_TEXT_MUTED)
            surface.blit(hint_surf, (dialog_rect.centerx - hint_surf.get_width() // 2, dialog_rect.top + 52))

            self.btn_dialog_yes.draw(surface)
            self.btn_dialog_no.draw(surface)
