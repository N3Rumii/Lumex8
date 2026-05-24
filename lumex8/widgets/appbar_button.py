"""Flat AppBar button — SVG icon + text, with accent-color tinting."""

import os

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QIcon, QFont, QPixmap, QPainter
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout


class AppBarButton(QWidget):
    """A flat rectangular button with tinted SVG icon and label."""

    ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icons")

    def __init__(self, text, icon_name, callback, parent_bar) -> None:
        super().__init__(parent_bar)
        self._callback = callback
        self._parent_bar = parent_bar
        self._hovered = False
        self._pressed = False
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        accent_hex = parent_bar.parent_window.config["settings"].get(
            "appbar_accent_color", "#FFFFFF"
        )
        accent_col = QColor(accent_hex)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(2)

        # Icon label
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = self._make_tinted_icon(icon_name, accent_col)
        if not icon.isNull():
            self.icon_label.setPixmap(icon.pixmap(28, 28))
        layout.addWidget(self.icon_label)

        # Text label
        self.text_label = QLabel(text)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setFont(QFont("Segoe UI", 9))
        self.text_label.setStyleSheet(f"color: {accent_hex}; background: transparent;")
        layout.addWidget(self.text_label)

        # Read show_labels from config (default True)
        show_labels = parent_bar.parent_window.config["settings"].get(
            "appbar_show_labels", True
        )
        self.text_label.setVisible(show_labels)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(90)

        self._accent_hex = accent_hex
        self._update_style()

    def _update_style(self) -> None:
        if self._pressed:
            bg = "rgba(255, 255, 255, 0.2)"
        elif self._hovered:
            bg = "rgba(255, 255, 255, 0.1)"
        else:
            bg = "transparent"
        self.setStyleSheet(f"""
            AppBarButton {{
                background-color: {bg};
                border: none;
            }}
        """)

    def _make_tinted_icon(self, icon_name: str, tint: QColor) -> QIcon:
        # Try active icon theme first, fall back to built-in icons
        path = ""
        try:
            theme_path = self._parent_bar.parent_window.get_theme_icon_path()
            candidate = os.path.join(theme_path, f"{icon_name}.svg")
            if os.path.exists(candidate):
                path = candidate
        except Exception:
            pass
        if not path:
            path = os.path.join(self.ICONS_DIR, f"{icon_name}.svg")
        if not os.path.exists(path):
            return QIcon()

        pix = QPixmap(path)
        if pix.isNull():
            return QIcon()

        # Respect the tint toggle — skip tint for colorful icon packs
        try:
            want_tint = self._parent_bar.parent_window.config["settings"].get(
                "appbar_tint_icons", True
            )
        except Exception:
            want_tint = True
        if not want_tint:
            return QIcon(pix)

        # Tint the SVG using SourceIn composition
        tinted = QPixmap(pix.size())
        tinted.fill(Qt.GlobalColor.transparent)
        p = QPainter(tinted)
        p.drawPixmap(0, 0, pix)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(tinted.rect(), tint)
        p.end()

        return QIcon(tinted)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._update_style()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._pressed = False
        self._update_style()
        if event.button() == Qt.MouseButton.LeftButton:
            if self.rect().contains(event.position().toPoint()):
                if self._callback:
                    self._callback()
        super().mouseReleaseEvent(event)
