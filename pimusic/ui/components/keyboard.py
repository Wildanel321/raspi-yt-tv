"""
Pi Music - Virtual On-Screen Touchscreen Keyboard
Designed specifically for 480x320 resistive displays with high-contrast,
large finger targets, shift, numbers/symbols modes, and real-time input preview.
"""

from typing import Callable, List, Optional
import pygame

from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_BG, COLOR_SURFACE,
    COLOR_SURFACE_LIGHT, COLOR_SURFACE_BORDER, COLOR_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED
)
from pimusic.ui.theme import Theme
from pimusic.ui.components.button import Button

class VirtualKeyboard:
    """Full-screen or overlay virtual keyboard for touchscreen text entry."""

    LAYOUT_LOWER = [
        ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
        ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
        ["SHIFT", "z", "x", "c", "v", "b", "n", "m", "BACKSPACE"],
        ["123", "SPACE", "CLEAR", "DONE"]
    ]

    LAYOUT_UPPER = [
        ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
        ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
        ["SHIFT", "Z", "X", "C", "V", "B", "N", "M", "BACKSPACE"],
        ["123", "SPACE", "CLEAR", "DONE"]
    ]

    LAYOUT_SYMBOLS = [
        ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
        ["-", "/", ":", ";", "(", ")", "$", "&", "@", "."],
        ["ABC", "?", "!", "\"", "'", ",", "_", "+", "BACKSPACE"],
        ["ABC", "SPACE", "CLEAR", "DONE"]
    ]

    def __init__(
        self,
        title: str = "Search YouTube",
        initial_text: str = "",
        on_submit: Optional[Callable[[str], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
        is_password: bool = False
    ):
        self.title = title
        self.text = initial_text
        self.on_submit = on_submit
        self.on_cancel = on_cancel
        self.is_password = is_password

        self.mode = "lower"  # "lower", "upper", "symbols"
        self.is_active = True
        self.cursor_blink = 0.0

        # Construct Key Buttons
        self._buttons: List[Button] = []
        self._cancel_button = Button(
            pygame.Rect(8, 8, 48, 32),
            text="<",
            font_size=18,
            callback=self._handle_cancel
        )
        self._rebuild_keys()

    def _handle_cancel(self):
        self.is_active = False
        if self.on_cancel:
            self.on_cancel()

    def _rebuild_keys(self):
        """Constructs buttons for the current keyboard mode."""
        self._buttons.clear()

        if self.mode == "upper":
            layout = self.LAYOUT_UPPER
        elif self.mode == "symbols":
            layout = self.LAYOUT_SYMBOLS
        else:
            layout = self.LAYOUT_LOWER

        # Geometry configuration for 480x320 screen
        # Top 80px is reserved for Title + Input preview bar
        start_y = 86
        row_h = 36
        gap = 4
        total_w = SCREEN_WIDTH - 16  # 464px available width

        for r_idx, row in enumerate(layout):
            y = start_y + r_idx * (row_h + gap)
            col_count = len(row)

            # Special layout for bottom rows
            if r_idx == 3:  # Bottom row: ["123", "SPACE", "CLEAR", "DONE"]
                btn_w_123 = 60
                btn_w_clear = 64
                btn_w_done = 84
                btn_w_space = total_w - btn_w_123 - btn_w_clear - btn_w_done - (gap * 3)

                x = 8
                # 123 / ABC
                mode_label = "ABC" if self.mode == "symbols" else "123"
                self._buttons.append(
                    Button(pygame.Rect(x, y, btn_w_123, row_h), text=mode_label, font_size=13,
                           callback=lambda: self._toggle_symbols())
                )
                x += btn_w_123 + gap

                # SPACE
                self._buttons.append(
                    Button(pygame.Rect(x, y, btn_w_space, row_h), text="Space", font_size=13,
                           callback=lambda: self._insert_char(" "))
                )
                x += btn_w_space + gap

                # CLEAR
                self._buttons.append(
                    Button(pygame.Rect(x, y, btn_w_clear, row_h), text="Clear", font_size=12,
                           callback=lambda: self._clear_text())
                )
                x += btn_w_clear + gap

                # DONE / SEARCH
                self._buttons.append(
                    Button(pygame.Rect(x, y, btn_w_done, row_h), text="Search", font_size=13,
                           bg_color=COLOR_ACCENT, hover_color=(255, 60, 60),
                           callback=lambda: self._submit())
                )
                continue

            elif r_idx == 2:  # Shift, letters, backspace
                shift_w = 54
                bksp_w = 54
                letter_w = int((total_w - shift_w - bksp_w - (col_count - 1) * gap) / (col_count - 2))

                x = 8
                # Shift or mode switch
                shift_label = "ABC" if self.mode == "symbols" else ("^" if self.mode == "upper" else "^")
                self._buttons.append(
                    Button(pygame.Rect(x, y, shift_w, row_h), text=shift_label, font_size=14,
                           is_toggle=True,
                           bg_color=COLOR_SURFACE_LIGHT if self.mode == "upper" else COLOR_SURFACE,
                           callback=lambda: self._toggle_shift())
                )
                x += shift_w + gap

                # Middle letters
                for key in row[1:-1]:
                    char = key
                    self._buttons.append(
                        Button(pygame.Rect(x, y, letter_w, row_h), text=char, font_size=15,
                               callback=lambda c=char: self._insert_char(c))
                    )
                    x += letter_w + gap

                # Backspace
                self._buttons.append(
                    Button(pygame.Rect(x, y, bksp_w, row_h), icon="backspace", icon_size=16,
                           callback=lambda: self._backspace())
                )
                continue

            # Default row (Row 0 and 1)
            key_w = int((total_w - (col_count - 1) * gap) / col_count)
            # Center row slightly if fewer keys (e.g. row 1 has 9 keys)
            row_total_w = col_count * key_w + (col_count - 1) * gap
            start_x = 8 + (total_w - row_total_w) // 2

            for c_idx, key in enumerate(row):
                x = start_x + c_idx * (key_w + gap)
                char = key
                self._buttons.append(
                    Button(pygame.Rect(x, y, key_w, row_h), text=char, font_size=15,
                           callback=lambda c=char: self._insert_char(c))
                )

    def _insert_char(self, char: str):
        self.text += char
        if self.mode == "upper":
            self.mode = "lower"
            self._rebuild_keys()

    def _backspace(self):
        if self.text:
            self.text = self.text[:-1]

    def _clear_text(self):
        self.text = ""

    def _toggle_shift(self):
        self.mode = "upper" if self.mode != "upper" else "lower"
        self._rebuild_keys()

    def _toggle_symbols(self):
        self.mode = "symbols" if self.mode != "symbols" else "lower"
        self._rebuild_keys()

    def _submit(self):
        self.is_active = False
        if self.on_submit:
            self.on_submit(self.text)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Processes keyboard input touches."""
        if not self.is_active:
            return False

        if self._cancel_button.handle_event(event):
            return True

        for btn in self._buttons:
            if btn.handle_event(event):
                return True

        # Also support physical keyboard for testing / USB keyboard on Pi
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self._submit()
                return True
            elif event.key == pygame.K_BACKSPACE:
                self._backspace()
                return True
            elif event.key == pygame.K_ESCAPE:
                self._handle_cancel()
                return True
            elif event.unicode and event.unicode.isprintable():
                self._insert_char(event.unicode)
                return True

        return True  # Consume all events while keyboard modal is up

    def draw(self, surface: pygame.Surface):
        """Draws virtual keyboard modal dialog."""
        if not self.is_active:
            return

        # Semi-transparent overlay backdrop
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.fill(COLOR_BG)
        surface.blit(overlay, (0, 0))

        # Title bar & Cancel button
        self._cancel_button.draw(surface)
        title_font = Theme.get_font(14, bold=True)
        title_surf = title_font.render(self.title, True, COLOR_TEXT_SECONDARY)
        surface.blit(title_surf, (64, 16))

        # Text Input Box Preview
        input_rect = pygame.Rect(8, 44, SCREEN_WIDTH - 16, 36)
        Theme.draw_rounded_rect(
            surface,
            input_rect,
            COLOR_SURFACE,
            radius=6,
            border_color=COLOR_ACCENT,
            border_width=1
        )

        display_text = ("*" * len(self.text)) if self.is_password else self.text
        text_font = Theme.get_font(16)
        rendered_text = text_font.render(display_text, True, COLOR_TEXT_PRIMARY)

        # Handle text clipping if too long
        max_tw = input_rect.width - 24
        if rendered_text.get_width() > max_tw:
            clip_x = rendered_text.get_width() - max_tw
            surface.blit(rendered_text, (input_rect.left + 12, input_rect.top + 8),
                         area=pygame.Rect(clip_x, 0, max_tw, rendered_text.get_height()))
            cursor_x = input_rect.left + 12 + max_tw
        else:
            surface.blit(rendered_text, (input_rect.left + 12, input_rect.top + 8))
            cursor_x = input_rect.left + 12 + rendered_text.get_width()

        # Blinking cursor
        self.cursor_blink = (self.cursor_blink + 0.05) % 1.0
        if self.cursor_blink < 0.5:
            pygame.draw.line(surface, COLOR_ACCENT, (cursor_x + 2, input_rect.top + 7),
                             (cursor_x + 2, input_rect.bottom - 7), 2)

        # Draw all keys
        for btn in self._buttons:
            btn.draw(surface)
