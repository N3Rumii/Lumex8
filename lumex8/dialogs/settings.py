"""Settings Dialog — QDialog with tabs for launcher configuration."""

from __future__ import annotations

import json
import os
import shutil
import zipfile

from PyQt6.QtCore import Qt, QSize, QTimer, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from lumex8.config import save_config
from lumex8.dialogs.gamepad_recorder import GamepadRecorder
from lumex8.dialogs.hotkey_recorder import HotkeyRecorder
from lumex8.services.asset_manager import AssetManager
from lumex8.services.terminal import get_installed_terminals


class SettingsDialog(QDialog):
    """Tabbed settings dialog for the Lumex8 launcher.

    Parameters
    ----------
    parent_window : LauncherWindow
        The main launcher window instance whose config will be edited.
    """

    def __init__(self, parent_window) -> None:
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setWindowTitle("Settings")
        self.resize(500, 700)
        self._pending_tile_overrides: dict = {}
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )

        # Local working copy of the config
        self._settings: dict = {}
        self._load_settings()

        self._build_ui()

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    def _load_settings(self) -> None:
        """Deep-copy relevant settings from the parent config."""
        cfg = self.parent_window.config
        self._settings = {
            "settings": dict(cfg.get("settings", {})),
            "start_btn": dict(cfg.get("start_btn", {})),
        }

    def get_current_settings(self) -> dict:
        """Return the current settings dict."""
        return dict(self._settings.get("settings", {}))

    def get_sb_settings(self) -> dict:
        """Return the current start-button settings dict."""
        return dict(self._settings.get("start_btn", {}))

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # ---- Tab 1: Appearance --------------------------------------------
        self.tabs.addTab(self._build_general_tab(), "Appearance")

        # ---- Tab 2: System ----------------------------------------------
        self.tabs.addTab(self._build_system_tab(), "System")

        # ---- Tab 3: Themes ----------------------------------------------
        self.tabs.addTab(self._build_themes_tab(), "Themes")

        # ---- Bottom buttons ---------------------------------------------
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("Save && Close")
        save_btn.clicked.connect(self.save_and_close)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Tab 1 — Appearance
    # ------------------------------------------------------------------
    def _build_general_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        main_layout = QVBoxLayout(container)

        # -------- Colors section -----------------------------------------
        colors_content = QWidget()
        colors_form = QFormLayout(colors_content)

        self.bg_type_combo = QComboBox()
        self.bg_type_combo.addItems(["color", "image", "slideshow"])
        self.bg_type_combo.setCurrentText(
            self._settings["settings"].get("background_type", "color")
        )
        self.bg_type_combo.currentTextChanged.connect(self._on_bg_type_changed)
        colors_form.addRow("Background:", self.bg_type_combo)

        # Single image path row
        bg_path_row = QHBoxLayout()
        self.bg_path_input = QLineEdit()
        self.bg_path_input.setText(
            self._settings["settings"].get("background_value", "")
        )
        bg_path_row.addWidget(self.bg_path_input)
        bg_browse_btn = QPushButton("Browse…")
        bg_browse_btn.clicked.connect(self.browse_bg)
        bg_path_row.addWidget(bg_browse_btn)

        self.bg_path_row_widget = QWidget()
        self.bg_path_row_widget.setLayout(bg_path_row)
        colors_form.addRow("BG Image:", self.bg_path_row_widget)

        # Slideshow controls (all wrapped for easy show/hide)
        self.slideshow_widget = QWidget()
        ss_layout = QVBoxLayout(self.slideshow_widget)
        ss_layout.setContentsMargins(0, 0, 0, 0)

        ss_row = QHBoxLayout()
        self.bg_slideshow_input = QLineEdit()
        self.bg_slideshow_input.setText(
            self._settings["settings"].get("slideshow_folder", "")
        )
        ss_row.addWidget(self.bg_slideshow_input)
        ss_browse_btn = QPushButton("Browse Folder…")
        ss_browse_btn.clicked.connect(self.browse_slideshow)
        ss_row.addWidget(ss_browse_btn)
        ss_layout.addLayout(ss_row)

        interval_row = QHBoxLayout()
        self.ss_interval_spin = QSpinBox()
        self.ss_interval_spin.setRange(5, 3600)
        self.ss_interval_spin.setSuffix(" sec")
        self.ss_interval_spin.setValue(
            self._settings["settings"].get("slideshow_interval", 60)
        )
        interval_row.addWidget(QLabel("Interval:"))
        interval_row.addWidget(self.ss_interval_spin)
        interval_row.addStretch()
        ss_layout.addLayout(interval_row)

        colors_form.addRow("Slideshow:", self.slideshow_widget)

        # Recent wallpapers thumbnail bar
        colors_form.addRow(QLabel("Recent Wallpapers:"))
        self.recent_wp_widget = QWidget()
        self.recent_wp_widget.setMinimumHeight(56)
        self.recent_wp_layout = QHBoxLayout(self.recent_wp_widget)
        self.recent_wp_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_wp_layout.setSpacing(4)
        self.recent_wp_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        colors_form.addRow(self.recent_wp_widget)
        self._populate_recent_wallpapers()

        self.bg_color_btn = QPushButton()
        self.bg_color_btn.setFixedSize(40, 28)
        self.bg_color_btn.clicked.connect(lambda: self.pick_color("background_color"))
        colors_form.addRow("BG Color:", self.bg_color_btn)

        self.bg_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.bg_opacity_slider.setRange(1, 100)
        self.bg_opacity_slider.setValue(
            self._settings["settings"].get("background_opacity", 100)
        )
        self.bg_opacity_label = QLabel(f"{self.bg_opacity_slider.value()}%")
        self.bg_opacity_slider.valueChanged.connect(
            lambda v: self.bg_opacity_label.setText(f"{v}%")
        )
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self.bg_opacity_slider)
        opacity_row.addWidget(self.bg_opacity_label)
        colors_form.addRow("Opacity:", opacity_row)

        self.accent_color_btn = QPushButton()
        self.accent_color_btn.setFixedSize(40, 28)
        self.accent_color_btn.clicked.connect(
            lambda: self.pick_color("appbar_accent_color")
        )
        colors_form.addRow("AppBar Accent:", self.accent_color_btn)

        self.default_tile_color_btn = QPushButton()
        self.default_tile_color_btn.setFixedSize(40, 28)
        self.default_tile_color_btn.clicked.connect(
            lambda: self.pick_color("default_tile_color")
        )
        colors_form.addRow("Default Tile:", self.default_tile_color_btn)

        self.sb_color_btn = QPushButton()
        self.sb_color_btn.setFixedSize(40, 28)
        self.sb_color_btn.clicked.connect(lambda: self.pick_color("start_btn_color"))
        colors_form.addRow("Start Button:", self.sb_color_btn)

        self._add_collapsible_section(main_layout, "Colors", colors_content)

        # -------- AppBar section -----------------------------------------
        appbar_content = QWidget()
        appbar_form = QFormLayout(appbar_content)

        self.appbar_show_labels_cb = QCheckBox("Show icon labels")
        self.appbar_show_labels_cb.setChecked(
            self._settings["settings"].get("appbar_show_labels", True)
        )
        appbar_form.addRow(self.appbar_show_labels_cb)

        self.appbar_tint_icons_cb = QCheckBox("Tint icons with accent color")
        self.appbar_tint_icons_cb.setChecked(
            self._settings["settings"].get("appbar_tint_icons", True)
        )
        appbar_form.addRow(self.appbar_tint_icons_cb)

        self.appbar_icon_spacing_slider = QSlider(Qt.Orientation.Horizontal)
        self.appbar_icon_spacing_slider.setRange(0, 40)
        self.appbar_icon_spacing_slider.setValue(
            self._settings["settings"].get("appbar_icon_spacing", 4)
        )
        self.appbar_spacing_label = QLabel(f"{self.appbar_icon_spacing_slider.value()}px")
        self.appbar_icon_spacing_slider.valueChanged.connect(
            lambda v: self.appbar_spacing_label.setText(f"{v}px")
        )
        ais_row = QHBoxLayout()
        ais_row.addWidget(self.appbar_icon_spacing_slider)
        ais_row.addWidget(self.appbar_spacing_label)
        appbar_form.addRow("Icon Spacing:", ais_row)

        self.appbar_dock_bar_cb = QCheckBox("Show dock background")
        self.appbar_dock_bar_cb.setChecked(
            self._settings["settings"].get("appbar_dock_bar", False)
        )
        appbar_form.addRow(self.appbar_dock_bar_cb)

        self.appbar_dock_color_btn = QPushButton()
        self.appbar_dock_color_btn.setFixedSize(40, 28)
        self.appbar_dock_color_btn.clicked.connect(
            lambda: self.pick_color("appbar_dock_color")
        )
        appbar_form.addRow("Dock Color:", self.appbar_dock_color_btn)

        self.appbar_dock_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.appbar_dock_opacity_slider.setRange(10, 100)
        self.appbar_dock_opacity_slider.setValue(
            self._settings["settings"].get("appbar_dock_opacity", 95)
        )
        self.appbar_dock_opacity_label = QLabel(
            f"{self.appbar_dock_opacity_slider.value()}%"
        )
        self.appbar_dock_opacity_slider.valueChanged.connect(
            lambda v: self.appbar_dock_opacity_label.setText(f"{v}%")
        )
        ado_row = QHBoxLayout()
        ado_row.addWidget(self.appbar_dock_opacity_slider)
        ado_row.addWidget(self.appbar_dock_opacity_label)
        appbar_form.addRow("Dock Opacity:", ado_row)

        self.appbar_alignment_combo = QComboBox()
        self.appbar_alignment_combo.addItems(["Left", "Center", "Right"])
        self.appbar_alignment_combo.setCurrentText(
            self._settings["settings"].get("appbar_alignment", "Left")
        )
        appbar_form.addRow("Alignment:", self.appbar_alignment_combo)

        self._add_collapsible_section(main_layout, "AppBar", appbar_content)

        # -------- Recolor All Tiles ---------------------------------------
        recolor_content = QWidget()
        recolor_form = QFormLayout(recolor_content)

        self._recolor_undo: list[dict] = []  # stores previous colors for undo

        self.recolor_color_btn = QPushButton()
        self.recolor_color_btn.setFixedSize(40, 28)
        self.recolor_color_btn.setStyleSheet(
            f"background-color: {self._settings['settings'].get('default_tile_color', '#00a300')};"
        )
        self.recolor_color_btn.clicked.connect(self._pick_recolor)
        recolor_form.addRow("Target color:", self.recolor_color_btn)

        recolor_row = QHBoxLayout()
        apply_btn = QPushButton("Apply to All Tiles")
        apply_btn.clicked.connect(self._apply_recolor)
        recolor_row.addWidget(apply_btn)

        undo_btn = QPushButton("Undo")
        undo_btn.clicked.connect(self._undo_recolor)
        recolor_row.addWidget(undo_btn)
        recolor_form.addRow(recolor_row)

        self._add_collapsible_section(main_layout, "Recolor All Tiles", recolor_content)

        # Sync initial button colours
        self._sync_color_buttons()

        # -------- Icon Packs section ------------------------------------
        iconpack_content = QWidget()
        iconpack_form = QFormLayout(iconpack_content)

        self.icon_pack_combo = QComboBox()
        self._populate_icon_themes_combo(self.icon_pack_combo)
        self.icon_pack_combo.currentTextChanged.connect(self._on_icon_pack_combo_changed)
        iconpack_form.addRow("Active Pack:", self.icon_pack_combo)

        # Preview area
        self.icon_pack_preview = QWidget()
        self.icon_pack_preview.setMinimumHeight(56)
        self.icon_pack_preview_layout = QHBoxLayout(self.icon_pack_preview)
        self.icon_pack_preview_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_pack_preview_layout.setSpacing(4)
        self.icon_pack_preview_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        iconpack_form.addRow("Preview:", self.icon_pack_preview)

        # Action buttons
        ip_btn_row = QHBoxLayout()
        save_pack_btn = QPushButton("Save Pack\u2026")
        save_pack_btn.clicked.connect(self._save_icon_pack)
        ip_btn_row.addWidget(save_pack_btn)

        export_pack_btn = QPushButton("Export Pack\u2026")
        export_pack_btn.clicked.connect(self._export_icon_pack)
        ip_btn_row.addWidget(export_pack_btn)

        import_pack_btn = QPushButton("Import Pack\u2026")
        import_pack_btn.clicked.connect(self._import_icon_pack)
        ip_btn_row.addWidget(import_pack_btn)

        open_pack_btn = QPushButton("Open Pack Folder")
        open_pack_btn.clicked.connect(self.open_themes_folder)
        ip_btn_row.addWidget(open_pack_btn)

        iconpack_form.addRow(ip_btn_row)

        self._add_collapsible_section(main_layout, "Icon Packs", iconpack_content)

        # -------- Tile & Layout section ----------------------------------
        tile_content = QWidget()
        tile_form = QFormLayout(tile_content)

        self.tile_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.tile_size_slider.setRange(80, 240)
        self.tile_size_slider.setValue(
            self._settings["settings"].get("tile_size", 140)
        )
        self.tile_size_label = QLabel(f"{self.tile_size_slider.value()}px")
        self.tile_size_slider.valueChanged.connect(
            lambda v: self.tile_size_label.setText(f"{v}px")
        )
        ts_row = QHBoxLayout()
        ts_row.addWidget(self.tile_size_slider)
        ts_row.addWidget(self.tile_size_label)
        tile_form.addRow("Tile Size:", ts_row)

        self.columns_spin = QSpinBox()
        self.columns_spin.setRange(1, 10)
        self.columns_spin.setValue(
            self._settings["settings"].get("group_columns", 2)
        )
        tile_form.addRow("Columns/Group:", self.columns_spin)

        self.corner_radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.corner_radius_slider.setRange(0, 50)
        self.corner_radius_slider.setValue(
            self._settings["settings"].get("tile_radius", 0)
        )
        self.corner_radius_label = QLabel(f"{self.corner_radius_slider.value()}px")
        self.corner_radius_slider.valueChanged.connect(
            lambda v: self.corner_radius_label.setText(f"{v}px")
        )
        cr_row = QHBoxLayout()
        cr_row.addWidget(self.corner_radius_slider)
        cr_row.addWidget(self.corner_radius_label)
        tile_form.addRow("Corner Radius:", cr_row)

        self.tile_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.tile_opacity_slider.setRange(0, 100)
        self.tile_opacity_slider.setValue(
            self._settings["settings"].get("tile_alpha", 255) * 100 // 255
        )
        self.tile_opacity_label = QLabel(f"{self.tile_opacity_slider.value()}%")
        self.tile_opacity_slider.valueChanged.connect(
            lambda v: self.tile_opacity_label.setText(f"{v}%")
        )
        to_row = QHBoxLayout()
        to_row.addWidget(self.tile_opacity_slider)
        to_row.addWidget(self.tile_opacity_label)
        tile_form.addRow("Tile Opacity:", to_row)

        self._add_collapsible_section(main_layout, "Tile && Layout", tile_content)

        # -------- Start Button section -----------------------------------
        sb_content = QWidget()
        sb_form = QFormLayout(sb_content)

        self.sb_visible_cb = QCheckBox("Visible")
        self.sb_visible_cb.setChecked(
            self._settings["start_btn"].get("visible", True)
        )
        sb_form.addRow(self.sb_visible_cb)

        self.sb_autohide_cb = QCheckBox("Auto-hide")
        self.sb_autohide_cb.setChecked(
            self._settings["start_btn"].get("autohide", False)
        )
        sb_form.addRow(self.sb_autohide_cb)

        self.sb_position_combo = QComboBox()
        self.sb_position_combo.addItems(
            [
                "Bottom Left",
                "Bottom Center",
                "Bottom Right",
                "Top Left",
                "Top Center",
                "Top Right",
            ]
        )
        self.sb_position_combo.setCurrentText(
            self._settings["start_btn"].get("position", "Bottom Left")
        )
        sb_form.addRow("Position:", self.sb_position_combo)

        self.sb_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.sb_size_slider.setRange(30, 100)
        self.sb_size_slider.setValue(
            self._settings["start_btn"].get("size", 60)
        )
        self.sb_size_label = QLabel(f"{self.sb_size_slider.value()}px")
        self.sb_size_slider.valueChanged.connect(
            lambda v: self.sb_size_label.setText(f"{v}px")
        )
        sbs_row = QHBoxLayout()
        sbs_row.addWidget(self.sb_size_slider)
        sbs_row.addWidget(self.sb_size_label)
        sb_form.addRow("Size:", sbs_row)

        self.sb_icon_type_combo = QComboBox()
        self.sb_icon_type_combo.addItems(["text", "image"])
        self.sb_icon_type_combo.setCurrentText(
            self._settings["start_btn"].get("icon_type", "text")
        )
        sb_form.addRow("Icon Type:", self.sb_icon_type_combo)

        sb_icon_row = QHBoxLayout()
        self.sb_icon_input = QLineEdit()
        self.sb_icon_input.setText(
            self._settings["start_btn"].get("icon_val", "\u2756")
        )
        sb_icon_row.addWidget(self.sb_icon_input)
        sb_icon_browse = QPushButton("Browse…")
        sb_icon_browse.clicked.connect(self.browse_sb_icon)
        sb_icon_row.addWidget(sb_icon_browse)
        sb_form.addRow("Icon Value:", sb_icon_row)

        # Recent start button icons thumbnail bar
        sb_form.addRow(QLabel("Recent Icons:"))
        self.recent_sb_widget = QWidget()
        self.recent_sb_widget.setMinimumHeight(56)
        self.recent_sb_layout = QHBoxLayout(self.recent_sb_widget)
        self.recent_sb_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_sb_layout.setSpacing(4)
        self.recent_sb_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        sb_form.addRow(self.recent_sb_widget)
        self._populate_recent_sb_icons()

        self._add_collapsible_section(main_layout, "Start Button", sb_content)
        main_layout.addStretch()

        scroll.setWidget(container)
        return scroll

    @staticmethod
    def _make_section_label(text: str) -> QLabel:
        """Return a bold, styled label for a settings section."""
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-weight: bold; font-size: 13px; "
            "padding: 6px 0 2px 0; color: #00a300;"
        )
        return lbl

    def _add_collapsible_section(
        self, layout: QVBoxLayout, title: str, content: QWidget
    ) -> QPushButton:
        """Add a collapsible section header + content to *layout*.

        The content widget starts visible. Clicking the header button
        toggles its visibility and updates the disclosure triangle icon.

        Returns the toggle button so callers can manipulate visibility.
        """
        btn = QPushButton(f"  \u25bc  {title}")
        btn.setStyleSheet(
            "QPushButton {"
            "  text-align: left;"
            "  border: none;"
            "  font-weight: bold;"
            "  font-size: 13px;"
            "  padding: 6px 0 2px 0;"
            "  color: #aaaaaa;"
            "  background: transparent;"
            "}"
        )
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(btn)
        layout.addWidget(content)

        btn.clicked.connect(
            lambda: self._toggle_section(btn, content)
        )
        return btn

    @staticmethod
    def _toggle_section(btn: QPushButton, content: QWidget) -> None:
        """Toggle content visibility and update disclosure triangle."""
        visible = not content.isVisible()
        content.setVisible(visible)
        triangle = "\u25bc" if visible else "\u25b6"
        # Update button text: first two chars are triangle
        text = btn.text()
        btn.setText(f"  {triangle}  {text[3:]}")

    # ------------------------------------------------------------------
    # Tab 2 — System
    # ------------------------------------------------------------------
    def _build_system_tab(self) -> QWidget:
        container = QWidget()
        layout = QFormLayout(container)

        # ---- Keyboard hotkey --------------------------------------------
        self.hotkey_recorder = HotkeyRecorder("Record Hotkey", self)
        current_hotkey = self._settings["settings"].get("global_hotkey", "")
        if current_hotkey:
            self.hotkey_recorder.set_hotkey(current_hotkey)
        layout.addRow("Global Hotkey:", self.hotkey_recorder)

        # ---- Edit mode hotkey --------------------------------------------
        self.edit_hotkey_recorder = HotkeyRecorder("Record Hotkey", self)
        current_edit_hk = self._settings["settings"].get("edit_hotkey", "")
        if current_edit_hk:
            self.edit_hotkey_recorder.set_hotkey(current_edit_hk)
        layout.addRow("Edit Mode Hotkey:", self.edit_hotkey_recorder)

        # ---- Gamepad toggle ---------------------------------------------
        self.gamepad_recorder = GamepadRecorder(
            self.parent_window, "Record Button", self
        )
        current_gamepad = self._settings["settings"].get("gamepad_hotkey", "")
        if current_gamepad:
            self.gamepad_recorder.set_button(current_gamepad)
        layout.addRow("Gamepad Toggle:", self.gamepad_recorder)

        # ---- Preferred console ------------------------------------------
        self.terminal_combo = QComboBox()
        terminals = get_installed_terminals()
        current_terminal = self._settings["settings"].get("terminal_app", "")
        for name, cmd, flags in terminals:
            self.terminal_combo.addItem(name, (cmd, flags))
        # Select the current terminal
        for i in range(self.terminal_combo.count()):
            item_data = self.terminal_combo.itemData(i)
            if item_data and item_data[0] == current_terminal:
                self.terminal_combo.setCurrentIndex(i)
                break
        layout.addRow("Preferred Console:", self.terminal_combo)

        # ---- Title (Launcher header text) ---------------------------------
        self.title_text_input = QLineEdit()
        self.title_text_input.setPlaceholderText(os.getlogin())
        current_title = self._settings["settings"].get("title_text", "")
        self.title_text_input.setText(current_title)
        layout.addRow("Header Title:", self.title_text_input)

        self.title_alignment_combo = QComboBox()
        self.title_alignment_combo.addItems(["Left", "Center", "Right"])
        self.title_alignment_combo.setCurrentText(
            self._settings["settings"].get("title_alignment", "Left")
        )
        layout.addRow("Title Alignment:", self.title_alignment_combo)

        layout.addRow(QLabel(""))  # spacer
        info = QLabel(
            "Changes to system settings take effect after a restart."
        )
        info.setStyleSheet("color: #888; font-style: italic;")
        layout.addRow(info)

        return container

    # ------------------------------------------------------------------
    # Tab 3 — Themes
    # ------------------------------------------------------------------
    def _build_themes_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        # ---- Icon theme + open folder -----------------------------------
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Icon Theme:"))
        self.icon_theme_combo = QComboBox()
        self._populate_icon_themes()
        self.icon_theme_combo.currentTextChanged.connect(self._on_icon_theme_combo_changed)
        theme_row.addWidget(self.icon_theme_combo, 1)
        open_folder_btn = QPushButton("Open Themes Folder")
        open_folder_btn.clicked.connect(self.open_themes_folder)
        theme_row.addWidget(open_folder_btn)
        layout.addLayout(theme_row)

        # ---- AppBar icon editor ------------------------------------------
        self.icons_section_btn = QPushButton(" Icons")
        self.icons_section_btn.setStyleSheet(
            "QPushButton { text-align: left; border: none;"
            " font-weight: bold; font-size: 13px; padding: 6px 0;"
            " color: #aaaaaa; background: transparent; }"
        )
        self.icons_section_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.icons_section_btn.clicked.connect(self._toggle_icon_editor)
        layout.addWidget(self.icons_section_btn)

        self.icon_editor_widget = QWidget()
        icon_editor_layout = QVBoxLayout(self.icon_editor_widget)
        icon_editor_layout.setContentsMargins(0, 4, 0, 4)

        self._custom_icon_paths: dict[str, str] = {}  # icon_name -> temp path
        icons_row = QHBoxLayout()
        icons_row.setSpacing(8)
        self.icon_buttons: dict[str, QPushButton] = {}
        for name in ("cmd_unpin", "cmd_edit", "cmd_color", "cmd_icon", "cmd_resize"):
            btn = QPushButton()
            btn.setFixedSize(48, 48)
            btn.setIconSize(QSize(32, 32))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, n=name: self._pick_appbar_icon(n))
            icons_row.addWidget(btn)
            self.icon_buttons[name] = btn
        icon_editor_layout.addLayout(icons_row)
        self._refresh_icon_editor_thumbs()

        btn_row = QHBoxLayout()
        save_icons_btn = QPushButton("Save as Pack…")
        save_icons_btn.clicked.connect(self._save_icon_pack_from_editor)
        btn_row.addWidget(save_icons_btn)
        reset_icons_btn = QPushButton("Reset to Default")
        reset_icons_btn.clicked.connect(self._reset_icon_editor)
        btn_row.addWidget(reset_icons_btn)
        btn_row.addStretch()
        icon_editor_layout.addLayout(btn_row)

        self.icon_editor_widget.hide()
        layout.addWidget(self.icon_editor_widget)

        # ---- Saved themes list ------------------------------------------
        layout.addWidget(QLabel("Skins:"))
        self.theme_list = QListWidget()
        self.theme_list.setIconSize(QSize(48, 24))
        self.theme_list.setSpacing(2)
        self.theme_list.currentItemChanged.connect(self.apply_theme_from_list)
        layout.addWidget(self.theme_list, 1)

        # ---- Theme action buttons ---------------------------------------
        action_row = QHBoxLayout()
        save_theme_btn = QPushButton("Save Current Skin…")
        save_theme_btn.clicked.connect(self.save_current_skin)
        action_row.addWidget(save_theme_btn)

        delete_theme_btn = QPushButton("Delete Skin")
        delete_theme_btn.clicked.connect(self.delete_selected_theme)
        action_row.addWidget(delete_theme_btn)
        layout.addLayout(action_row)

        export_import_row = QHBoxLayout()
        export_btn = QPushButton("Export Skin…")
        export_btn.clicked.connect(self.export_skin)
        export_import_row.addWidget(export_btn)

        import_btn = QPushButton("Import Skin…")
        import_btn.clicked.connect(self.import_skin)
        export_import_row.addWidget(import_btn)
        layout.addLayout(export_import_row)

        # ---- Reset ------------------------------------------------------
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setStyleSheet(
            "color: white; background-color: #c00; "
            "padding: 6px 18px; border-radius: 4px;"
        )
        reset_btn.clicked.connect(self.reset_defaults)
        reset_row.addWidget(reset_btn)
        layout.addLayout(reset_row)

        # Populate theme list
        self.populate_theme_list()

        return container

    # ------------------------------------------------------------------
    # Background type switching
    # ------------------------------------------------------------------
    def _on_bg_type_changed(self, bg_type: str) -> None:
        is_image = bg_type == "image"
        is_slideshow = bg_type == "slideshow"
        for i in range(self.bg_path_row_widget.layout().count()):
            w = self.bg_path_row_widget.layout().itemAt(i)
            if w and w.widget():
                w.widget().setVisible(is_image)
        self.slideshow_widget.setVisible(is_slideshow)

    # ------------------------------------------------------------------
    # Browse helpers
    # ------------------------------------------------------------------
    def browse_bg(self) -> None:
        """Open a file dialog to pick a background image."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Background Image",
            os.path.expanduser("~"),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.svg)",
        )
        if path:
            self.bg_path_input.setText(path)
            self._add_recent_wallpaper(path)

    def browse_slideshow(self) -> None:
        """Open a folder dialog for slideshow folder."""
        path = QFileDialog.getExistingDirectory(
            self, "Select Slideshow Folder", os.path.expanduser("~")
        )
        if path:
            self.bg_slideshow_input.setText(path)

    # ------------------------------------------------------------------
    # Recent wallpapers
    # ------------------------------------------------------------------
    def _populate_recent_wallpapers(self) -> None:
        """Build thumbnail buttons from recently used wallpapers."""
        while self.recent_wp_layout.count():
            item = self.recent_wp_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        recent = self.parent_window.config.setdefault("recent_wallpapers", [])
        for path in recent[:10]:
            if os.path.exists(path):
                btn = QPushButton()
                btn.setFixedSize(64, 48)
                pix = QPixmap(path).scaled(
                    64, 48, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                if not pix.isNull():
                    btn.setIcon(QIcon(pix))
                    btn.setIconSize(btn.size())
                btn.setToolTip(os.path.basename(path))
                btn.clicked.connect(lambda checked, p=path: self._select_recent_wallpaper(p))
                self.recent_wp_layout.addWidget(btn)

    def _add_recent_wallpaper(self, path: str) -> None:
        """Add a wallpaper path to the recent list."""
        recent = self.parent_window.config.setdefault("recent_wallpapers", [])
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        self.parent_window.config["recent_wallpapers"] = recent[-20:]
        self._populate_recent_wallpapers()

    def _select_recent_wallpaper(self, path: str) -> None:
        """Set the selected recent wallpaper as the current background."""
        self.bg_type_combo.setCurrentText("image")
        self.bg_path_input.setText(path)

    # --- Recent start button icons ---
    def _populate_recent_sb_icons(self) -> None:
        """Build thumbnail buttons from recently used start button icons."""
        while self.recent_sb_layout.count():
            item = self.recent_sb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        recent = self.parent_window.config.setdefault("recent_sb_icons", [])
        for path in recent[:10]:
            if os.path.exists(path):
                btn = QPushButton()
                btn.setFixedSize(64, 48)
                pix = QPixmap(path).scaled(
                    64, 48, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                if not pix.isNull():
                    btn.setIcon(QIcon(pix))
                    btn.setIconSize(btn.size())
                btn.setToolTip(os.path.basename(path))
                btn.clicked.connect(lambda checked, p=path: self._select_recent_sb_icon(p))
                self.recent_sb_layout.addWidget(btn)

    def _add_recent_sb_icon(self, path: str) -> None:
        """Add a start button icon path to the recent list."""
        recent = self.parent_window.config.setdefault("recent_sb_icons", [])
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        self.parent_window.config["recent_sb_icons"] = recent[-20:]
        self._populate_recent_sb_icons()

    def _select_recent_sb_icon(self, path: str) -> None:
        """Set the selected recent icon as the start button icon."""
        self.sb_icon_type_combo.setCurrentText("image")
        self.sb_icon_input.setText(path)

    def browse_sb_icon(self) -> None:
        """Open a file dialog to pick a start-button icon image."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Start Button Icon",
            os.path.expanduser("~"),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.svg)",
        )
        if path:
            self.sb_icon_input.setText(path)
            self._add_recent_sb_icon(path)

    # ------------------------------------------------------------------
    # Color picker
    # ------------------------------------------------------------------
    def pick_color(self, target: str) -> None:
        """Open a color dialog and update the given setting *target*.

        Parameters
        ----------
        target : str
            One of ``background_color``, ``appbar_accent_color``,
            ``default_tile_color``, ``start_btn_color``, or
            ``icon_override_color``.
        """
        current = "#ffffff"
        if target == "background_color":
            current = self._settings["settings"].get("background_color", "#1d1d1d")
        elif target == "appbar_accent_color":
            current = self._settings["settings"].get("appbar_accent_color", "#ffffff")
        elif target == "default_tile_color":
            current = self._settings["settings"].get("default_tile_color", "#00a300")
        elif target == "start_btn_color":
            current = self._settings.get("start_btn", {}).get("color", "rgba(255,255,255,0.2)")
            # Try to parse as hex if it's rgba
            if current.startswith("rgba"):
                current = "#ffffff"
        elif target == "appbar_dock_color":
            current = self._settings["settings"].get(
                "appbar_dock_color",
                self._settings["settings"].get("appbar_accent_color", "#00a300"),
            )
        elif target == "icon_override_color":
            current = (
                self._settings["settings"]
                .get("icon_color_override", {})
                .get("color", "#ffffff")
            )

        initial = QColor(current)
        color = QColorDialog.getColor(initial, self, "Pick Color")
        if not color.isValid():
            return

        hex_color = color.name()

        if target == "background_color":
            self._settings["settings"]["background_color"] = hex_color
        elif target == "appbar_accent_color":
            self._settings["settings"]["appbar_accent_color"] = hex_color
        elif target == "default_tile_color":
            self._settings["settings"]["default_tile_color"] = hex_color
        elif target == "start_btn_color":
            self._settings["start_btn"]["color"] = hex_color
        elif target == "appbar_dock_color":
            self._settings["settings"]["appbar_dock_color"] = hex_color
        elif target == "icon_override_color":
            override = self._settings["settings"].setdefault(
                "icon_color_override", {"enabled": False, "color": "#ffffff"}
            )
            override["color"] = hex_color

        self._sync_color_buttons()

    def _sync_color_buttons(self) -> None:
        """Update the colour button stylesheets from current settings."""
        self._apply_btn_color(
            self.bg_color_btn,
            self._settings["settings"].get("background_color", "#1d1d1d"),
        )
        self._apply_btn_color(
            self.accent_color_btn,
            self._settings["settings"].get("appbar_accent_color", "#ffffff"),
        )
        self._apply_btn_color(
            self.default_tile_color_btn,
            self._settings["settings"].get("default_tile_color", "#00a300"),
        )
        sb_color = self._settings.get("start_btn", {}).get("color", "rgba(255,255,255,0.2)")
        self._apply_btn_color(self.sb_color_btn, sb_color)

        dock_color = self._settings["settings"].get(
            "appbar_dock_color",
            self._settings["settings"].get("appbar_accent_color", "#00a300"),
        )
        self._apply_btn_color(self.appbar_dock_color_btn, dock_color)

        self._apply_btn_color(self.recolor_color_btn, self._settings["settings"].get("default_tile_color", "#00a300"))

    @staticmethod
    def _apply_btn_color(btn: QPushButton, color: str) -> None:
        btn.setStyleSheet(
            f"background-color: {color}; border: 1px solid #555; border-radius: 4px;"
        )

    # ------------------------------------------------------------------
    # Recolor all tiles
    # ------------------------------------------------------------------
    def _pick_recolor(self) -> None:
        color = QColorDialog.getColor(QColor("#00a300"), self, "Pick Tile Color")
        if color.isValid():
            hex_color = color.name()
            self._apply_btn_color(self.recolor_color_btn, hex_color)
            self._recolor_target = hex_color

    def _apply_recolor(self) -> None:
        target = getattr(self, "_recolor_target", "#00a300")
        # Save current colors for undo
        self._recolor_undo = []
        for grp in self.parent_window.config.get("groups", []):
            for app in grp.get("apps", []):
                old_color = app.get("color", "")
                self._recolor_undo.append({
                    "group": grp,
                    "app": app,
                    "old_color": old_color,
                })
                app["color"] = target
        self.parent_window.save_config()
        self.parent_window.refresh_ui()

    def _undo_recolor(self) -> None:
        if not self._recolor_undo:
            return
        for entry in self._recolor_undo:
            entry["app"]["color"] = entry["old_color"]
        self._recolor_undo = []
        self.parent_window.save_config()
        self.parent_window.refresh_ui()

    # ------------------------------------------------------------------
    # Save / close
    # ------------------------------------------------------------------
    def save_and_close(self) -> None:
        """Persist all settings to the parent config and close."""
        settings = self._settings["settings"]
        sb = self._settings["start_btn"]

        # General tab
        settings["background_type"] = self.bg_type_combo.currentText()
        settings["background_value"] = self.bg_path_input.text().strip()
        settings["background_opacity"] = self.bg_opacity_slider.value()
        settings["slideshow_folder"] = self.bg_slideshow_input.text().strip()
        settings["slideshow_interval"] = self.ss_interval_spin.value()


        # Tile & Layout
        settings["tile_size"] = self.tile_size_slider.value()
        settings["group_columns"] = self.columns_spin.value()
        settings["tile_radius"] = self.corner_radius_slider.value()
        settings["tile_alpha"] = self.tile_opacity_slider.value() * 255 // 100

        # AppBar
        settings["appbar_show_labels"] = self.appbar_show_labels_cb.isChecked()
        settings["appbar_tint_icons"] = self.appbar_tint_icons_cb.isChecked()
        settings["appbar_icon_spacing"] = self.appbar_icon_spacing_slider.value()
        settings["appbar_dock_bar"] = self.appbar_dock_bar_cb.isChecked()
        settings["appbar_dock_opacity"] = self.appbar_dock_opacity_slider.value()
        settings["appbar_alignment"] = self.appbar_alignment_combo.currentText()
        # dock_color is already stored in _settings via pick_color()
        settings["appbar_dock_color"] = self._settings["settings"].get(
            "appbar_dock_color",
            settings.get("appbar_accent_color", "#00a300"),
        )

        # Start Button
        sb["visible"] = self.sb_visible_cb.isChecked()
        sb["autohide"] = self.sb_autohide_cb.isChecked()
        sb["position"] = self.sb_position_combo.currentText()
        sb["size"] = self.sb_size_slider.value()
        sb["icon_type"] = self.sb_icon_type_combo.currentText()
        sb["icon_val"] = self.sb_icon_input.text().strip()

        # System tab
        settings["global_hotkey"] = self.hotkey_recorder.current_hotkey()
        settings["edit_hotkey"] = self.edit_hotkey_recorder.current_hotkey()
        settings["gamepad_hotkey"] = self.gamepad_recorder.current_button()
        term_idx = self.terminal_combo.currentIndex()
        if term_idx >= 0:
            term_data = self.terminal_combo.currentData()
            if term_data:
                settings["terminal_app"] = term_data[0]
                settings["terminal_flags"] = term_data[1]

        # Title (header text)
        settings["title_text"] = self.title_text_input.text().strip()
        settings["title_alignment"] = self.title_alignment_combo.currentText()

        # Icon theme
        settings["icon_theme"] = self.icon_pack_combo.currentText()

        # Write back to parent config
        self.parent_window.config["settings"] = settings
        self.parent_window.config["start_btn"] = sb

        # Apply pending tile overrides from skin
        overrides = getattr(self, "_pending_tile_overrides", {})
        if overrides:
            for key, ov in overrides.items():
                try:
                    gi_str, ti_str = key.split(":")
                    gi, ti = int(gi_str), int(ti_str)
                except (ValueError, IndexError):
                    continue
                groups = self.parent_window.config.get("groups", [])
                if gi < len(groups):
                    apps = groups[gi].get("apps", [])
                    if ti < len(apps):
                        if "color" in ov:
                            apps[ti]["color"] = ov["color"]
                        if "icon" in ov:
                            apps[ti]["icon"] = ov["icon"]
            self._pending_tile_overrides = {}

        # Persist to disk
        config_file = getattr(self.parent_window, "config_file", "")
        if config_file:
            save_config(config_file, self.parent_window.config)

        # Apply visual changes immediately
        if hasattr(self.parent_window, "apply_background"):
            self.parent_window.apply_background()

        # Update title label
        if hasattr(self.parent_window, "title_lbl"):
            title_text = settings.get("title_text", "") or os.getlogin()
            self.parent_window.title_lbl.setText(title_text)
        if hasattr(self.parent_window, "_apply_title_alignment"):
            self.parent_window._apply_title_alignment()

        if hasattr(self.parent_window, "refresh_ui"):
            self.parent_window.refresh_ui()
        if hasattr(self.parent_window, "floating_btn"):
            self.parent_window.floating_btn.apply_settings()

        # Restart hotkey listener with new keybindings
        if hasattr(self.parent_window, "setup_shortcuts"):
            self.parent_window.setup_shortcuts()

        self.accept()

    # ------------------------------------------------------------------
    # Icon theme helpers
    # ------------------------------------------------------------------
    def _populate_icon_themes(self) -> None:
        """Scan the themes directory and populate the combo box."""
        current = self._settings["settings"].get("icon_theme", "default_theme")
        self.icon_theme_combo.clear()

        if os.path.isdir(AssetManager.THEMES_DIR):
            for entry in sorted(os.listdir(AssetManager.THEMES_DIR)):
                theme_path = os.path.join(AssetManager.THEMES_DIR, entry)
                if os.path.isdir(theme_path):
                    self.icon_theme_combo.addItem(entry)

        idx = self.icon_theme_combo.findText(current)
        if idx >= 0:
            self.icon_theme_combo.setCurrentIndex(idx)

    def open_themes_folder(self) -> None:
        """Open the themes directory in the file manager."""
        AssetManager.ensure_directories()
        QDesktopServices.openUrl(QUrl.fromLocalFile(AssetManager.THEMES_DIR))

    # ------------------------------------------------------------------
    # Theme management
    # ------------------------------------------------------------------
    def populate_theme_list(self) -> None:
        """Populate the theme list from the parent config's themes data."""
        self.theme_list.clear()
        themes = self.parent_window.config.get("themes", [])
        for theme in themes:
            name = theme.get("name", "Unnamed")
            colors = self.get_swatch_colors(theme)
            icon = self.create_swatch_icon(colors)
            item = QListWidgetItem(icon, name)
            item.setData(Qt.ItemDataRole.UserRole, theme)
            self.theme_list.addItem(item)

    @staticmethod
    def get_swatch_colors(theme: dict) -> tuple[str, str, str]:
        """Extract (bg, tile, accent) colour strings from a theme dict.

        Parameters
        ----------
        theme : dict
            A theme dictionary with at least ``background_color``,
            ``default_tile_color``, and optionally ``appbar_accent_color``.

        Returns
        -------
        tuple[str, str, str]
            A tuple of hex colour strings ``(bg, tile, accent)``.
        """
        bg = theme.get("background_color", "#1d1d1d")
        tile = theme.get("default_tile_color", "#00a300")
        accent = theme.get("appbar_accent_color", "#ffffff")
        return bg, tile, accent

    @staticmethod
    def create_swatch_icon(colors: tuple[str, str, str]) -> QIcon:
        """Create a small horizontal swatch icon from three colour strings.

        Parameters
        ----------
        colors : tuple[str, str, str]
            ``(bg, tile, accent)`` hex colour strings.

        Returns
        -------
        QIcon
            A 48×24 pixmap with three coloured panels.
        """
        pix = QPixmap(48, 24)
        pix.fill(QColor("#00000000"))
        painter = QPainter(pix)
        third = 16
        for i, color_str in enumerate(colors):
            painter.fillRect(i * third, 0, third, 24, QColor(color_str))
        painter.end()
        return QIcon(pix)

    @staticmethod
    def _sanitize_slug(name: str) -> str:
        """Convert a theme name into a filesystem-safe slug."""
        import re
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", name.lower()).strip("_")
        return slug or "theme"

    def _collect_theme_images(self) -> dict[str, str]:
        """Collect all image paths referenced by the current settings.

        Returns a dict mapping a stable key (e.g. ``bg``, ``tile_0:1``, ``sb``)
        to the original filesystem path.
        """
        images: dict[str, str] = {}
        settings = self._settings["settings"]

        # Wallpaper
        bg_val = settings.get("background_value", "")
        if bg_val and os.path.isfile(bg_val):
            images["bg"] = bg_val

        # Start button icon
        sb = self._settings.get("start_btn", {})
        if sb.get("icon_type") == "image":
            sb_val = sb.get("icon_val", "")
            if sb_val and os.path.isfile(sb_val):
                images["sb"] = sb_val

        # Tile icons
        for gi, grp in enumerate(self.parent_window.config.get("groups", [])):
            for ti, app in enumerate(grp.get("apps", [])):
                icon = app.get("icon", "")
                if icon and os.path.isfile(icon):
                    images[f"tile_{gi}:{ti}"] = icon

        return images

    @staticmethod
    def _copy_as_webp(src_path: str, dest_dir: str, basename: str) -> str | None:
        """Copy *src_path* into *dest_dir* as ``<basename>.webp``.

        Returns the absolute path to the new webp file, or ``None`` on failure.
        """
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, f"{basename}.webp")
        pix = QPixmap(src_path)
        if pix.isNull():
            return None
        if pix.save(dest, "WEBP", 85):
            return os.path.abspath(dest)
        return None

    def save_current_skin(self) -> None:
        """Prompt for a name and save the current settings as a theme.

        All referenced images are copied into the theme's asset directory
        as webp, so the theme is immune to original file deletion and can
        be shared with others.
        """
        name, ok = QInputDialog.getText(
            self, "Save Skin", "Skin name:"
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        slug = self._sanitize_slug(name)

        AssetManager.ensure_directories()
        theme_asset_dir = os.path.join(AssetManager.THEMES_DIR, slug)

        # --- Copy all referenced images into the theme's asset dir ---
        images = self._collect_theme_images()
        copied: dict[str, str] = {}  # original_path -> new_webp_path
        for key, src_path in images.items():
            dest = self._copy_as_webp(src_path, theme_asset_dir, key)
            if dest:
                copied[src_path] = dest

        settings = self._settings["settings"]
        sb = self._settings.get("start_btn", {})

        # Update wallpaper path
        bg_val = settings.get("background_value", "")
        if bg_val in copied:
            bg_val = copied[bg_val]

        # Update SB icon path
        sb_icon_val = sb.get("icon_val", "")
        if sb.get("icon_type") == "image" and sb_icon_val in copied:
            sb_icon_val = copied[sb_icon_val]

        theme = {
            "name": name,
            "slug": slug,
            "background_type": settings.get("background_type", "color"),
            "background_value": bg_val,
            "background_color": settings.get("background_color", "#1d1d1d"),
            "background_opacity": settings.get("background_opacity", 100),
            "default_tile_color": settings.get("default_tile_color", "#00a300"),
            "appbar_accent_color": settings.get("appbar_accent_color", "#ffffff"),
            "tile_size": settings.get("tile_size", 140),
            "group_columns": settings.get("group_columns", 2),
            "tile_radius": settings.get("tile_radius", 0),
            "tile_alpha": settings.get("tile_alpha", 255),
            "icon_theme": settings.get("icon_theme", "default_theme"),
            # AppBar overrides
            "appbar_show_labels": settings.get("appbar_show_labels", True),
            "appbar_tint_icons": settings.get("appbar_tint_icons", True),
            "appbar_icon_spacing": settings.get("appbar_icon_spacing", 4),
            "appbar_dock_bar": settings.get("appbar_dock_bar", False),
            "appbar_dock_color": settings.get(
                "appbar_dock_color",
                settings.get("appbar_accent_color", "#00a300"),
            ),
            # Start button overrides
            "sb_visible": sb.get("visible", True),
            "sb_autohide": sb.get("autohide", False),
            "sb_position": sb.get("position", "Bottom Left"),
            "sb_size": sb.get("size", 60),
            "sb_icon_type": sb.get("icon_type", "text"),
            "sb_icon_val": sb_icon_val,
            "sb_color": sb.get("color", ""),
        }

        # Bundle per-tile color/icon overrides (with updated icon paths)
        tile_overrides = {}
        for gi, grp in enumerate(self.parent_window.config.get("groups", [])):
            for ti, app in enumerate(grp.get("apps", [])):
                key = f"{gi}:{ti}"
                override = {}
                if app.get("color"):
                    override["color"] = app["color"]
                icon = app.get("icon", "")
                if icon:
                    override["icon"] = copied.get(icon, icon)
                if override:
                    tile_overrides[key] = override
        theme["tile_overrides"] = tile_overrides

        # If a non-default icon pack is active, copy its SVGs into the theme
        icon_theme_name = settings.get("icon_theme", "default_theme")
        if icon_theme_name and icon_theme_name != "default_theme":
            icon_src = os.path.join(AssetManager.THEMES_DIR, icon_theme_name)
            if os.path.isdir(icon_src):
                icons_dest = os.path.join(theme_asset_dir, "icons")
                for f in os.listdir(icon_src):
                    if f.endswith(".svg"):
                        shutil.copy2(os.path.join(icon_src, f), os.path.join(icons_dest, f))
                theme["icon_theme_embedded"] = True

        themes: list[dict] = self.parent_window.config.setdefault("themes", [])
        for i, t in enumerate(themes):
            if t.get("name") == name:
                themes[i] = theme
                break
        else:
            themes.append(theme)

        config_file = getattr(self.parent_window, "config_file", "")
        if config_file:
            save_config(config_file, self.parent_window.config)

        self.populate_theme_list()

    def delete_selected_theme(self) -> None:
        """Delete the currently selected theme from the list and config."""
        item = self.theme_list.currentItem()
        if item is None:
            QMessageBox.information(
                self, "No Selection", "Select a theme to delete."
            )
            return

        theme = item.data(Qt.ItemDataRole.UserRole)
        name = theme.get("name", "Unnamed")

        answer = QMessageBox.question(
            self,
            "Delete Theme",
            f'Delete theme "{name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        themes: list[dict] = self.parent_window.config.get("themes", [])
        self.parent_window.config["themes"] = [
            t for t in themes if t.get("name") != name
        ]

        config_file = getattr(self.parent_window, "config_file", "")
        if config_file:
            save_config(config_file, self.parent_window.config)

        self.populate_theme_list()

    def apply_theme_from_list(
        self, current: QListWidgetItem, previous: QListWidgetItem
    ) -> None:
        """Apply the selected theme to the local settings copy.

        Parameters
        ----------
        current : QListWidgetItem | None
            The newly selected item.
        previous : QListWidgetItem | None
            The previously selected item (unused).
        """
        if current is None:
            return
        theme: dict = current.data(Qt.ItemDataRole.UserRole)
        if not theme:
            return

        settings = self._settings["settings"]
        for key in (
            "background_type",
            "background_value",
            "background_color",
            "background_opacity",
            "default_tile_color",
            "appbar_accent_color",
            "tile_size",
            "group_columns",
            "tile_radius",
            "tile_alpha",
            "icon_theme",
            "appbar_show_labels",
            "appbar_tint_icons",
            "appbar_icon_spacing",
            "appbar_dock_bar",
            "appbar_dock_color",
            "appbar_alignment",
            "appbar_dock_opacity",
        ):
            if key in theme:
                settings[key] = theme[key]

        # Sync UI widgets
        self.bg_type_combo.setCurrentText(
            settings.get("background_type", "color")
        )
        self.bg_path_input.setText(settings.get("background_value", ""))
        self.bg_opacity_slider.setValue(settings.get("background_opacity", 100))
        self.tile_size_slider.setValue(settings.get("tile_size", 140))
        self.columns_spin.setValue(settings.get("group_columns", 2))
        self.corner_radius_slider.setValue(settings.get("tile_radius", 0))
        self.tile_opacity_slider.setValue(
            settings.get("tile_alpha", 255) * 100 // 255
        )
        idx = self.icon_theme_combo.findText(settings.get("icon_theme", ""))
        if idx >= 0:
            self.icon_theme_combo.setCurrentIndex(idx)
        idx = self.icon_pack_combo.findText(settings.get("icon_theme", ""))
        if idx >= 0:
            self.icon_pack_combo.setCurrentIndex(idx)

        # Apply start button overrides from theme
        sb = self._settings.setdefault("start_btn", {})
        for key, sb_key in (
            ("sb_visible", "visible"),
            ("sb_autohide", "autohide"),
            ("sb_position", "position"),
            ("sb_size", "size"),
            ("sb_icon_type", "icon_type"),
            ("sb_icon_val", "icon_val"),
            ("sb_color", "color"),
        ):
            if key in theme:
                sb[sb_key] = theme[key]

        # Sync SB UI widgets
        self.sb_visible_cb.setChecked(sb.get("visible", True))
        self.sb_autohide_cb.setChecked(sb.get("autohide", False))
        self.sb_position_combo.setCurrentText(sb.get("position", "Bottom Left"))
        self.sb_size_slider.setValue(sb.get("size", 60))
        self.sb_icon_type_combo.setCurrentText(sb.get("icon_type", "text"))
        self.sb_icon_input.setText(sb.get("icon_val", ""))

        # Sync AppBar widgets
        self.appbar_show_labels_cb.setChecked(
            settings.get("appbar_show_labels", True)
        )
        self.appbar_tint_icons_cb.setChecked(
            settings.get("appbar_tint_icons", True)
        )
        self.appbar_icon_spacing_slider.setValue(
            settings.get("appbar_icon_spacing", 4)
        )
        self.appbar_dock_bar_cb.setChecked(
            settings.get("appbar_dock_bar", False)
        )
        idx = self.appbar_alignment_combo.findText(
            settings.get("appbar_alignment", "Left")
        )
        if idx >= 0:
            self.appbar_alignment_combo.setCurrentIndex(idx)
        self.appbar_dock_opacity_slider.setValue(
            settings.get("appbar_dock_opacity", 95)
        )

        # Store pending tile overrides for save_and_close
        self._pending_tile_overrides = theme.get("tile_overrides", {})

        self._sync_color_buttons()

    def export_skin(self) -> None:
        """Export current appearance to a self-contained .skin file (ZIP).

        All referenced images are bundled as webp inside the archive,
        making it safe to share and immune to original file deletion.
        """
        import tempfile

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Skin", os.path.expanduser("~"), "Skin files (*.skin)"
        )
        if not path:
            return

        name = os.path.splitext(os.path.basename(path))[0]
        slug = self._sanitize_slug(name)

        # Collect and copy images to a temp dir
        images = self._collect_theme_images()
        with tempfile.TemporaryDirectory() as tmp:
            assets_dir = os.path.join(tmp, "assets")
            copied: dict[str, str] = {}
            for key, src_path in images.items():
                dest = self._copy_as_webp(src_path, assets_dir, key)
                if dest:
                    copied[src_path] = dest

            settings = dict(self._settings["settings"])
            sb = dict(self._settings.get("start_btn", {}))

            bg_val = settings.get("background_value", "")
            if bg_val in copied:
                settings["background_value"] = os.path.basename(copied[bg_val])

            if sb.get("icon_type") == "image":
                sb_val = sb.get("icon_val", "")
                if sb_val in copied:
                    sb["icon_val"] = os.path.basename(copied[sb_val])

            # If a non-default icon pack is active, copy its SVGs to assets
            icon_theme_name = settings.get("icon_theme", "default_theme")
            if icon_theme_name and icon_theme_name != "default_theme":
                icon_src = os.path.join(AssetManager.THEMES_DIR, icon_theme_name)
                if os.path.isdir(icon_src):
                    icons_assets = os.path.join(assets_dir, "icons")
                    os.makedirs(icons_assets, exist_ok=True)
                    for f in os.listdir(icon_src):
                        if f.endswith(".svg"):
                            shutil.copy2(os.path.join(icon_src, f), os.path.join(icons_assets, f))

            skin_data = {
                "name": name,
                "slug": slug,
                "settings": settings,
                "start_btn": sb,
                "assets_dir": "assets",
            }

            # Write skin.json to temp
            json_path = os.path.join(tmp, "skin.json")
            with open(json_path, "w") as f:
                json.dump(skin_data, f, indent=2)

            # Zip everything
            try:
                with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.write(json_path, "skin.json")
                    for root, dirs, files in os.walk(assets_dir):
                        for fname in files:
                            fpath = os.path.join(root, fname)
                            arcname = os.path.join("assets", fname)
                            zf.write(fpath, arcname)
            except OSError as exc:
                QMessageBox.critical(
                    self, "Export Failed", f"Could not write file:\n{exc}"
                )
                return

        QMessageBox.information(
            self, "Exported",
            f"Skin exported to:\n{path}\n\n"
            "It contains all images as webp and can be shared."
        )

    def import_skin(self) -> None:
        """Load appearance from a .skin file (self-contained ZIP or legacy JSON).

        Assets are extracted into the theme's directory so they survive
        independently of the original source files.
        """
        import tempfile

        path, _ = QFileDialog.getOpenFileName(
            self, "Import Skin", os.path.expanduser("~"), "Skin files (*.skin)"
        )
        if not path:
            return

        # Try ZIP first (new format), fall back to JSON (legacy)
        skin = None
        is_zip = False
        try:
            with zipfile.ZipFile(path, "r") as zf:
                is_zip = True
                with zf.open("skin.json") as f:
                    skin = json.loads(f.read().decode("utf-8"))
        except (zipfile.BadZipFile, KeyError):
            pass

        if not is_zip:
            try:
                with open(path, "r") as f:
                    skin = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                QMessageBox.critical(
                    self, "Import Failed", f"Could not read file:\n{exc}"
                )
                return

        if not skin:
            return

        name = skin.get("name", "Imported")
        slug = skin.get("slug", self._sanitize_slug(name))

        # Extract assets if ZIP
        if is_zip:
            AssetManager.ensure_directories()
            theme_asset_dir = os.path.join(AssetManager.THEMES_DIR, slug)
            os.makedirs(theme_asset_dir, exist_ok=True)
            try:
                with zipfile.ZipFile(path, "r") as zf:
                    for member in zf.namelist():
                        if member.startswith("assets/") and not member.endswith("/"):
                            fname = os.path.basename(member)
                            dest = os.path.join(theme_asset_dir, fname)
                            with zf.open(member) as src:
                                with open(dest, "wb") as dst:
                                    dst.write(src.read())
            except OSError as exc:
                QMessageBox.critical(
                    self, "Import Failed", f"Could not extract assets:\n{exc}"
                )
                return

            # Update paths to point to extracted assets
            settings = skin.get("settings", {})
            for key in ("background_value",):
                val = settings.get(key, "")
                if val and not os.path.isabs(val):
                    settings[key] = os.path.join(theme_asset_dir, val)

            sb = skin.get("start_btn", {})
            if sb.get("icon_type") == "image":
                val = sb.get("icon_val", "")
                if val and not os.path.isabs(val):
                    sb["icon_val"] = os.path.join(theme_asset_dir, val)

            # Restore icon pack from extracted assets/icons if present
            icons_extracted = os.path.join(theme_asset_dir, "icons")
            if os.path.isdir(icons_extracted) and os.listdir(icons_extracted):
                icon_pack_slug = f"{slug}_icons"
                icon_pack_dir = os.path.join(AssetManager.THEMES_DIR, icon_pack_slug)
                os.makedirs(icon_pack_dir, exist_ok=True)
                for f in os.listdir(icons_extracted):
                    if f.endswith(".svg"):
                        shutil.copy2(
                            os.path.join(icons_extracted, f),
                            os.path.join(icon_pack_dir, f),
                        )
                settings["icon_theme"] = icon_pack_slug

        if "settings" in skin:
            self.parent_window.config["settings"].update(skin["settings"])
        if "start_btn" in skin:
            self.parent_window.config["start_btn"] = skin["start_btn"]
        self.parent_window.save_config()
        self.parent_window.apply_background()
        self.parent_window.refresh_ui()
        if hasattr(self.parent_window, "floating_btn"):
            self.parent_window.floating_btn.apply_settings()

        QMessageBox.information(
            self, "Imported",
            f'Skin "{name}" has been applied.\n'
            "Images were extracted into the theme's asset directory."
        )
        self.close()

    def export_theme(self) -> None:
        """Export the selected theme to a JSON file."""
        item = self.theme_list.currentItem()
        if item is None:
            QMessageBox.information(
                self, "No Selection", "Select a theme to export."
            )
            return

        theme = item.data(Qt.ItemDataRole.UserRole)
        if not theme:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Theme",
            os.path.expanduser(f"~/{theme.get('name', 'theme')}.json"),
            "JSON Files (*.json)",
        )
        if not path:
            return

        try:
            with open(path, "w") as f:
                json.dump(theme, f, indent=2)
            QMessageBox.information(
                self, "Exported", f"Theme saved to:\n{path}"
            )
        except OSError as exc:
            QMessageBox.critical(
                self, "Export Failed", f"Could not write file:\n{exc}"
            )

    def import_theme(self) -> None:
        """Import a theme from a JSON file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Theme",
            os.path.expanduser("~"),
            "JSON Files (*.json)",
        )
        if not path:
            return

        try:
            with open(path, "r") as f:
                theme = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            QMessageBox.critical(
                self, "Import Failed", f"Could not read file:\n{exc}"
            )
            return

        if not isinstance(theme, dict) or "name" not in theme:
            QMessageBox.critical(
                self,
                "Invalid Theme",
                "The selected file does not contain a valid theme.",
            )
            return

        themes: list[dict] = self.parent_window.config.setdefault("themes", [])
        name = theme.get("name", "Imported")
        # Replace if name already exists
        for i, t in enumerate(themes):
            if t.get("name") == name:
                themes[i] = theme
                break
        else:
            themes.append(theme)

        config_file = getattr(self.parent_window, "config_file", "")
        if config_file:
            save_config(config_file, self.parent_window.config)

        self.populate_theme_list()
        QMessageBox.information(
            self,
            "Imported",
            f'Theme "{name}" has been imported.',
        )

    def reset_defaults(self) -> None:
        """Reset all settings to factory defaults after user confirmation."""
        answer = QMessageBox.warning(
            self,
            "Reset to Defaults",
            "This will reset all settings to their default values.\n"
            "This action cannot be undone.\n\n"
            "Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        from lumex8.config import DEFAULT_CONFIG

        self._settings = {
            "settings": dict(DEFAULT_CONFIG.get("settings", {})),
            "start_btn": dict(DEFAULT_CONFIG.get("start_btn", {})),
        }

        settings = self._settings["settings"]
        sb = self._settings["start_btn"]

        # Re-sync all UI widgets with defaults
        self.bg_type_combo.setCurrentText(settings.get("background_type", "color"))
        self.bg_path_input.setText(settings.get("background_value", ""))
        self.bg_opacity_slider.setValue(settings.get("background_opacity", 100))
        self.bg_color_btn.setStyleSheet(
            f"background-color: {settings.get('background_color', '#1d1d1d')}; "
            "border: 1px solid #555; border-radius: 4px;"
        )

        self.bg_slideshow_input.setText(settings.get("slideshow_folder", ""))
        self.ss_interval_spin.setValue(settings.get("slideshow_interval", 60))

        self.tile_size_slider.setValue(settings.get("tile_size", 140))
        self.columns_spin.setValue(settings.get("group_columns", 2))
        self.corner_radius_slider.setValue(settings.get("tile_radius", 0))
        self.tile_opacity_slider.setValue(settings.get("tile_alpha", 255) * 100 // 255)

        self.sb_visible_cb.setChecked(sb.get("visible", True))
        self.sb_autohide_cb.setChecked(sb.get("autohide", False))
        self.sb_position_combo.setCurrentText(sb.get("position", "Bottom Left"))
        self.sb_size_slider.setValue(sb.get("size", 60))
        self.sb_icon_type_combo.setCurrentText(sb.get("icon_type", "text"))
        self.sb_icon_input.setText(sb.get("icon_val", "\u2756"))

        # AppBar fields
        self.appbar_show_labels_cb.setChecked(
            settings.get("appbar_show_labels", True)
        )
        self.appbar_tint_icons_cb.setChecked(
            settings.get("appbar_tint_icons", True)
        )
        self.appbar_icon_spacing_slider.setValue(
            settings.get("appbar_icon_spacing", 4)
        )
        self.appbar_dock_bar_cb.setChecked(
            settings.get("appbar_dock_bar", False)
        )
        idx = self.appbar_alignment_combo.findText(
            settings.get("appbar_alignment", "Left")
        )
        if idx >= 0:
            self.appbar_alignment_combo.setCurrentIndex(idx)

        # System tab fields
        self.hotkey_recorder.set_hotkey(settings.get("global_hotkey", "<cmd>+p"))
        self.edit_hotkey_recorder.set_hotkey(settings.get("edit_hotkey", ""))
        self.gamepad_recorder.set_button(settings.get("gamepad_hotkey", ""))
        icon_theme = settings.get("icon_theme", "default_theme")
        idx = self.icon_theme_combo.findText(icon_theme)
        if idx >= 0:
            self.icon_theme_combo.setCurrentIndex(idx)
        idx = self.icon_pack_combo.findText(icon_theme)
        if idx >= 0:
            self.icon_pack_combo.setCurrentIndex(idx)

        # Terminal combo
        term_target = settings.get("terminal_app", "gnome-terminal")
        for i in range(self.terminal_combo.count()):
            item_data = self.terminal_combo.itemData(i)
            if item_data and item_data[0] == term_target:
                self.terminal_combo.setCurrentIndex(i)
                break

        # Title fields
        self.title_text_input.setText(settings.get("title_text", ""))
        self.title_text_input.setPlaceholderText(os.getlogin())
        idx = self.title_alignment_combo.findText(settings.get("title_alignment", "Left"))
        if idx >= 0:
            self.title_alignment_combo.setCurrentIndex(idx)

        self._sync_color_buttons()

        QMessageBox.information(
            self, "Reset Complete", "All settings have been reset to defaults."
        )

    # ------------------------------------------------------------------
    # Icon editor helpers (AppBar icon picker in Themes tab)
    # ------------------------------------------------------------------
    def _toggle_icon_editor(self) -> None:
        """Show/hide the in-line icon editor section."""
        visible = not self.icon_editor_widget.isVisible()
        self.icon_editor_widget.setVisible(visible)
        arrow = "\u25bc" if visible else "\u25b6"
        self.icons_section_btn.setText(f"  {arrow}  Icons")

    def _on_icon_theme_combo_changed(self, theme_name: str) -> None:
        """Sync the Appearance-tab icon_pack_combo when Themes-tab combo changes."""
        if hasattr(self, "icon_pack_combo"):
            idx = self.icon_pack_combo.findText(theme_name)
            if idx >= 0:
                self.icon_pack_combo.blockSignals(True)
                self.icon_pack_combo.setCurrentIndex(idx)
                self.icon_pack_combo.blockSignals(False)
        # Update live icon editor thumbnails
        if hasattr(self, "icon_editor_widget"):
            self._refresh_icon_editor_thumbs()

    def _get_icon_source_path(self, name: str) -> str:
        """Return the filesystem path for icon *name*."""
        if name in self._custom_icon_paths:
            return self._custom_icon_paths[name]
        theme_name = self.icon_theme_combo.currentText()
        if theme_name and theme_name != "default_theme":
            cand = os.path.join(AssetManager.THEMES_DIR, theme_name, f"{name}.svg")
            if os.path.exists(cand):
                return cand
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "icons", f"{name}.svg",
        )

    def _refresh_icon_editor_thumbs(self) -> None:
        """Refresh the 5 AppBar icon buttons from current sources."""
        for name, btn in self.icon_buttons.items():
            path = self._get_icon_source_path(name)
            if os.path.exists(path):
                pix = QPixmap(path).scaled(
                    40, 40,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                btn.setIcon(QIcon(pix))
            else:
                btn.setIcon(QIcon())

    def _pick_appbar_icon(self, name: str) -> None:
        """Open a file dialog to replace the selected AppBar icon."""
        path, _ = QFileDialog.getOpenFileName(
            self, f"Replace {name} icon",
            os.path.expanduser("~"),
            "Images (*.svg *.png *.webp *.jpg *.jpeg *.bmp)",
        )
        if not path or not os.path.exists(path):
            return
        self._custom_icon_paths[name] = path
        self._refresh_icon_editor_thumbs()

    def _save_icon_pack_from_editor(self) -> None:
        """Save the current icon editor state as a new icon pack."""
        if not self._custom_icon_paths:
            QMessageBox.information(
                self, "No Changes",
                "No icons have been changed. Pick some icons first."
            )
            return
        name, ok = QInputDialog.getText(
            self, "Save Icon Pack", "Pack name:",
        )
        if not ok or not name.strip():
            return
        import shutil
        slug = self._sanitize_slug(name.strip())
        AssetManager.ensure_directories()
        pack_dir = os.path.join(AssetManager.THEMES_DIR, slug)
        os.makedirs(pack_dir, exist_ok=True)
        # Copy all 5 icons, using custom or source
        for icon_name in ("cmd_unpin", "cmd_edit", "cmd_color", "cmd_icon", "cmd_resize"):
            src = self._get_icon_source_path(icon_name)
            ext = os.path.splitext(src)[1] or ".svg"
            shutil.copy2(src, os.path.join(pack_dir, f"{icon_name}{ext}"))
        # Refresh combos and select the new pack
        self._populate_icon_themes_combo(self.icon_pack_combo)
        idx = self.icon_pack_combo.findText(slug)
        if idx >= 0:
            self.icon_pack_combo.setCurrentIndex(idx)
        self._populate_icon_themes()
        QMessageBox.information(self, "Saved", f"Icon pack '{name.strip()}' saved.")

    def _reset_icon_editor(self) -> None:
        """Clear custom icon paths and revert to default thumbnails."""
        self._custom_icon_paths.clear()
        idx = self.icon_theme_combo.findText("default_theme")
        if idx >= 0:
            self.icon_theme_combo.setCurrentIndex(idx)
        self._refresh_icon_editor_thumbs()

    # ------------------------------------------------------------------
    # Icon pack helpers
    # ------------------------------------------------------------------
    def _populate_icon_themes_combo(self, combo: QComboBox) -> None:
        """Populate *combo* with icon theme names from THEMES_DIR."""
        current = self._settings["settings"].get("icon_theme", "default_theme")
        combo.clear()
        combo.addItem("default_theme")
        if os.path.isdir(AssetManager.THEMES_DIR):
            for entry in sorted(os.listdir(AssetManager.THEMES_DIR)):
                theme_path = os.path.join(AssetManager.THEMES_DIR, entry)
                if os.path.isdir(theme_path):
                    combo.addItem(entry)
        idx = combo.findText(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _on_icon_pack_combo_changed(self, pack_name: str) -> None:
        """Update preview and sync the Themes-tab combo."""
        if not hasattr(self, "icon_theme_combo"):
            return
        idx = self.icon_theme_combo.findText(pack_name)
        if idx >= 0:
            self.icon_theme_combo.setCurrentIndex(idx)
        self._build_icon_pack_preview()

    def _build_icon_pack_preview(self) -> None:
        """Rebuild icon preview thumbnails from the selected pack."""
        while self.icon_pack_preview_layout.count():
            item = self.icon_pack_preview_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        pack_name = self.icon_pack_combo.currentText()
        if pack_name == "default_theme":
            pack_dir = AssetManager.SYSTEM_DIR
        else:
            pack_dir = os.path.join(AssetManager.THEMES_DIR, pack_name)

        if not os.path.isdir(pack_dir):
            return

        icons = sorted(
            f for f in os.listdir(pack_dir)
            if f.startswith("cmd_") and f.endswith(".svg")
        )
        for icon_file in icons[:8]:
            path = os.path.join(pack_dir, icon_file)
            lbl = QLabel()
            pix = QPixmap(path)
            if not pix.isNull():
                scaled = pix.scaled(
                    32, 32,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                lbl.setPixmap(scaled)
            else:
                lbl.setText(icon_file.replace(".svg", ""))
            lbl.setToolTip(icon_file)
            lbl.setFixedSize(36, 36)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.icon_pack_preview_layout.addWidget(lbl)

    def _save_icon_pack(self) -> None:
        """Duplicate the currently selected icon pack under a new name."""
        current = self.icon_pack_combo.currentText()
        name, ok = QInputDialog.getText(
            self, "Save Icon Pack",
            f'Save "{current}" as new pack name:',
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        # Prevent overwriting existing packs
        existing = [
            self.icon_pack_combo.itemText(i)
            for i in range(self.icon_pack_combo.count())
        ]
        if name in existing:
            QMessageBox.warning(
                self, "Name Taken",
                f'A pack named "{name}" already exists.',
            )
            return
        slug = self._sanitize_slug(name)
        if current == "default_theme":
            src = AssetManager.SYSTEM_DIR
        else:
            src = os.path.join(AssetManager.THEMES_DIR, current)
        dst = os.path.join(AssetManager.THEMES_DIR, slug)
        try:
            shutil.copytree(src, dst, dirs_exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(
                self, "Save Failed", f"Could not copy pack:\n{exc}"
            )
            return
        # Re-populate and select the new pack
        self._populate_icon_themes_combo(self.icon_pack_combo)
        idx = self.icon_pack_combo.findText(slug)
        if idx >= 0:
            self.icon_pack_combo.setCurrentIndex(idx)
        self._populate_icon_themes()

    def _export_icon_pack(self) -> None:
        """Export the currently selected icon pack as a .zip file."""
        pack_name = self.icon_pack_combo.currentText()
        if pack_name == "default_theme":
            src = AssetManager.SYSTEM_DIR
        else:
            src = os.path.join(AssetManager.THEMES_DIR, pack_name)
        if not os.path.isdir(src):
            QMessageBox.information(self, "No Pack", "Select a valid icon pack.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Icon Pack",
            os.path.expanduser(f"~/{pack_name}.zip"),
            "ZIP Files (*.zip)",
        )
        if not path:
            return
        try:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(src):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        arcname = os.path.relpath(fpath, os.path.dirname(src))
                        zf.write(fpath, arcname)
        except OSError as exc:
            QMessageBox.critical(
                self, "Export Failed", f"Could not write file:\n{exc}"
            )
            return
        QMessageBox.information(
            self, "Exported",
            f"Icon pack exported to:\n{path}",
        )

    def _import_icon_pack(self) -> None:
        """Import an icon pack from a .zip file into THEMES_DIR."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Icon Pack",
            os.path.expanduser("~"),
            "ZIP Files (*.zip)",
        )
        if not path:
            return
        # Determine pack name from filename
        basename = os.path.splitext(os.path.basename(path))[0]
        slug = self._sanitize_slug(basename)
        dest = os.path.join(AssetManager.THEMES_DIR, slug)
        try:
            os.makedirs(dest, exist_ok=True)
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(dest)
        except (OSError, zipfile.BadZipFile) as exc:
            QMessageBox.critical(
                self, "Import Failed", f"Could not import pack:\n{exc}"
            )
            # Clean up partial extraction
            if os.path.isdir(dest):
                shutil.rmtree(dest, ignore_errors=True)
            return
        # Refresh combos and select the new pack
        self._populate_icon_themes_combo(self.icon_pack_combo)
        idx = self.icon_pack_combo.findText(slug)
        if idx >= 0:
            self.icon_pack_combo.setCurrentIndex(idx)
        self._populate_icon_themes()
        QMessageBox.information(
            self, "Imported",
            f'Icon pack "{slug}" imported successfully.',
        )
