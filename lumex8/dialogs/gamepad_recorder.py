"""Gamepad Recorder — QPushButton that records a gamepad button name."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QPushButton


class GamepadRecorder(QPushButton):
    """A push-button that records a gamepad button when toggled.

    While checked the button connects to the main window's gamepad thread
    ``btn_pressed`` signal.  The first button press finalises the recording
    and unchecks the button.

    Signals
    -------
    button_recorded(button_name: str)
        Emitted when a gamepad button has been captured.
    """

    button_recorded = pyqtSignal(str)

    def __init__(self, main_window, text: str = "Record Button", parent=None) -> None:
        super().__init__(text, parent)
        self._main_window = main_window
        self._recording: bool = False

        self.setCheckable(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.toggled.connect(self._on_toggled)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def set_button(self, button_name: str) -> None:
        """Display an already-configured button name."""
        self.setText(button_name)

    def current_button(self) -> str:
        """Return the button name currently shown on the button."""
        txt = self.text()
        return "" if txt == self._idle_text() else txt

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_toggled(self, checked: bool) -> None:
        if checked:
            self._start_recording()
        else:
            self._stop_recording()

    def _on_btn_pressed(self, button_name: str) -> None:
        """Slot connected to ``gamepad_thread.btn_pressed``."""
        if not self._recording:
            return
        self.setText(button_name)
        self.button_recorded.emit(button_name)
        self.setChecked(False)  # triggers _stop_recording

    # ------------------------------------------------------------------
    # Recording lifecycle
    # ------------------------------------------------------------------
    def _start_recording(self) -> None:
        self._recording = True
        self.setText("Press a gamepad button…")

        gamepad_thread = getattr(self._main_window, "gamepad_thread", None)
        if gamepad_thread is not None:
            try:
                gamepad_thread.btn_pressed.connect(self._on_btn_pressed)
            except AttributeError:
                pass  # signal may not exist — just ignore

    def _stop_recording(self) -> None:
        self._recording = False

        gamepad_thread = getattr(self._main_window, "gamepad_thread", None)
        if gamepad_thread is not None:
            try:
                gamepad_thread.btn_pressed.disconnect(self._on_btn_pressed)
            except (AttributeError, TypeError):
                pass  # not connected or doesn't exist

        # If the button text still says "Press a gamepad button…" the user
        # toggled off without pressing anything, so reset to idle.
        if self.text() == "Press a gamepad button…":
            self.setText(self._idle_text())

    def cancel_recording(self) -> None:
        """Cancel without emitting a signal."""
        self._recording = False
        self._stop_recording()
        self.setText(self._idle_text())
        self.setChecked(False)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _idle_text(self) -> str:
        return "Record Button"
