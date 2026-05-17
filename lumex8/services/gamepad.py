"""Gamepad input listener — runs in a background QThread."""

from PyQt6.QtCore import QThread, pyqtSignal

try:
    import pygame
    HAS_GAMEPAD_LIB = True
except ImportError:
    HAS_GAMEPAD_LIB = False


class GamepadWorker(QThread):
    """Background thread that polls a gamepad via pygame.joystick.

    Emits ``btn_pressed`` with button names (A, B, X, Y, LB, RB,
    SELECT, START, GUIDE, L3, R3) and ``dpad`` with directions
    (UP, DOWN, LEFT, RIGHT).
    """

    btn_pressed = pyqtSignal(str)
    dpad = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._running = True

    def stop(self) -> None:
        """Signal the thread to exit its main loop."""
        self._running = False

    def run(self) -> None:
        if not HAS_GAMEPAD_LIB:
            return

        try:
            pygame.init()
            pygame.joystick.init()
        except Exception as e:
            print(f"Gamepad init error: {e}")
            return

        if pygame.joystick.get_count() == 0:
            print("No gamepad detected.")
            return

        try:
            joystick = pygame.joystick.Joystick(0)
            joystick.init()
            print(f"Gamepad connected: {joystick.get_name()}")
        except Exception:
            return

        while self._running:
            for event in pygame.event.get():

                # --- BUTTONS ---
                if event.type == pygame.JOYBUTTONDOWN:
                    b = event.button
                    btn_name = f"BTN_{b}"  # fallback

                    if b == 0:
                        btn_name = "A"
                    elif b == 1:
                        btn_name = "B"
                    elif b == 2:
                        btn_name = "X"
                    elif b == 3:
                        btn_name = "Y"
                    elif b == 4:
                        btn_name = "LB"
                    elif b == 5:
                        btn_name = "RB"
                    elif b == 6:
                        btn_name = "SELECT"
                    elif b == 7:
                        btn_name = "START"
                    elif b == 8:
                        btn_name = "GUIDE"
                    elif b == 9:
                        btn_name = "L3"
                    elif b == 10:
                        btn_name = "R3"

                    self.btn_pressed.emit(btn_name)

                # --- D-PAD (HAT) ---
                elif event.type == pygame.JOYHATMOTION:
                    x, y = event.value
                    if x == -1:
                        self.dpad.emit("LEFT")
                    elif x == 1:
                        self.dpad.emit("RIGHT")
                    if y == 1:
                        self.dpad.emit("UP")
                    elif y == -1:
                        self.dpad.emit("DOWN")

            self.msleep(10)
