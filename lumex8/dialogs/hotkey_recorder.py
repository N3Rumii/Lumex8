"""Hotkey Recorder — QPushButton that records keyboard hotkey combos.

Uses pynput-compatible key naming (e.g. <cmd>+p, <ctrl>+<shift>+a).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QPushButton


class HotkeyRecorder(QPushButton):
    """A push-button that records keyboard hotkeys.

    When checked (depressed), the widget grabs keyboard input. On a
    non-modifier key press, it builds a pynput-compatible hotkey string
    and displays it. Escape cancels.

    Provides ``set_hotkey()`` and ``current_hotkey()`` for integration
    with the settings dialog.
    """

    def __init__(self, text: str = "Record Hotkey", parent=None) -> None:
        super().__init__(text, parent)
        self.setCheckable(True)
        self._hotkey: str = ""
        self.clicked.connect(self._toggle_mode)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_hotkey(self, hotkey: str) -> None:
        """Display a pre-configured hotkey string."""
        self._hotkey = hotkey
        self.setText(hotkey)

    def current_hotkey(self) -> str:
        """Return the recorded hotkey string."""
        return self._hotkey

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _toggle_mode(self, checked: bool) -> None:
        if checked:
            self.setText("Press Combo... (Esc to cancel)")
            self.grabKeyboard()
        else:
            self.releaseKeyboard()
            self.setText(self._hotkey)

    def keyPressEvent(self, event) -> None:
        if not self.isChecked():
            super().keyPressEvent(event)
            return

        key = event.key()

        if key == Qt.Key.Key_Escape:
            self.setChecked(False)
            self.releaseKeyboard()
            self.setText(self._hotkey)
            return

        # Ignore pure modifier presses
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return

        parts = []
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("<ctrl>")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("<shift>")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("<alt>")
        if mods & Qt.KeyboardModifier.MetaModifier:
            parts.append("<cmd>")

        txt = QKeySequence(key).toString().lower()

        special_map = {
            Qt.Key.Key_Space: "<space>",
            Qt.Key.Key_Return: "<enter>",
            Qt.Key.Key_Enter: "<enter>",
            Qt.Key.Key_Tab: "<tab>",
            Qt.Key.Key_Backspace: "<backspace>",
            Qt.Key.Key_Delete: "<delete>",
            Qt.Key.Key_Left: "<left>",
            Qt.Key.Key_Right: "<right>",
            Qt.Key.Key_Up: "<up>",
            Qt.Key.Key_Down: "<down>",
            Qt.Key.Key_Home: "<home>",
            Qt.Key.Key_End: "<end>",
            Qt.Key.Key_PageUp: "<pageup>",
            Qt.Key.Key_PageDown: "<pagedown>",
            Qt.Key.Key_Insert: "<insert>",
        }

        if key in special_map:
            txt = special_map[key]
        elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F12:
            txt = f"<{txt}>"

        parts.append(txt)
        final = "+".join(parts)

        self._hotkey = final
        self.setText(final)
        self.setChecked(False)
        self.releaseKeyboard()
