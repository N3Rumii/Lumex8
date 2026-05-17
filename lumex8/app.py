"""LauncherWindow — the main fullscreen tile launcher application."""

import json
import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont, QColor, QKeySequence, QPixmap, QPainter, QKeyEvent, QAction
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QScrollArea, QSystemTrayIcon,
                             QMenu, QApplication, QInputDialog, QMessageBox)
from pynput import keyboard

from lumex8.config import load_config, save_config
from lumex8.services.asset_manager import AssetManager
from lumex8.services.plugin_manager import PluginManager
from lumex8.services.gamepad import GamepadWorker
from lumex8.widgets.start_button import FloatingStartButton
from lumex8.widgets.group import GroupWidget
from lumex8.widgets.tile import MetroTile
from lumex8.widgets.scroll import KineticScrollArea
from lumex8.widgets.appbar import AppBar
from lumex8.dialogs.settings import SettingsDialog
from lumex8.dialogs.app_editor import AppEditorDialog


class LauncherWindow(QMainWindow):
    """The main frameless fullscreen tile launcher window."""

    def __init__(self) -> None:
        super().__init__()

        # 1. Assets & config
        AssetManager.ensure_directories()
        self.config_file = "config.json"
        self.is_edit_mode = False
        self.load_config()
        self.apply_active_theme()

        # 2. Sub-systems
        self.app_bar = AppBar(self)
        self.plugin_manager = PluginManager()

        # 3. UI
        self.init_ui()

        # 4. Gamepad worker
        self.gamepad_thread = GamepadWorker()
        self.gamepad_thread.btn_pressed.connect(self.handle_gamepad_btn)
        self.gamepad_thread.dpad.connect(self.handle_gamepad_nav)
        self.gamepad_thread.start()

        # 5. Tray & shortcuts
        self.setup_tray()
        self.setup_shortcuts()

        # 6. Floating start button
        self.floating_btn = FloatingStartButton(self)
        self.floating_btn.hide()

        # 7. Debounced save timer
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self._save_to_disk)

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    def load_config(self) -> None:
        self.config = load_config(self.config_file)

    def save_config(self) -> None:
        """Trigger debounced save (2s)."""
        self.save_timer.start(2000)

    def _save_to_disk(self) -> None:
        save_config(self.config_file, self.config)

    def closeEvent(self, event) -> None:
        self._save_to_disk()
        if hasattr(self, "gamepad_thread"):
            self.gamepad_thread.stop()
            self.gamepad_thread.wait(500)
        event.accept()

    def apply_active_theme(self) -> None:
        """Apply the active theme's settings on top of the current config."""
        active = self.config.get("active_theme", "Default")
        themes = self.config.get("themes", [])
        theme = None
        for t in themes:
            if t["name"] == active:
                theme = t
                break
        if theme:
            self.config["settings"] = theme.get("settings", self.config["settings"])
            self.config["start_btn"] = theme.get("start_btn", self.config.get("start_btn", {}))
            if "icon_theme" in theme.get("settings", {}):
                self.config["settings"]["icon_theme"] = theme["settings"]["icon_theme"]
            else:
                self.config["settings"]["icon_theme"] = theme.get("icon_theme", "default_theme")
            ov = theme.get("icon_color_override") or theme.get("settings", {}).get("icon_color_override", {})
        else:
            ov = self.config["settings"].get("icon_color_override", {})

        self.icon_color_override_enabled = ov.get("enabled", False)
        self.icon_color_override_color = ov.get("color", "#ffffff")
        self.config["settings"]["icon_color_override"] = {
            "enabled": self.icon_color_override_enabled,
            "color": self.icon_color_override_color,
        }

    def get_theme_icon_path(self) -> str:
        """Return the directory path for the active icon theme."""
        theme = self.config["settings"].get("icon_theme", "default_theme")
        if theme == "default_theme":
            return AssetManager.SYSTEM_DIR
        return os.path.join(AssetManager.THEMES_DIR, theme)

    def _apply_title_alignment(self) -> None:
        """Rebuild the toolbar to position title_lbl per title_alignment setting."""
        toolbar = self.toolbar_layout
        # Clear all items
        while toolbar.count():
            item = toolbar.takeAt(0)

        alignment = self.config["settings"].get("title_alignment", "Left")

        if alignment == "Right":
            toolbar.addStretch()
            toolbar.addWidget(self.title_lbl)
        elif alignment == "Center":
            toolbar.addStretch()
            toolbar.addWidget(self.title_lbl)
            toolbar.addStretch()
        else:  # Left
            toolbar.addWidget(self.title_lbl)
            toolbar.addStretch()

        # Buttons always on the right
        toolbar.addWidget(self.add_grp_btn)
        toolbar.addWidget(self.cog_btn)
        toolbar.addWidget(self.close_btn)

    # ------------------------------------------------------------------
    # Hotkeys & gamepad
    # ------------------------------------------------------------------
    def setup_shortcuts(self) -> None:
        try:
            if hasattr(self, "hotkey_listener"):
                self.hotkey_listener.stop()

            hotkeys = {}
            hk = self.config["settings"].get("global_hotkey", "<cmd>+p")
            hotkeys[hk] = self.toggle_visibility

            ehk = self.config["settings"].get("edit_hotkey", "")
            if ehk:
                hotkeys[ehk] = self.toggle_edit_mode

            self.hotkey_listener = keyboard.GlobalHotKeys(hotkeys)
            self.hotkey_listener.start()
        except Exception:
            pass

    def setup_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon.fromTheme("applications-system"))
        menu = QMenu()
        menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        quit_action = QAction("Quit Launcher", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(
            lambda r: self.toggle_visibility()
            if r == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )

    def toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide()
            self.floating_btn.apply_settings()
        else:
            self.showFullScreen()
            self.activateWindow()
            self.floating_btn.hide()

    def handle_gamepad_btn(self, btn_name: str) -> None:
        target = self.config["settings"].get("gamepad_hotkey", "GUIDE")
        if btn_name == target:
            self.toggle_visibility()

        if not self.isVisible():
            return

        # Defer UI operations to avoid thread races with refresh_ui
        QTimer.singleShot(0, lambda b=btn_name: self._do_gamepad_btn(b))

    def _do_gamepad_btn(self, btn_name: str) -> None:
        if not self.isVisible():
            return

        focus_widget = self.focusWidget()
        if btn_name == "A":
            if isinstance(focus_widget, MetroTile):
                focus_widget.trigger_action()
            elif isinstance(focus_widget, QPushButton):
                focus_widget.click()
        elif btn_name == "B":
            if hasattr(self, "app_bar") and self.app_bar.isVisible():
                self.app_bar.hide_bar()
        elif btn_name == "Y":
            if isinstance(focus_widget, MetroTile):
                self.app_bar.toggle_for_tile(focus_widget)
        elif btn_name == "START":
            self.toggle_edit_action.toggle()

    def handle_gamepad_nav(self, direction: str) -> None:
        if not self.isVisible():
            return

        # Defer navigation to avoid thread-warning races with refresh_ui
        QTimer.singleShot(0, lambda d=direction: self._do_gamepad_nav(d))

    def _do_gamepad_nav(self, direction: str) -> None:
        if not self.isVisible():
            return

        # Collect all visible tiles
        all_tiles: list = []
        for i in range(self.groups_layout.count()):
            item = self.groups_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), GroupWidget):
                group = item.widget()
                for j in range(group.grid.count()):
                    tile = group.grid.itemAt(j).widget()
                    if tile and isinstance(tile, MetroTile) and tile.isVisible():
                        all_tiles.append(tile)

        if not all_tiles:
            return

        current = self.focusWidget()
        if not current or not isinstance(current, MetroTile):
            all_tiles[0].setFocus()
            return

        try:
            idx = all_tiles.index(current)
        except ValueError:
            idx = 0

        cols = self.config["settings"].get("group_columns", 2)
        next_idx = idx
        if direction == "RIGHT":
            next_idx = min(idx + 1, len(all_tiles) - 1)
        elif direction == "LEFT":
            next_idx = max(idx - 1, 0)
        elif direction == "DOWN":
            next_idx = min(idx + cols, len(all_tiles) - 1)
        elif direction == "UP":
            next_idx = max(idx - cols, 0)

        target = all_tiles[next_idx]
        target.setFocus()
        self.scroll_area.ensureWidgetVisible(target)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def init_ui(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.showFullScreen()

        self.central_container = QWidget()
        self.setCentralWidget(self.central_container)
        self.apply_background()

        layout = QVBoxLayout(self.central_container)
        layout.setContentsMargins(40, 60, 40, 40)

        # Toolbar
        self.toolbar_layout = QHBoxLayout()
        title_text = self.config["settings"].get("title_text", "") or os.getlogin()
        self.title_lbl = QLabel(title_text)
        self.title_lbl.setStyleSheet(
            "font-size: 30px; font-weight: 300; color: white; font-family: 'Segoe UI Light';"
        )

        self.add_grp_btn = QPushButton("+ Group")
        self.add_grp_btn.clicked.connect(self.add_group)
        self.add_grp_btn.hide()
        self._style_toolbar_btn(self.add_grp_btn)

        self.cog_btn = QPushButton("\u2699")
        self.cog_btn.setFixedSize(50, 40)
        self._style_toolbar_btn(self.cog_btn)

        # Cog dropdown menu
        cog_menu = QMenu(self.cog_btn)
        self.toggle_edit_action = cog_menu.addAction("\u270e Add Tiles")
        self.toggle_edit_action.setCheckable(True)
        self.toggle_edit_action.triggered.connect(self._on_edit_action)
        cog_menu.addSeparator()
        cog_menu.addAction("Settings", self.open_settings)
        self.cog_btn.setMenu(cog_menu)

        self.close_btn = QPushButton("\u2715")
        self.close_btn.setFixedSize(50, 40)
        self.close_btn.setStyleSheet(
            "background-color: transparent; color: white; font-size: 20px; border: none;"
        )
        self.close_btn.clicked.connect(self.toggle_visibility)

        self._apply_title_alignment()
        layout.addLayout(self.toolbar_layout)

        # Scrollable groups area (KineticScrollArea)
        self.scroll_area = KineticScrollArea()
        self.groups_container = QWidget()
        self.groups_container.setStyleSheet("background: transparent;")
        self.groups_layout = QHBoxLayout(self.groups_container)
        self.groups_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.groups_layout.setSpacing(0)
        self.scroll_area.setWidget(self.groups_container)
        layout.addWidget(self.scroll_area)

        self.refresh_ui()

    def _style_toolbar_btn(self, btn) -> None:
        btn.setStyleSheet(
            "QPushButton { background-color: rgba(0, 0, 0, 0.5); color: white; "
            "border: 1px solid rgba(255,255,255,0.3); font-size: 14px; "
            "border-radius: 5px; padding: 5px; } "
            "QPushButton:hover { background-color: rgba(255, 255, 255, 0.2); } "
            "QPushButton:checked { background-color: #e51400; border: none; }"
        )

    def paintEvent(self, event) -> None:
        """Draw background with opacity support for images and slideshows."""
        painter = QPainter(self)
        s = self.config.get("settings", {})
        opacity = s.get("background_opacity", 100) / 100.0
        painter.setOpacity(opacity)

        bg_type = s.get("background_type", "color")

        if bg_type == "slideshow":
            folder = s.get("slideshow_folder", "")
            if folder and os.path.isdir(folder):
                # Build image list
                if (not hasattr(self, "_ss_cache_path")
                        or self._ss_cache_path != folder):
                    self._ss_cache_path = folder
                    self._ss_images = sorted(
                        f for f in os.listdir(folder)
                        if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp"))
                    )
                    self._ss_index = 0

                if self._ss_images:
                    # Setup slideshow timer
                    if not hasattr(self, "_ss_timer") or not self._ss_timer:
                        self._ss_timer = QTimer(self)
                        self._ss_timer.timeout.connect(lambda: self._advance_slideshow())
                        interval = s.get("slideshow_interval", 60) * 1000
                        self._ss_timer.start(interval)

                    # Draw current slide from cache
                    if hasattr(self, "_ss_cached_pix") and not self._ss_cached_pix.isNull():
                        scaled = self._ss_cached_pix
                        x = (self.width() - scaled.width()) // 2
                        y = (self.height() - scaled.height()) // 2
                        painter.drawPixmap(x, y, scaled)
                    return

        elif bg_type == "image":
            path = s.get("background_value", "")
            if path and os.path.exists(path):
                # Cache raw pixmap — only reload when path changes
                if not hasattr(self, "_bg_cache_path") or self._bg_cache_path != path:
                    self._bg_cache_path = path
                    self._bg_cache_pix = QPixmap(path)
                    self._bg_cache_size = None

                raw = self._bg_cache_pix
                if not raw.isNull():
                    cur_size = (self.width(), self.height())
                    if (not hasattr(self, "_bg_cache_scaled")
                            or self._bg_cache_size != cur_size):
                        self._bg_cache_scaled = raw.scaled(
                            *cur_size,
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        self._bg_cache_size = cur_size

                    scaled = self._bg_cache_scaled
                    x = (self.width() - scaled.width()) // 2
                    y = (self.height() - scaled.height()) // 2
                    painter.drawPixmap(x, y, scaled)
        else:
            color_hex = s.get("background_color", "#1d1d1d")
            painter.fillRect(self.rect(), QColor(color_hex))

    def _advance_slideshow(self) -> None:
        """Move to next image in the slideshow and pre-cache it."""
        if hasattr(self, "_ss_images") and self._ss_images:
            self._ss_index = (self._ss_index + 1) % len(self._ss_images)
            # Pre-cache the next slide
            folder = self.config.get("settings", {}).get("slideshow_folder", "")
            img_path = os.path.join(folder, self._ss_images[self._ss_index])
            if os.path.exists(img_path):
                pix = QPixmap(img_path)
                if not pix.isNull():
                    self._ss_cached_pix = pix.scaled(
                        self.size(),
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
            self.update()

    def apply_background(self) -> None:
        """Make container transparent — background is drawn in paintEvent."""
        self._bg_cache_path = None  # invalidate cache
        self.central_container.setStyleSheet("background: transparent;")
        self.update()

    def refresh_ui(self) -> None:
        if hasattr(self, 'app_bar'):
            self.app_bar.hide_bar()
        self.setUpdatesEnabled(False)

        while self.groups_layout.count():
            item = self.groups_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        groups = self.config.get("groups", [])
        for i, grp_data in enumerate(groups):
            grp_widget = GroupWidget(self, grp_data, i)
            self.groups_layout.addWidget(grp_widget)
        self.groups_layout.addStretch()

        self.setUpdatesEnabled(True)

    def _on_edit_action(self) -> None:
        """Handle cog menu click — just call toggle."""
        self.toggle_edit_mode()

    def toggle_edit_mode(self) -> None:
        """Toggle edit mode on/off. Safe from hotkeys or menu."""
        self.is_edit_mode = not self.is_edit_mode
        self.toggle_edit_action.setChecked(self.is_edit_mode)
        self.add_grp_btn.setVisible(self.is_edit_mode)
        # Defer UI rebuild to main thread (called from pynput thread via hotkeys)
        QTimer.singleShot(0, self.refresh_ui)

    def open_settings(self) -> None:
        dlg = SettingsDialog(self)
        if dlg.exec():
            pass

    # ------------------------------------------------------------------
    # Group & tile management
    # ------------------------------------------------------------------
    def add_group(self) -> None:
        dlg = QInputDialog(self)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        dlg.setWindowTitle("New Group")
        dlg.setLabelText("Group Name:")
        if dlg.exec():
            name = dlg.textValue()
            if name:
                self.config["groups"].append({"name": name, "apps": []})
                self.save_config()
                self.refresh_ui()

    def delete_group(self, index: int) -> None:
        del self.config["groups"][index]
        self.save_config()
        self.refresh_ui()

    def add_new_item(self, group_index: int) -> None:
        dlg = AppEditorDialog(self, self)
        if dlg.exec():
            new_data = dlg.get_data()
            if new_data["name"]:
                self.config["groups"][group_index]["apps"].append(new_data)
                self.save_config()
                self.refresh_ui()

    def delete_item(self, group_index: int, item_index: int) -> None:
        msg = QMessageBox(self)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        msg.setWindowTitle("Delete")
        msg.setText("Remove item?")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if msg.exec() == QMessageBox.StandardButton.Yes:
            del self.config["groups"][group_index]["apps"][item_index]
            self.save_config()
            self.refresh_ui()

    def handle_drop(self, src_grp: int, src_idx: int, dst_grp: int, dst_idx: int) -> None:
        def get_list(grp_idx):
            return self.config["groups"][grp_idx]["apps"]

        src_list = get_list(src_grp)
        dst_list = get_list(dst_grp)
        item = src_list.pop(src_idx)

        if src_grp == dst_grp and src_idx < dst_idx:
            dst_idx -= 1

        if dst_idx == -1:
            dst_list.append(item)
        else:
            dst_list.insert(dst_idx, item)

        # Optimize: same-group move → only rebuild that group
        if src_grp == dst_grp:
            self.repopulate_group(src_grp)
        else:
            self.refresh_ui()

    def repopulate_group(self, group_index: int) -> None:
        """Rebuild a single group's grid without destroying existing tiles."""
        item = self.groups_layout.itemAt(group_index)
        if not item or not item.widget() or not isinstance(item.widget(), GroupWidget):
            return
        group = item.widget()

        # Collect existing tiles
        tile_map: dict[int, object] = {}
        for i in range(group.grid.count()):
            grid_item = group.grid.itemAt(i)
            if grid_item and grid_item.widget():
                tile = grid_item.widget()
                idx = getattr(tile, "item_index", -1)
                if idx >= 0:
                    tile_map[idx] = tile

        # Remove all from grid without destroying
        while group.grid.count():
            child = group.grid.takeAt(0)
            w = child.widget()
            if w:
                group.grid.removeWidget(w)

        # Re-add tiles in new config order
        group.populate_grid(tile_map if tile_map else None)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            focus_widget = self.focusWidget()
            if isinstance(focus_widget, QPushButton):
                focus_widget.click()
                return
        super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        if hasattr(self, 'app_bar') and self.app_bar.isVisible():
            self.app_bar.setGeometry(0, self.height() - 70, self.width(), 70)
            self.app_bar.raise_()
        super().resizeEvent(event)

    def mousePressEvent(self, event) -> None:
        if hasattr(self, 'app_bar') and self.app_bar.isVisible():
            if not self.app_bar.geometry().contains(event.pos()):
                self.app_bar.hide_bar()
        super().mousePressEvent(event)

    def focusOutEvent(self, event) -> None:
        if hasattr(self, 'app_bar'):
            self.app_bar.hide_bar()
        super().focusOutEvent(event)
