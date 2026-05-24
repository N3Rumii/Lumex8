"""App Tile Editor — QDialog for creating or editing application tiles."""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from lumex8.dialogs.app_importer import AppImporterDialog


class AppEditorDialog(QDialog):
    """Dialog for adding or editing an application tile.

    Parameters
    ----------
    parent_window : QWidget
        The parent launcher window instance.
    app_data : dict | None
        Optional dictionary of existing tile data to populate the form.
    """

    def __init__(self, parent=None, parent_window=None, app_data: dict | None = None) -> None:
        super().__init__(parent)
        self.parent_window = parent_window or parent
        self.app_data = app_data or {}

        self.setWindowTitle("Properties")
        self.setFixedWidth(400)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            QDialog {
                background-color: #2d2d2d;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
                background: transparent;
            }
            QCheckBox {
                color: #e0e0e0;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QComboBox {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QComboBox:hover {
                border-color: #6b8cce;
            }
            QComboBox QAbstractItemView {
                background-color: #3a3a3a;
                color: #e0e0e0;
                selection-background-color: #6b8cce;
                border: 1px solid #555;
            }
            QComboBox::drop-down {
                border: none;
            }
            QLineEdit {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QLineEdit:focus {
                border-color: #6b8cce;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border-color: #6b8cce;
            }
            QPushButton:pressed {
                background-color: #555;
            }
        """)

        # Fallback color from Appearance settings, then hardcoded green
        default_tile = "#6b8cce"
        if hasattr(self.parent_window, "config"):
            default_tile = self.parent_window.config["settings"].get(
                "default_tile_color", "#6b8cce"
            )
        self._selected_color: str = self.app_data.get("color", default_tile)
        self._imported_icon: str | None = None

        self._build_ui()
        self._populate_from_data()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # ---- Name --------------------------------------------------------
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Tile name…")
        form.addRow("Name:", self.name_input)

        # ---- Tile Mode ---------------------------------------------------
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Run Application", "Special Tile"])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        form.addRow("Tile Mode:", self.mode_combo)

        layout.addLayout(form)

        # ---- Stack: Run Application fields -------------------------------
        self.app_stack = QWidget()
        app_layout = QFormLayout(self.app_stack)

        # Script path
        script_row = QHBoxLayout()
        self.script_path_input = QLineEdit()
        self.script_path_input.setPlaceholderText("/path/to/script.sh")
        script_row.addWidget(self.script_path_input)
        script_browse = QPushButton("Browse…")
        script_browse.clicked.connect(lambda: self._browse_file(self.script_path_input))
        script_row.addWidget(script_browse)
        app_layout.addRow("Script:", script_row)

        # Python path
        python_row = QHBoxLayout()
        self.python_path_input = QLineEdit()
        self.python_path_input.setPlaceholderText("/usr/bin/python3")
        python_row.addWidget(self.python_path_input)
        python_browse = QPushButton("Browse…")
        python_browse.clicked.connect(lambda: self._browse_file(self.python_path_input))
        python_row.addWidget(python_browse)
        app_layout.addRow("Python:", python_row)

        # Import button
        import_btn = QPushButton("Import from System/Flatpak…")
        import_btn.clicked.connect(self._open_importer)
        app_layout.addRow(import_btn)

        layout.addWidget(self.app_stack)

        # ---- Stack: Special Tile fields ----------------------------------
        self.special_stack = QWidget()
        special_layout = QFormLayout(self.special_stack)

        self.plugin_combo = QComboBox()
        self.plugin_combo.currentIndexChanged.connect(self._on_plugin_changed)
        special_layout.addRow("Plugin:", self.plugin_combo)

        self.plugin_config_widget = QWidget()
        self.plugin_config_layout = QFormLayout(self.plugin_config_widget)
        self.plugin_config_layout.setContentsMargins(0, 0, 0, 0)
        special_layout.addRow(self.plugin_config_widget)

        layout.addWidget(self.special_stack)

        # ---- Checkboxes --------------------------------------------------
        check_layout = QHBoxLayout()
        self.full_tile_cb = QCheckBox("Full Tile Mode")
        self.wide_tile_cb = QCheckBox("Wide Tile Mode")
        check_layout.addWidget(self.full_tile_cb)
        check_layout.addWidget(self.wide_tile_cb)
        layout.addLayout(check_layout)

        self.hide_label_cb = QCheckBox("Hide Name")
        layout.addWidget(self.hide_label_cb)

        # ---- Color picker ------------------------------------------------
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Tile Color:"))
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(40, 28)
        self._update_color_btn(self._selected_color)
        self.color_btn.clicked.connect(self._pick_color)
        color_row.addWidget(self.color_btn)
        color_row.addStretch()
        layout.addLayout(color_row)

        layout.addStretch()

        # ---- Save / Cancel -----------------------------------------------
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        # Start with the correct stack visible
        self._on_mode_changed(self.mode_combo.currentText())

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------
    def _on_mode_changed(self, mode: str) -> None:
        is_special = mode == "Special Tile"
        self.app_stack.setVisible(not is_special)
        self.special_stack.setVisible(is_special)
        if is_special:
            self.populate_plugins()

    # ------------------------------------------------------------------
    # Browse helpers
    # ------------------------------------------------------------------
    def _browse_file(self, target: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select File", os.path.expanduser("~")
        )
        if path:
            target.setText(path)

    def _open_importer(self) -> None:
        dialog = AppImporterDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Use the first selected app to fill in the fields
            apps = dialog.apps_selected  # signal not used here — read table directly
            # Actually grab data from internal table
            if dialog.table.rowCount() > 0:
                selected_rows = {
                    idx.row() for idx in dialog.table.selectedIndexes()
                }
                if selected_rows:
                    row = sorted(selected_rows)[0]
                    data_item = dialog.table.item(row, 5)  # _DATA_COL
                    if data_item is not None:
                        app = data_item.data(Qt.ItemDataRole.UserRole)
                        self.name_input.setText(app.get("name", ""))
                        exec_val = app.get("exec", "")
                        # Clean up desktop-file placeholders
                        exec_val = exec_val.replace("%f", "").replace("%F", "")
                        exec_val = exec_val.replace("%u", "").replace("%U", "")
                        exec_val = exec_val.strip().strip('"')
                        self.script_path_input.setText(exec_val)
                        # System/AppImage apps run directly, not via Python
                        self.python_path_input.setText("SYSTEM")
                        # Auto-import system icon
                        if app.get("import_icon", True) and app.get("icon"):
                            self._imported_icon = app.get("icon")
                        else:
                            self._imported_icon = None

    # ------------------------------------------------------------------
    # Color picker
    # ------------------------------------------------------------------
    def populate_plugins(self) -> None:
        """Fill the plugin combo with available plugins."""
        self.plugin_combo.clear()
        self.plugin_combo.addItem("(none)", None)
        if self.parent_window and hasattr(self.parent_window, "plugin_manager"):
            for pid, pinfo in self.parent_window.plugin_manager.plugins.items():
                self.plugin_combo.addItem(pinfo.get("name", pid), pid)

    def _on_plugin_changed(self, _index: int) -> None:
        """Rebuild plugin config fields when plugin selection changes.

        Also auto-fills the tile name from the plugin's NAME if the
        name field is still empty.
        """
        # Clear old fields
        while self.plugin_config_layout.count():
            item = self.plugin_config_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        pid = self.plugin_combo.currentData()
        if not pid:
            return

        mgr = getattr(self.parent_window, "plugin_manager", None)
        if not mgr or pid not in mgr.plugins:
            return

        pinfo = mgr.plugins[pid]
        mod = pinfo.get("module")

        # Auto-fill name from plugin if still empty
        if not self.name_input.text().strip():
            self.name_input.setText(pinfo.get("name", pid))

        if not mod or not hasattr(mod, "CONFIG_FIELDS"):
            return

        for field in mod.CONFIG_FIELDS:
            key = field["key"]
            label = field.get("label", key)
            default = field.get("default", "")
            options = field.get("options")

            if options:
                widget = QComboBox()
                widget.addItems(options)
                current = self.app_data.get(key, default)
                idx = widget.findText(current)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            else:
                widget = QLineEdit()
                widget.setText(self.app_data.get(key, default))

            # Store the canonical config key on the widget for get_data()
            widget.setProperty("config_key", key)
            self.plugin_config_layout.addRow(label + ":", widget)

    def _pick_color(self) -> None:
        initial = QColor(self._selected_color)
        color = QColorDialog.getColor(initial, self, "Select Tile Color")
        if color.isValid():
            self._selected_color = color.name()
            self._update_color_btn(self._selected_color)

    def _update_color_btn(self, color_hex: str) -> None:
        self.color_btn.setStyleSheet(
            f"background-color: {color_hex}; border: 1px solid #555; border-radius: 4px;"
        )

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    def _populate_from_data(self) -> None:
        """Fill the form from *app_data* if provided."""
        if not self.app_data:
            return

        name = self.app_data.get("name", "")
        if name:
            self.name_input.setText(name)

        tile_type = self.app_data.get("type", "app")
        if tile_type in ("plugin", "special"):
            self.mode_combo.setCurrentText("Special Tile")
            pid = self.app_data.get("plugin_id", "")
            if pid:
                self.populate_plugins()
                idx = self.plugin_combo.findData(pid)
                if idx >= 0:
                    self.plugin_combo.setCurrentIndex(idx)
        else:
            self.mode_combo.setCurrentText("Run Application")
            script = self.app_data.get("script_path", "")
            if script:
                self.script_path_input.setText(script)
            python_path = self.app_data.get("python_path", "")
            if python_path:
                self.python_path_input.setText(python_path)

        self.full_tile_cb.setChecked(self.app_data.get("full_tile", False))
        self.wide_tile_cb.setChecked(self.app_data.get("wide_tile", False))
        self.hide_label_cb.setChecked(self.app_data.get("hide_label", False))

        color = self.app_data.get("color", "")
        if color:
            self._selected_color = color
            self._update_color_btn(self._selected_color)

    def get_data(self) -> dict:
        """Return the form state as a dictionary suitable for storing.

        Returns
        -------
        dict
            Tile data with keys: name, type, color, icon, full_tile,
            wide_tile, script_path, python_path, function.
        """
        mode = self.mode_combo.currentText()

        data: dict = {
            "name": self.name_input.text().strip(),
            "type": "app",
            "color": self._selected_color,
            "icon": self._imported_icon if self._imported_icon else self.app_data.get("icon", ""),
            "full_tile": self.full_tile_cb.isChecked(),
            "wide_tile": self.wide_tile_cb.isChecked(),
            "hide_label": self.hide_label_cb.isChecked(),
            "script_path": "",
            "python_path": "",
            "function": "",
            "plugin_id": "",
        }

        if mode == "Run Application":
            data["script_path"] = self.script_path_input.text().strip()
            data["python_path"] = self.python_path_input.text().strip()
        elif mode == "Special Tile":
            pid = self.plugin_combo.currentData()
            # If no plugin selected, fall back to first available plugin
            if not pid and self.plugin_combo.count() > 1:
                pid = self.plugin_combo.itemData(1)  # skip "(none)" at index 0
            if pid:
                data["type"] = "plugin"
                data["plugin_id"] = pid
            # Save plugin config field values using stored config keys
            for i in range(self.plugin_config_layout.count()):
                item = self.plugin_config_layout.itemAt(i)
                w = item.widget() if item else None
                if isinstance(w, (QLineEdit, QComboBox)):
                    key = w.property("config_key")
                    if key:
                        if isinstance(w, QLineEdit):
                            data[key] = w.text().strip()
                        else:
                            data[key] = w.currentText()
            # Also clear app fields
            data["script_path"] = ""
            data["python_path"] = ""

        return data
