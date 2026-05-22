"""Floating Start Button — persistent overlay button on the desktop."""

import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont, QFontMetrics
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QApplication


class FloatingStartButton(QWidget):
    """An always-on-top overlay button docked to a screen edge.

    Toggles the main launcher window on click. Supports auto-hide,
    text/image icons, and configurable color/position.

    On Wayland we use a plain ``Window`` (not ``Popup``) because
    Popups require a visible transient-parent that has received input.
    ``setGeometry`` before ``show()`` gives the compositor a size hint
    even if it ultimately decides placement.
    """

    def __init__(self, parent_window) -> None:
        super().__init__()
        self.parent_window = parent_window

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.btn = QPushButton()
        self.btn.clicked.connect(self.safe_toggle)
        self.layout.addWidget(self.btn)

        self.keep_alive = QTimer(self)
        self.keep_alive.timeout.connect(self.ensure_visible)
        self.keep_alive.start(2000)

        self.apply_settings()

    def ensure_visible(self) -> None:
        settings = self.parent_window.config.get("start_btn", {})
        if settings.get("visible", True) and not self.parent_window.isVisible():
            if not self.isVisible():
                self.show()
            self.raise_()

    def safe_toggle(self) -> None:
        self.parent_window.toggle_visibility()

    def apply_settings(self) -> None:
        settings = self.parent_window.config.get("start_btn", {})

        if self.parent_window.isVisible() or not settings.get("visible", True):
            self.hide()
            return

        h = settings.get("size", 60)
        pos = settings.get("position", "Bottom Left")
        icon_type = settings.get("icon_type", "text")
        icon_val = settings.get("icon_val", "\u2756")
        autohide = settings.get("autohide", False)

        w = h
        if icon_type == "text":
            fm = QFontMetrics(QFont("Segoe UI", int(h * 0.5)))
            w = max(h, fm.horizontalAdvance(icon_val) + 30)

        self.setFixedSize(w, h)
        self.btn.setFixedSize(w, h)

        geo = QApplication.primaryScreen().geometry()
        if "Left" in pos:
            x = 0
        elif "Right" in pos:
            x = geo.width() - w
        else:
            x = (geo.width() - w) // 2
        y = 0 if "Top" in pos else geo.height() - h

        # setGeometry + resize as a compositor size-hint, then show.
        self.resize(w, h)
        self.move(x, y)
        self.show()
        self.raise_()

        r = "10px"
        corners = ""
        if "Bottom" in pos:
            if "Left" in pos:
                corners = f"border-top-right-radius: {r};"
            elif "Right" in pos:
                corners = f"border-top-left-radius: {r};"
            elif "Center" in pos:
                corners = f"border-top-left-radius: {r}; border-top-right-radius: {r};"
        else:
            if "Left" in pos:
                corners = f"border-bottom-right-radius: {r};"
            elif "Right" in pos:
                corners = f"border-bottom-left-radius: {r};"
            elif "Center" in pos:
                corners = f"border-bottom-left-radius: {r}; border-bottom-right-radius: {r};"

        self.btn.setIcon(QIcon())
        self.btn.setText("")

        base_extra = ""
        hover_extra = ""

        if icon_type == "image" and os.path.exists(icon_val):
            img_rule = f"border-image: url({icon_val.replace('', '/')}) 0 0 0 0 stretch stretch; padding: 10px;"
            if autohide:
                base_extra = "border-image: none;"
                hover_extra = img_rule
            else:
                base_extra = img_rule
                hover_extra = img_rule
        else:
            self.btn.setText(icon_val)
            base_extra = f"font-size: {int(h * 0.5)}px;"
            hover_extra = base_extra

        std_col = settings.get("color", "rgba(255,255,255,0.2)")
        nbg = "transparent" if autohide else std_col
        ncol = "transparent" if autohide else "white"

        self.btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {nbg}; color: {ncol};
                border: none; {corners} {base_extra}
            }}
            QPushButton:hover {{
                background-color: {std_col}; color: white; {hover_extra}
            }}
            """
        )
