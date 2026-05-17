"""Kinetic/inertia scroll area for horizontal group scrolling."""

from PyQt6.QtCore import QPropertyAnimation, Qt, QEasingCurve
from PyQt6.QtWidgets import QScrollArea, QFrame


class KineticScrollArea(QScrollArea):
    """A horizontal scroll area with momentum-based inertia scrolling."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Force transparency on the viewport
        self.viewport().setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Drag variables
        self._is_dragging = False
        self._start_pos = None
        self._start_scroll_val = 0
        self._last_mouse_x = 0
        self._velocity = 0

        # Inertia animation
        self.anim = QPropertyAnimation(self.horizontalScrollBar(), b"value")
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)

        self.setStyleSheet(
            """
            QScrollArea { background: transparent; border: none; }
            QScrollBar:horizontal {
                height: 12px; background: transparent; margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(255, 255, 255, 0.3);
                min-width: 20px; border-radius: 6px;
            }
            QScrollBar::handle:horizontal:hover {
                background: rgba(255, 255, 255, 0.5);
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal { width: 0px; }
            """
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._start_pos = event.pos()
            self._start_scroll_val = self.horizontalScrollBar().value()
            self._last_mouse_x = event.pos().x()
            self._velocity = 0
            self.anim.stop()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._is_dragging:
            delta = event.pos().x() - self._start_pos.x()
            self.horizontalScrollBar().setValue(self._start_scroll_val - delta)

            current_x = event.pos().x()
            self._velocity = current_x - self._last_mouse_x
            self._last_mouse_x = current_x
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._is_dragging:
            self._is_dragging = False
            if abs(self._velocity) > 2:
                current_val = self.horizontalScrollBar().value()
                end_val = current_val - (self._velocity * 30)
                end_val = max(
                    self.horizontalScrollBar().minimum(),
                    min(end_val, self.horizontalScrollBar().maximum()),
                )
                self.anim.setDuration(600)
                self.anim.setStartValue(current_val)
                self.anim.setEndValue(end_val)
                self.anim.start()
        super().mouseReleaseEvent(event)
