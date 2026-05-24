"""App Bar — bottom-sliding contextual menu for tile actions."""

from PyQt6.QtCore import QPropertyAnimation, Qt, QRect, QEasingCurve
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout

from lumex8.widgets.appbar_button import AppBarButton


class AppBar(QWidget):
    """A bottom-sliding contextual action bar for a selected tile.

    Provides Unpin, Resize, Edit, Color, and Icon actions.
    Matches the Windows 8 charms-bar metaphor.
    """

    def __init__(self, parent_window) -> None:
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.target_tile = None

        self.hide()
        self.setFixedHeight(70)
        # Qt6 requires WA_StyledBackground for stylesheet backgrounds
        # to paint on custom QWidget subclasses.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "background-color: #1a1a1a;"
            "border: none;"
        )

        # Dock bar — full-height colored background behind buttons
        self.dock_bar = QWidget(self)
        self.dock_bar.hide()

        # Button row — floats on top of dock bar
        self.button_row = QWidget(self)
        self.button_row.setStyleSheet("background: transparent;")
        self.layout = QHBoxLayout(self.button_row)
        self.layout.setContentsMargins(30, 0, 30, 0)
        self.layout.setSpacing(4)

    def resizeEvent(self, event) -> None:
        """Keep dock bar and button row filling the entire appbar."""
        w, h = self.width(), self.height()
        self.dock_bar.setGeometry(0, 0, w, h)
        self.button_row.setGeometry(0, 0, w, h)
        super().resizeEvent(event)

    def refresh_dock_bar(self) -> None:
        """Show/hide and style the dock bar based on config."""
        enabled = self.parent_window.config["settings"].get("appbar_dock_bar", False)
        if enabled:
            dock_color = self.parent_window.config["settings"].get(
                "appbar_dock_color",
                self.parent_window.config["settings"].get("appbar_accent_color", "#6b8cce"),
            )
            self.dock_bar.setStyleSheet(
                f"background-color: {dock_color};"
                "border: none;"
            )
            self.dock_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self.dock_bar.show()
            self.dock_bar.lower()  # behind buttons
        else:
            self.dock_bar.hide()
            self.setStyleSheet(
                "background-color: #1a1a1a;"
                "border: none;"
            )

    def toggle_for_tile(self, tile) -> None:
        """Show or hide the bar for the given tile."""
        if self.isVisible() and self.target_tile is tile:
            self.hide_bar()
        else:
            self.show_for_tile(tile)

    def show_for_tile(self, tile) -> None:
        """Slide the bar up from the bottom."""
        self.target_tile = tile
        self.refresh_menu()
        self.refresh_dock_bar()
        self.raise_()

        self.setGeometry(0, self.parent_window.height(), self.parent_window.width(), 70)
        self.show()

        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(200)
        self.anim.setStartValue(
            QRect(0, self.parent_window.height(), self.parent_window.width(), 70)
        )
        self.anim.setEndValue(
            QRect(0, self.parent_window.height() - 70, self.parent_window.width(), 70)
        )
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.anim.start()

    def hide_bar(self) -> None:
        """Hide the bar immediately."""
        self.target_tile = None
        self.hide()

    def refresh_menu(self) -> None:
        """Rebuild the button row for the current target tile."""
        # Clear old buttons
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Apply spacing from config
        spacing = self.parent_window.config["settings"].get("appbar_icon_spacing", 4)
        self.layout.setSpacing(spacing)

        # Read alignment
        alignment = self.parent_window.config["settings"].get("appbar_alignment", "Left")

        if self.target_tile:
            tile = self.target_tile

            # Alignment: insert leading stretch if needed
            if alignment == "Right":
                self.layout.addStretch()
            elif alignment == "Center":
                self.layout.addStretch()

            self.layout.addWidget(
                AppBarButton("Unpin", "cmd_unpin", lambda: self.action_delete(), self)
            )
            self.layout.addWidget(
                AppBarButton("Resize", "cmd_resize", lambda: tile.cycle_size(), self)
            )
            self.layout.addWidget(
                AppBarButton("Edit", "cmd_edit", lambda: self.action_edit(), self)
            )
            self.layout.addWidget(
                AppBarButton("Color", "cmd_color", lambda: tile.change_color(), self)
            )
            self.layout.addWidget(
                AppBarButton("Icon", "cmd_icon", lambda: tile.change_icon(), self)
            )

            # Alignment: trailing stretch
            if alignment in ("Left", "Center"):
                self.layout.addStretch()

    def action_delete(self) -> None:
        if self.target_tile:
            self.target_tile.request_delete()
            self.hide_bar()

    def action_edit(self) -> None:
        if self.target_tile:
            self.target_tile.edit_details()
            self.hide_bar()
