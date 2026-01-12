import sys
import json
import subprocess
import os
import shutil
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QGridLayout, 
                             QPushButton, QLabel, QVBoxLayout, QHBoxLayout, 
                             QMessageBox, QDialog, QLineEdit, QFileDialog, 
                             QColorDialog, QMenu, QFormLayout, QComboBox, 
                             QSystemTrayIcon, QScrollArea, QInputDialog, QStackedWidget,
                             QListWidget, QListWidgetItem, QTabWidget, QStyleOptionButton,
                             QCheckBox, QSlider, QFrame, QGroupBox, QSizePolicy, QSpinBox)
from PyQt6.QtCore import (Qt, QMimeData, QPoint, QSize, QPropertyAnimation, 
                          QRect, QEasingCurve, pyqtProperty, QEvent, QTimer)
from PyQt6.QtGui import QAction, QPixmap, QFont, QColor, QDrag, QIcon, QPainter, QKeyEvent, QFontMetrics
from pynput import keyboard

# --- GLOBAL CACHE ---
ICON_CACHE = {}

def get_cached_pixmap(path, w, h):
    key = (path, w, h)
    if key in ICON_CACHE: return ICON_CACHE[key]
    if os.path.exists(path):
        pix = QPixmap(path).scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        ICON_CACHE[key] = pix
        return pix
    return None

# --- HELPER: Floating "Start" Button ---
class FloatingStartButton(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        
        self.btn = QPushButton()
        self.btn.clicked.connect(self.safe_toggle)
        self.layout.addWidget(self.btn)
        
        self.apply_settings()

    def safe_toggle(self):
        if self.parent_window:
            self.parent_window.toggle_visibility()

    def apply_settings(self):
        settings = self.parent_window.config.get('start_btn', {
            'visible': True, 'size': 60, 'position': 'Bottom Left', 
            'color': 'rgba(255, 255, 255, 0.2)', 'icon_type': 'text', 'icon_val': '❖'
        })
        
        if not settings.get('visible', True):
            self.hide()
            return
        elif not self.parent_window.isVisible():
            self.show()

        height = settings.get('size', 60)
        pos_str = settings.get('position', 'Bottom Left')
        autohide = settings.get('autohide', False)
        
        icon_type = settings.get('icon_type', 'text')
        icon_val = settings.get('icon_val', '❖')
        
        width = height 
        
        if icon_type == 'text':
            font_size = int(height * 0.5)
            font = QFont("Segoe UI", font_size)
            fm = QFontMetrics(font)
            text_width = fm.horizontalAdvance(icon_val)
            width = max(height, text_width + 30) 
            
        self.setFixedSize(width, height)
        self.btn.setFixedSize(width, height)
        
        screen_geo = QApplication.primaryScreen().geometry()
        
        x = 0
        y = 0
        
        if "Top" in pos_str:
            y = 0
        else: # Bottom
            y = screen_geo.height() - height
            
        if "Left" in pos_str:
            x = 0
        elif "Right" in pos_str:
            x = screen_geo.width() - width
        elif "Center" in pos_str:
            x = (screen_geo.width() - width) // 2
            
        self.move(x, y)
        
        bg_color = settings.get('color', 'rgba(255, 255, 255, 0.2)')
        
        radius = "10px"
        corners = ""
        if "Bottom" in pos_str:
            if "Left" in pos_str: corners = f"border-top-right-radius: {radius};"
            elif "Right" in pos_str: corners = f"border-top-left-radius: {radius};"
            elif "Center" in pos_str: corners = f"border-top-left-radius: {radius}; border-top-right-radius: {radius};"
        else: # Top
            if "Left" in pos_str: corners = f"border-bottom-right-radius: {radius};"
            elif "Right" in pos_str: corners = f"border-bottom-left-radius: {radius};"
            elif "Center" in pos_str: corners = f"border-bottom-left-radius: {radius}; border-bottom-right-radius: {radius};"

        self.btn.setIcon(QIcon()) 
        self.btn.setText("")      
        
        icon_style = ""
        if icon_type == 'image' and os.path.exists(icon_val):
            path_fixed = icon_val.replace('\\', '/')
            icon_style = f"border-image: url({path_fixed}) 0 0 0 0 stretch stretch; padding: 10px;"
        else:
            self.btn.setText(icon_val)
            icon_style = f"font-size: {int(height * 0.5)}px;"

        normal_bg = bg_color
        normal_color = "white"
        
        if autohide:
            normal_bg = "transparent"
            normal_color = "transparent"
            hover_bg = bg_color 
            hover_color = "white"
        else:
            hover_bg = "rgba(229, 20, 0, 0.8)" 
            hover_color = "white"

        self.btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {normal_bg};
                color: {normal_color};
                border: none;
                {corners}
                {icon_style}
            }}
            QPushButton:hover {{ 
                background-color: {hover_bg}; 
                color: {hover_color};
            }}
        """)

# --- HELPER: App Importer ---
class AppImporterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Import Applications")
        self.resize(500, 600)
        self.layout = QVBoxLayout(self)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search apps...")
        self.search_bar.textChanged.connect(self.filter_list)
        self.layout.addWidget(self.search_bar)

        self.list_widget = QListWidget()
        self.layout.addWidget(self.list_widget)
        
        self.icon_check = QCheckBox("Import System Icon")
        self.icon_check.setChecked(True) 
        self.layout.addWidget(self.icon_check)
        
        self.btn_box = QHBoxLayout()
        import_btn = QPushButton("Import")
        import_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        self.btn_box.addWidget(import_btn)
        self.btn_box.addWidget(cancel_btn)
        self.layout.addLayout(self.btn_box)
        
        self.system_apps = []
        self.load_system_apps()

    def load_system_apps(self):
        paths = [
            "/usr/share/applications",
            os.path.expanduser("~/.local/share/applications"),
            "/var/lib/flatpak/exports/share/applications",          
            os.path.expanduser("~/.local/share/flatpak/exports/share/applications"), 
            "/var/lib/snapd/desktop/applications"                   
        ]
        unique_names = set()
        for path in paths:
            if not os.path.exists(path): continue
            
            # Walk strictly (no recursive subfolders to avoid snap junk) or just listdir
            # Using os.walk allows finding apps in subdirs like /kde or /wine
            for root, _, files in os.walk(path):
                for file in files:
                    if file.endswith(".desktop"):
                        try:
                            data = self.parse_desktop_file(os.path.join(root, file))
                            if data:
                                # Use name + exec as unique key to prevent duplicates
                                key = f"{data['name']}|{data['exec']}"
                                if key not in unique_names:
                                    self.system_apps.append(data)
                                    unique_names.add(key)
                        except: pass
                        
        self.system_apps.sort(key=lambda x: x['name'].lower())
        self.populate_list(self.system_apps)

    def parse_desktop_file(self, path):
        name = None
        loc_name = None 
        exec_cmd = None
        icon = None
        no_display = False
        hidden = False
        
        # Flag to track if we are inside the main [Desktop Entry] section
        in_main_section = False
        
        try:
            with open(path, 'r', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'): continue
                    
                    # Check for Section Headers
                    if line.startswith('['):
                        if line == "[Desktop Entry]":
                            in_main_section = True
                            continue
                        else:
                            # If we hit ANY other section (like [Desktop Action...]), STOP reading
                            if in_main_section: 
                                break 
                            else:
                                continue # Skip lines until we find [Desktop Entry]

                    # Only parse lines if we are inside the main section
                    if in_main_section and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()
                        
                        if key == "Name": name = value
                        elif key.startswith("Name["): loc_name = value 
                        elif key == "Exec": exec_cmd = value
                        elif key == "Icon": icon = value
                        elif key == "NoDisplay" and value.lower() == "true": no_display = True
                        elif key == "Hidden" and value.lower() == "true": hidden = True
                        elif key == "Type" and value.lower() != "application": return None 
        except:
            return None

        if no_display or hidden: return None
        
        final_name = name if name else loc_name
        if not final_name or not exec_cmd: return None
        
        # Clean Exec command
        exec_cmd = exec_cmd.split('%')[0].strip()
        
        return {"name": final_name, "exec": exec_cmd, "icon_name": icon, "path": path}

    def populate_list(self, apps):
        self.list_widget.clear()
        for app in apps:
            item = QListWidgetItem(app['name'])
            if app['icon_name']:
                icon = QIcon.fromTheme(app['icon_name'])
                if not icon.isNull(): item.setIcon(icon)
            item.setData(Qt.ItemDataRole.UserRole, app)
            self.list_widget.addItem(item)

    def filter_list(self, text):
        filtered = [app for app in self.system_apps if text.lower() in app['name'].lower()]
        self.populate_list(filtered)

    def get_selected_app(self):
        item = self.list_widget.currentItem()
        if item: return item.data(Qt.ItemDataRole.UserRole)
        return None
    def load_system_apps(self):
        paths = [
            "/usr/share/applications",
            os.path.expanduser("~/.local/share/applications"),
            "/var/lib/flatpak/exports/share/applications",          
            os.path.expanduser("~/.local/share/flatpak/exports/share/applications"), 
            "/var/lib/snapd/desktop/applications"                   
        ]
        unique_names = set()
        for path in paths:
            if not os.path.exists(path): continue
            for file in os.listdir(path):
                if file.endswith(".desktop"):
                    try:
                        data = self.parse_desktop_file(os.path.join(path, file))
                        if data and data['name'] and data['name'] not in unique_names:
                            self.system_apps.append(data)
                            unique_names.add(data['name'])
                    except: pass
        self.system_apps.sort(key=lambda x: x['name'])
        self.populate_list(self.system_apps)
def parse_desktop_file(self, path):
        name = None
        loc_name = None 
        exec_cmd = None
        icon = None
        no_display = False
        hidden = False
        
        # Flag to track if we are inside the main [Desktop Entry] section
        in_main_section = False
        
        with open(path, 'r', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                
                # Check for Section Headers
                if line.startswith('['):
                    if line == "[Desktop Entry]":
                        in_main_section = True
                        continue
                    else:
                        # If we hit ANY other section (like [Desktop Action...]), STOP reading
                        if in_main_section: 
                            break 
                        else:
                            continue # Skip lines until we find [Desktop Entry]

                # Only parse lines if we are inside the main section
                if in_main_section and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if key == "Name": name = value
                    elif key.startswith("Name["): loc_name = value 
                    elif key == "Exec": exec_cmd = value
                    elif key == "Icon": icon = value
                    elif key == "NoDisplay" and value.lower() == "true": no_display = True
                    elif key == "Hidden" and value.lower() == "true": hidden = True
                    elif key == "Type" and value.lower() != "application": return None 

        if no_display or hidden: return None
        
        final_name = name if name else loc_name
        if not final_name or not exec_cmd: return None
        
        exec_cmd = exec_cmd.split('%')[0].strip()
        
        return {"name": final_name, "exec": exec_cmd, "icon_name": icon, "path": path}

  def populate_list(self, apps):
        self.list_widget.clear()
        for app in apps:
            item = QListWidgetItem(app['name'])
            if app['icon_name']:
                icon = QIcon.fromTheme(app['icon_name'])
                if not icon.isNull(): item.setIcon(icon)
            item.setData(Qt.ItemDataRole.UserRole, app)
            self.list_widget.addItem(item)

   def filter_list(self, text):
        filtered = [app for app in self.system_apps if text.lower() in app['name'].lower()]
        self.populate_list(filtered)

  def get_selected_app(self):
        item = self.list_widget.currentItem()
        if item: return item.data(Qt.ItemDataRole.UserRole)
        return None

# --- HELPER: App Editor Dialog ---
class AppEditorDialog(QDialog):
    def __init__(self, parent=None, parent_window=None, app_data=None):
        super().__init__(parent)
        self.parent_window = parent_window
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Properties")
        self.setFixedWidth(400)
        self.app_data = app_data or {}
        
        layout = QFormLayout(self)
        
        self.name_input = QLineEdit(self.app_data.get('name', ''))
        layout.addRow("Name:", self.name_input)
        
        # 1. Primary Mode Selection
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Run Application", "Special Tile"])
        self.mode_combo.currentTextChanged.connect(self.refresh_layout)
        layout.addRow("Tile Mode:", self.mode_combo)

        # 2. Special Function Selection (Hidden by default)
        self.special_combo = QComboBox()
        self.special_combo.addItems(["Show Desktop"]) 
        # Future ideas: ["Show Desktop", "Sleep", "Restart", "Shutdown"]
        self.special_label = QLabel("Function:")
        layout.addRow(self.special_label, self.special_combo)

        # 3. Application Paths (Grouped)
        self.grp_paths = QWidget()
        path_layout = QFormLayout(self.grp_paths)
        path_layout.setContentsMargins(0,0,0,0)

        self.script_input = QLineEdit(self.app_data.get('script_path', ''))
        self.script_btn = QPushButton("Browse...")
        self.script_btn.clicked.connect(lambda: self.browse_file(self.script_input))
        self.script_row = QHBoxLayout()
        self.script_row.addWidget(self.script_input)
        self.script_row.addWidget(self.script_btn)
        self.script_container = QWidget()
        self.script_container.setLayout(self.script_row)
        path_layout.addRow("Script/Exec:", self.script_container)

        self.python_input = QLineEdit(self.app_data.get('python_path', sys.executable))
        self.python_btn = QPushButton("Browse...")
        self.python_btn.clicked.connect(lambda: self.browse_file(self.python_input))
        self.python_row = QHBoxLayout()
        self.python_row.addWidget(self.python_input)
        self.python_row.addWidget(self.python_btn)
        self.python_container = QWidget()
        self.python_container.setLayout(self.python_row)
        path_layout.addRow("Python Path:", self.python_container)

        self.import_sys_btn = QPushButton("Import from System/Flatpak...")
        self.import_sys_btn.clicked.connect(self.import_system_app)
        path_layout.addRow("", self.import_sys_btn)
        
        layout.addRow(self.grp_paths)

        # 4. Toggles
        self.full_tile_check = QCheckBox("Full Tile Mode (Image fills tile)")
        self.full_tile_check.setChecked(self.app_data.get('full_tile', False))
        layout.addRow("", self.full_tile_check)
        
        self.wide_tile_check = QCheckBox("Wide Tile Mode (2x1)")
        self.wide_tile_check.setChecked(self.app_data.get('wide_tile', False))
        layout.addRow("", self.wide_tile_check)

        # 5. Color
        self.color_btn = QPushButton("Pick Color")
        default_color = '#00a300'
        if self.parent_window:
             default_color = self.parent_window.config['settings'].get('default_tile_color', '#00a300')
        self.selected_color = self.app_data.get('color', default_color)
        self.color_btn.setStyleSheet(f"background-color: {self.selected_color}")
        self.color_btn.clicked.connect(self.pick_color)
        layout.addRow("Tile Color:", self.color_btn)

        # Footer
        btn_box = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(save_btn)
        btn_box.addWidget(cancel_btn)
        layout.addRow(btn_box)
        
        # Initialize State
        current_type = self.app_data.get('type', 'app')
        if current_type == 'desktop':
            self.mode_combo.setCurrentText("Special Tile")
            self.special_combo.setCurrentText("Show Desktop")
        else:
            self.mode_combo.setCurrentText("Run Application")
            
        self.refresh_layout()

    def refresh_layout(self):
        mode = self.mode_combo.currentText()
        is_app = (mode == "Run Application")
        
        # Toggle visibility
        self.grp_paths.setVisible(is_app)
        self.special_combo.setVisible(not is_app)
        self.special_label.setVisible(not is_app)

    def browse_file(self, line_edit):
        dlg = QFileDialog(self, "Select File")
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        if dlg.exec():
            files = dlg.selectedFiles()
            if files: line_edit.setText(files[0])

    def pick_color(self):
        dlg = QColorDialog(QColor(self.selected_color), self)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        if dlg.exec():
            c = dlg.selectedColor()
            if c.isValid():
                self.selected_color = c.name()
                self.color_btn.setStyleSheet(f"background-color: {self.selected_color}")

    def import_system_app(self):
        dlg = AppImporterDialog(self)
        if dlg.exec():
            app = dlg.get_selected_app()
            if app:
                self.name_input.setText(app['name'])
                self.script_input.setText(app['exec'])
                self.python_input.setText("SYSTEM") 
                if dlg.icon_check.isChecked() and app['icon_name']:
                    self.app_data['icon'] = app['icon_name']

    def get_data(self):
        # Determine internal 'type' based on UI selection
        mode = self.mode_combo.currentText()
        internal_type = 'app'
        
        if mode == "Special Tile":
            special_func = self.special_combo.currentText()
            if special_func == "Show Desktop":
                internal_type = 'desktop'
            # Add elif for future functions here
        
        data = {
            "name": self.name_input.text(),
            "type": internal_type,
            "color": self.selected_color,
            "icon": self.app_data.get('icon', None),
            "full_tile": self.full_tile_check.isChecked(),
            "wide_tile": self.wide_tile_check.isChecked()
        }
        
        if internal_type == 'app':
            data['script_path'] = self.script_input.text()
            data['python_path'] = self.python_input.text()
        else:
            # Special tiles usually don't need paths, but keep keys to avoid errors
            data['script_path'] = ""
            data['python_path'] = ""
            
        # Ensure apps list exists for structure consistency (though specific to folders previously)
        data['apps'] = self.app_data.get('apps', [])
        return data
# --- HELPER: Settings & Themes Dialog ---
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Settings")
        self.resize(500, 450)
        
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        
        # TAB 1: Appearance
        appear_tab = QWidget()
        form = QFormLayout(appear_tab)
        
        self.bg_type = QComboBox()
        self.bg_type.addItems(["color", "image"])
        self.bg_type.setCurrentText(parent.config['settings'].get('background_type', 'color'))
        form.addRow("Background Type:", self.bg_type)
        
        self.bg_value = QLineEdit(parent.config['settings'].get('background_value', ''))
        browse_bg = QPushButton("Browse Image")
        browse_bg.clicked.connect(self.browse_bg)
        form.addRow("Image Path:", self.bg_value)
        form.addRow("", browse_bg)

        self.bg_color_btn = QPushButton("Pick Background Color")
        self.current_bg_color = parent.config['settings'].get('background_color', '#1d1d1d')
        self.bg_color_btn.setStyleSheet(f"background-color: {self.current_bg_color}")
        self.bg_color_btn.clicked.connect(lambda: self.pick_color('bg'))
        form.addRow("Background Color:", self.bg_color_btn)

        form.addRow(QLabel("<b>Tile Settings</b>"))

        self.def_tile_btn = QPushButton("Pick Default Tile Color")
        self.current_tile_color = parent.config['settings'].get('default_tile_color', '#00a300')
        self.def_tile_btn.setStyleSheet(f"background-color: {self.current_tile_color}")
        self.def_tile_btn.clicked.connect(lambda: self.pick_color('tile'))
        form.addRow("Default App Color:", self.def_tile_btn)

        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(80, 240)
        self.size_slider.setValue(parent.config['settings'].get('tile_size', 140))
        self.size_lbl = QLabel(f"{self.size_slider.value()} px")
        self.size_slider.valueChanged.connect(lambda v: self.size_lbl.setText(f"{v} px"))
        form.addRow("Tile Size:", self.size_lbl)
        form.addRow(self.size_slider)
        
        self.col_spin = QSpinBox()
        self.col_spin.setRange(1, 10)
        self.col_spin.setValue(parent.config['settings'].get('group_columns', 2))
        form.addRow("Columns per Group:", self.col_spin)
        
        tabs.addTab(appear_tab, "Appearance")

        # TAB 2: Start Button
        sb_tab = QWidget()
        sb_form = QFormLayout(sb_tab)
        sb_config = parent.config.get('start_btn', {})

        self.sb_visible = QCheckBox("Show Floating Start Button")
        self.sb_visible.setChecked(sb_config.get('visible', True))
        sb_form.addRow(self.sb_visible)
        
        self.sb_autohide = QCheckBox("Invisible until hovered (Auto-Hide)")
        self.sb_autohide.setChecked(sb_config.get('autohide', False))
        sb_form.addRow(self.sb_autohide)

        self.sb_pos = QComboBox()
        self.sb_pos.addItems(["Bottom Left", "Bottom Center", "Bottom Right", "Top Left", "Top Center", "Top Right"])
        self.sb_pos.setCurrentText(sb_config.get('position', 'Bottom Left'))
        sb_form.addRow("Position:", self.sb_pos)

        self.sb_size = QSlider(Qt.Orientation.Horizontal)
        self.sb_size.setRange(30, 100)
        self.sb_size.setValue(sb_config.get('size', 60))
        self.sb_size_lbl = QLabel(f"{self.sb_size.value()} px")
        self.sb_size.valueChanged.connect(lambda v: self.sb_size_lbl.setText(f"{v} px"))
        sb_form.addRow("Height:", self.sb_size_lbl)
        sb_form.addRow(self.sb_size)

        self.sb_icon_type = QComboBox()
        self.sb_icon_type.addItems(["text", "image"])
        self.sb_icon_type.setCurrentText(sb_config.get('icon_type', 'text'))
        sb_form.addRow("Icon Type:", self.sb_icon_type)

        self.sb_icon_val = QLineEdit(sb_config.get('icon_val', '❖'))
        sb_browse = QPushButton("Browse Icon")
        sb_browse.clicked.connect(self.browse_sb_icon)
        sb_form.addRow("Icon/Text:", self.sb_icon_val)
        sb_form.addRow("", sb_browse)

        self.sb_color_btn = QPushButton("Pick Button Color")
        self.current_sb_color = sb_config.get('color', 'rgba(255, 255, 255, 0.2)')
        self.sb_color_btn.setStyleSheet(f"background-color: {self.current_sb_color}")
        self.sb_color_btn.clicked.connect(lambda: self.pick_color('sb'))
        sb_form.addRow("Color:", self.sb_color_btn)

        tabs.addTab(sb_tab, "Start Button")

        # TAB 3: Themes
        theme_tab = QWidget()
        theme_layout = QVBoxLayout(theme_tab)
        theme_layout.addWidget(QLabel("Recent Themes:"))
        self.recent_list = QListWidget()
        self.populate_recent()
        self.recent_list.itemDoubleClicked.connect(self.load_recent_theme)
        theme_layout.addWidget(self.recent_list)
        hbox = QHBoxLayout()
        export_btn = QPushButton("Export Current")
        export_btn.clicked.connect(self.export_theme)
        import_btn = QPushButton("Import Theme")
        import_btn.clicked.connect(self.import_theme)
        hbox.addWidget(export_btn)
        hbox.addWidget(import_btn)
        theme_layout.addLayout(hbox)
        tabs.addTab(theme_tab, "Themes")
        
        layout.addWidget(tabs)
        save_btn = QPushButton("Save & Close")
        save_btn.clicked.connect(self.save_and_close)
        layout.addWidget(save_btn)

    def populate_recent(self):
        recents = self.parent_window.config.get('recent_themes', [])
        for theme in recents:
            self.recent_list.addItem(theme['name'])

    def browse_bg(self):
        dlg = QFileDialog(self, "Select Image")
        dlg.setNameFilter("Images (*.png *.jpg)")
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        if dlg.exec():
            files = dlg.selectedFiles()
            if files:
                self.bg_value.setText(files[0])
                self.bg_type.setCurrentText("image")

    def browse_sb_icon(self):
        dlg = QFileDialog(self, "Select Icon")
        dlg.setNameFilter("Images (*.png *.jpg *.svg)")
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        if dlg.exec():
            files = dlg.selectedFiles()
            if files:
                self.sb_icon_val.setText(files[0])
                self.sb_icon_type.setCurrentText("image")

    def pick_color(self, target):
        initial = '#000000'
        if target == 'bg': initial = self.current_bg_color
        elif target == 'tile': initial = self.current_tile_color
        elif target == 'sb': initial = self.current_sb_color

        dlg = QColorDialog(QColor(initial), self)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        if dlg.exec():
            c = dlg.selectedColor()
            if c.isValid():
                name = c.name()
                if target == 'bg': 
                    self.current_bg_color = name
                    self.bg_color_btn.setStyleSheet(f"background-color: {name}")
                    self.bg_type.setCurrentText("color")
                elif target == 'tile':
                    self.current_tile_color = name
                    self.def_tile_btn.setStyleSheet(f"background-color: {name}")
                elif target == 'sb':
                    name = f"rgba({c.red()},{c.green()},{c.blue()},{c.alpha()/255})"
                    self.current_sb_color = name
                    self.sb_color_btn.setStyleSheet(f"background-color: {name}")

    def get_current_settings(self):
        return {
            "window_title": "Pop Metro Launcher",
            "background_type": self.bg_type.currentText(),
            "background_value": self.bg_value.text(),
            "background_color": self.current_bg_color,
            "default_tile_color": self.current_tile_color,
            "tile_size": self.size_slider.value(),
            "group_columns": self.col_spin.value()
        }

    def get_sb_settings(self):
        return {
            "visible": self.sb_visible.isChecked(),
            "autohide": self.sb_autohide.isChecked(),
            "position": self.sb_pos.currentText(),
            "size": self.sb_size.value(),
            "icon_type": self.sb_icon_type.currentText(),
            "icon_val": self.sb_icon_val.text(),
            "color": self.current_sb_color
        }

    def save_and_close(self):
        self.parent_window.config['settings'] = self.get_current_settings()
        self.parent_window.config['start_btn'] = self.get_sb_settings()
        self.parent_window.save_config()
        self.parent_window.apply_background()
        self.parent_window.refresh_ui()
        self.parent_window.floating_btn.apply_settings()
        self.accept()

    def export_theme(self):
        dlg = QFileDialog(self, "Export Theme")
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dlg.setDefaultSuffix("json")
        dlg.setNameFilter("JSON (*.json)")
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        if dlg.exec():
            fname = dlg.selectedFiles()[0]
            theme_data = {
                "name": os.path.basename(fname),
                "settings": self.get_current_settings(),
                "start_btn": self.get_sb_settings()
            }
            with open(fname, 'w') as f:
                json.dump(theme_data, f)
            self.show_message("Success", "Theme exported.")

    def import_theme(self):
        dlg = QFileDialog(self, "Import Theme")
        dlg.setNameFilter("JSON (*.json)")
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        if dlg.exec():
            fname = dlg.selectedFiles()[0]
            try:
                with open(fname, 'r') as f:
                    data = json.load(f)
                    if 'settings' in data:
                        self.parent_window.config['settings'] = data['settings']
                    if 'start_btn' in data:
                        self.parent_window.config['start_btn'] = data['start_btn']
                    
                    self.parent_window.add_recent_theme(data.get('name','Theme'), data)
                    self.parent_window.save_config()
                    self.parent_window.apply_background()
                    self.parent_window.refresh_ui()
                    self.parent_window.floating_btn.apply_settings()
                    self.close()
            except Exception as e:
                self.show_message("Error", str(e))

    def show_message(self, title, text):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        msg.exec()

    def load_recent_theme(self, item):
        name = item.text()
        recents = self.parent_window.config.get('recent_themes', [])
        for theme in recents:
            if theme['name'] == name:
                if 'settings' in theme['settings']:
                     self.parent_window.config['settings'] = theme['settings']['settings']
                     self.parent_window.config['start_btn'] = theme['settings'].get('start_btn', {})
                else:
                     self.parent_window.config['settings'] = theme['settings']
                
                self.parent_window.save_config()
                self.parent_window.apply_background()
                self.parent_window.refresh_ui()
                self.parent_window.floating_btn.apply_settings()
                self.close()
                break

# --- CORE: Animated Tile Widget ---
class MetroTile(QPushButton):
    def __init__(self, app_data, parent_window, group_index, item_index, is_add=False, is_back=False):
        super().__init__()
        self.app_data = app_data
        self.parent_window = parent_window
        self.group_index = group_index 
        self.item_index = item_index
        self.is_add = is_add
        self.is_back = is_back
        
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        self.drag_start_position = None
        self.drop_target_mode = None
        self._last_drag_target_mode = None 
        self.insert_side = 'left' 

        self._scale = 1.0
        self.anim = QPropertyAnimation(self, b"scale_prop")
        self.anim.setDuration(100) 
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)

        self.init_widgets()
        self.update_fixed_size() 
        self.update_style()

    def update_fixed_size(self):
        size = self.parent_window.config['settings'].get('tile_size', 140)
        spacing = 4 
        
        is_wide = self.app_data.get('wide_tile', False)
        
        cols = self.parent_window.config['settings'].get('group_columns', 2)
        if cols < 2: is_wide = False

        width = size
        height = size
        
        if is_wide:
            width = (size * 2) + spacing
            
        self.setFixedSize(width, height)

    def get_scale_prop(self): return self._scale
    def set_scale_prop(self, val):
        self._scale = val
        self.update() 
    scale_prop = pyqtProperty(float, get_scale_prop, set_scale_prop)

    def init_widgets(self):
        self.icon_label = QLabel(self)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.text_label = QLabel(self)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
        self.text_label.setWordWrap(True)
        self.text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.delete_btn = QPushButton("×", self)
        self.delete_btn.setStyleSheet("background-color: red; color: white; border: none; font-weight: bold; font-size: 16px;")
        self.delete_btn.clicked.connect(self.request_delete)
        self.delete_btn.hide()
        
        self.update_content()

    def update_content(self):
        if self.is_add:
            self.icon_label.setText("➕")
            self.text_label.setText("")
        elif self.is_back:
            # Not used anymore as folders are removed, but kept for safe cleanup
            pass
        else:
            name_text = self.app_data.get('name', 'Unknown')
            self.text_label.setText(name_text)
            self.update_icon_display()

    def update_icon_display(self):
        icon_path = self.app_data.get('icon')
        name = self.app_data.get('name', '??')
        
        size = self.parent_window.config['settings'].get('tile_size', 140)
        is_full = self.app_data.get('full_tile', False)
        
        spacing = 4
        is_wide = self.app_data.get('wide_tile', False)
        cols = self.parent_window.config['settings'].get('group_columns', 2)
        if cols < 2: is_wide = False
        
        target_w = (size * 2) + spacing if is_wide else size
        target_h = size
        
        if not is_full:
            target_w = int(size * 0.5)
            target_h = int(size * 0.5)

        cached_pix = None
        if icon_path:
            cached_pix = get_cached_pixmap(icon_path, target_w, target_h)
        
        if cached_pix:
            if is_full:
                scaled = cached_pix.scaled(target_w, target_h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                x = (scaled.width() - target_w) // 2
                y = (scaled.height() - target_h) // 2
                final_pix = scaled.copy(x, y, target_w, target_h)
                self.icon_label.setPixmap(final_pix)
            else:
                self.icon_label.setPixmap(cached_pix)
            self.icon_label.setText("") 
        elif icon_path and QIcon.hasThemeIcon(icon_path):
            icon = QIcon.fromTheme(icon_path)
            pixmap = icon.pixmap(target_w, target_h)
            self.icon_label.setPixmap(pixmap)
            self.icon_label.setText("")
        else:
            self.icon_label.setPixmap(QPixmap())
            initials = name[:2].upper()
            self.icon_label.setText(initials)
            
        if self.is_add:
            self.icon_label.setStyleSheet(f"font-size: {int(size*0.3)}px; color: #888; background: transparent;")
        else:
            if not self.icon_label.pixmap().isNull():
                 self.icon_label.setStyleSheet("background: transparent;")
            else:
                 self.icon_label.setStyleSheet(f"font-size: {int(size*0.3)}px; font-weight: bold; color: white; background: transparent;")
            
            self.text_label.setStyleSheet(f"font-size: {max(10, int(size*0.09))}px; font-weight: 500; color: white; background: transparent; padding: 2px;")

    def resizeEvent(self, event):
        w = self.width()
        h = self.height()
        
        if self.is_add:
            self.icon_label.setGeometry(0, 0, w, h)
            self.text_label.hide()
        else:
            is_full = self.app_data.get('full_tile', False)
            if is_full:
                self.icon_label.setGeometry(0, 0, w, h)
                self.text_label.hide()
            else:
                text_h = int(h * 0.30)
                icon_h = h - text_h
                self.icon_label.setGeometry(0, 0, w, icon_h)
                self.text_label.setGeometry(5, icon_h, w-10, text_h)
                self.text_label.show()
                
        self.delete_btn.setGeometry(w-30, 0, 25, 25)
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self.rect().center()
        painter.translate(c)
        painter.scale(self._scale, self._scale)
        painter.translate(-c)
        
        def_color = self.parent_window.config['settings'].get('default_tile_color', '#00a300')
        bg_color = QColor(self.app_data.get('color', def_color))
        
        if self.is_add: bg_color = QColor(60, 60, 60)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawRect(self.rect())

        if self.hasFocus(): 
            painter.setPen(QColor(0, 120, 215))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.rect().adjusted(1,1,-1,-1))
            painter.drawRect(self.rect().adjusted(4,4,-4,-4))
            
        # Draw Insertion Line
        if self.drop_target_mode == 'insert' and not self.is_add:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255))
            if self.insert_side == 'left':
                painter.drawRect(0, 0, 4, self.height())
            else:
                painter.drawRect(self.width()-4, 0, 4, self.height())

        painter.end() 

    def enterEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(self._scale)
        self.anim.setEndValue(1.05)
        self.anim.start()
        self.update_style(hover=True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(self._scale)
        self.anim.setEndValue(1.0)
        self.anim.start()
        self.update_style(hover=False)
        super().leaveEvent(event)
    
    def focusInEvent(self, event):
        self.update()
        super().focusInEvent(event)
    def focusOutEvent(self, event):
        self.update()
        super().focusOutEvent(event)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = e.position().toPoint()
        self.anim.stop()
        self.anim.setStartValue(self._scale)
        self.anim.setEndValue(0.95)
        self.anim.start()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        self.anim.stop()
        self.anim.setStartValue(self._scale)
        self.anim.setEndValue(1.0)
        self.anim.start()
        
        if self.rect().contains(e.position().toPoint()):
            self.trigger_action()

    def trigger_action(self):
        if self.is_add: self.parent_window.add_new_item(self.group_index)
        elif not self.parent_window.is_edit_mode:
            if self.app_data.get('type') == 'desktop':
                self.parent_window.toggle_visibility() 
            else:
                self.launch_app()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton): return
        if self.is_add: return
        if self.drag_start_position is None: return

        current_pos = event.position().toPoint()
        if (current_pos - self.drag_start_position).manhattanLength() < QApplication.startDragDistance(): return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(f"{self.group_index}|{self.item_index}")
        drag.setMimeData(mime_data)
        drag.setPixmap(self.grab())
        drag.setHotSpot(current_pos)
        drag.exec(Qt.DropAction.MoveAction)

    def update_style(self, border_color=None, hover=False):
        if self.drop_target_mode == self._last_drag_target_mode and not hover:
            return
        
        self._last_drag_target_mode = self.drop_target_mode
        
        border_css = "border: none;"
        if hover: border_css = "border: 3px solid rgba(255, 255, 255, 0.5);"
        self.setStyleSheet(f"MetroTile {{ background-color: transparent; {border_css} }}")

    def dragEnterEvent(self, event):
        if event.source() and isinstance(event.source(), MetroTile): event.accept()
        else: event.ignore()

    def dragMoveEvent(self, event):
        if event.source() and isinstance(event.source(), MetroTile): 
             pos = event.position().toPoint()
             if pos.x() < self.width() / 2:
                 self.insert_side = 'left'
             else:
                 self.insert_side = 'right'
             
             self.drop_target_mode = 'insert'
             self.update() 
             
             event.setDropAction(Qt.DropAction.MoveAction)
             event.accept()

    def dragLeaveEvent(self, event):
        self.drop_target_mode = None
        self.update() 
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.drop_target_mode = None
        self.update()
        source_tile = event.source()
        if source_tile and source_tile != self:
            if self.is_add:
                 self.parent_window.handle_drop(source_tile.group_index, source_tile.item_index, self.group_index, -1)
            else:
                offset = 0 if self.insert_side == 'left' else 1
                self.parent_window.handle_drop(source_tile.group_index, source_tile.item_index, self.group_index, self.item_index + offset)

    def launch_app(self):
        script = self.app_data.get('script_path')
        python_exe = self.app_data.get('python_path')
        
        if python_exe == "SYSTEM":
            try: 
                subprocess.Popen(script.split())
                self.parent_window.toggle_visibility() 
            except Exception as e: 
                self.show_error(str(e))
            return
            
        if not script or not os.path.exists(script):
            self.show_error(f"Script not found:\n{script}")
            return
            
        cwd = os.path.dirname(script)
        try:
            cmd = ['gnome-terminal', '--', 'bash', '-c', f'"{python_exe}" "{script}"; exec bash']
            subprocess.Popen(cmd, cwd=cwd)
            self.parent_window.toggle_visibility()
        except Exception as e:
            self.show_error(str(e))

    def show_error(self, text):
        msg = QMessageBox(self)
        msg.setWindowTitle("Error")
        msg.setText(text)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        msg.exec()

    def request_delete(self):
        self.parent_window.delete_item(self.group_index, self.item_index)

    def contextMenuEvent(self, event):
        if self.is_add: return
        menu = QMenu(self)
        menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        tile_menu = menu.addMenu("Tile")
        tile_menu.addAction("Change Color", self.change_color)
        tile_menu.addAction("Change Icon", self.change_icon)
        tile_menu.addAction("Remove Icon", self.remove_icon)
        
        menu.addAction("Properties", self.edit_details)
        menu.addSeparator()
        menu.addAction("Delete", self.request_delete)
        
        menu.exec(self.mapToGlobal(event.pos()))

    def change_name(self):
        dlg = QInputDialog(self)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        dlg.setWindowTitle("Rename")
        dlg.setLabelText("Name:")
        dlg.setTextValue(self.app_data['name'])
        if dlg.exec():
            new_name = dlg.textValue()
            if new_name:
                self.app_data['name'] = new_name
                self.text_label.setText(new_name)
                self.parent_window.save_config()

    def change_icon(self):
        dlg = QFileDialog(self, "Select Icon")
        dlg.setNameFilter("Images (*.png *.jpg *.svg)")
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        if dlg.exec():
            files = dlg.selectedFiles()
            if files:
                self.app_data['icon'] = files[0]
                self.update_icon_display()
                self.parent_window.save_config()

    def remove_icon(self):
        self.app_data['icon'] = None
        self.update_icon_display()
        self.parent_window.save_config()

    def change_color(self):
        initial = QColor(self.app_data.get('color', '#000'))
        dlg = QColorDialog(initial, self)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        if dlg.exec():
            color = dlg.selectedColor()
            if color.isValid():
                self.app_data['color'] = color.name()
                self.update() 
                self.parent_window.save_config()

    def edit_details(self):
        dlg = AppEditorDialog(self, self.parent_window, self.app_data)
        if dlg.exec():
            self.app_data.update(dlg.get_data())
            self.parent_window.refresh_ui()
            self.parent_window.save_config()

# --- GROUP WIDGET ---
class GroupWidget(QWidget):
    def __init__(self, parent_window, group_data, group_index):
        super().__init__()
        self.parent_window = parent_window
        self.group_data = group_data
        self.group_index = group_index
        
        tile_size = self.parent_window.config['settings'].get('tile_size', 140)
        spacing = 4
        cols = self.parent_window.config['settings'].get('group_columns', 2)
        width = (tile_size * cols) + (spacing * (cols-1)) + 40 
        self.setFixedWidth(width) 
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 40, 0)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header_layout = QHBoxLayout()
        self.title = QLabel(group_data.get('name', 'Group'))
        self.title.setStyleSheet("color: white; font-size: 20px; font-family: 'Segoe UI Light', sans-serif;")
        header_layout.addWidget(self.title)
        
        if self.parent_window.is_edit_mode:
            del_grp = QPushButton("Del")
            del_grp.setStyleSheet("color: red; background: transparent; border: none;")
            del_grp.clicked.connect(self.delete_self)
            header_layout.addWidget(del_grp)
            
            rename_grp = QPushButton("Ren")
            rename_grp.setStyleSheet("color: #aaa; background: transparent; border: none;")
            rename_grp.clicked.connect(self.rename_self)
            header_layout.addWidget(rename_grp)

        self.main_layout.addLayout(header_layout)

        self.grid_widget = QWidget()
        self.grid = QGridLayout(self.grid_widget)
        self.grid.setSpacing(spacing)
        self.grid.setContentsMargins(0, 10, 0, 0)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.populate_grid()
        self.main_layout.addWidget(self.grid_widget)
        self.main_layout.addStretch()

    def populate_grid(self):
        apps = self.group_data.get('apps', [])
        
        grid_map = {} 
        current_row = 0
        current_col = 0
        max_cols = self.parent_window.config['settings'].get('group_columns', 2)
        
        def is_occupied(r, c):
            return grid_map.get((r,c), False)
        
        def mark_occupied(r, c):
            grid_map[(r,c)] = True

        for i, app in enumerate(apps):
            is_wide = app.get('wide_tile', False)
            if max_cols < 2: is_wide = False
            
            while True:
                if is_wide:
                    if current_col + 1 < max_cols and not is_occupied(current_row, current_col) and not is_occupied(current_row, current_col+1):
                        break
                    else:
                        current_col += 1
                        if current_col >= max_cols:
                            current_col = 0
                            current_row += 1
                else:
                    if not is_occupied(current_row, current_col):
                        break
                    else:
                        current_col += 1
                        if current_col >= max_cols:
                            current_col = 0
                            current_row += 1
            
            tile = MetroTile(app, self.parent_window, self.group_index, i)
            if self.parent_window.is_edit_mode: tile.delete_btn.show()
            
            if is_wide:
                self.grid.addWidget(tile, current_row, current_col, 1, 2)
                mark_occupied(current_row, current_col)
                mark_occupied(current_row, current_col+1)
            else:
                self.grid.addWidget(tile, current_row, current_col, 1, 1)
                mark_occupied(current_row, current_col)
                
        if self.parent_window.is_edit_mode:
            while is_occupied(current_row, current_col):
                current_col += 1
                if current_col >= max_cols:
                    current_col = 0
                    current_row += 1
            add_tile = MetroTile({}, self.parent_window, self.group_index, -1, is_add=True)
            self.grid.addWidget(add_tile, current_row, current_col)

    def delete_self(self):
        msg = QMessageBox(self)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        msg.setWindowTitle("Delete Group")
        msg.setText("Delete this group and all apps inside?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.parent_window.delete_group(self.group_index)

    def rename_self(self):
        dlg = QInputDialog(self)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        dlg.setWindowTitle("Rename Group")
        dlg.setLabelText("Name:")
        dlg.setTextValue(self.group_data['name'])
        if dlg.exec():
            new_name = dlg.textValue()
            if new_name:
                self.group_data['name'] = new_name
                self.title.setText(new_name)
                self.parent_window.save_config()

# --- MAIN WINDOW ---
class LauncherWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_file = 'config.json'
        self.is_edit_mode = False
        
        self.load_config()
        self.init_ui()
        self.setup_tray()
        self.setup_shortcuts()
        
        self.floating_btn = FloatingStartButton(self)
        self.floating_btn.hide()
        
        # Debounce timer for saving
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self._save_to_disk)

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {"settings": {}, "groups": [{"name": "Start", "apps": []}], "recent_themes": []}
        
        if "groups" not in self.config: self.config["groups"] = []
        if "recent_themes" not in self.config: self.config["recent_themes"] = []
        if "settings" not in self.config: self.config["settings"] = {}

    def save_config(self):
        # Trigger debounce save
        self.save_timer.start(2000) 

    def _save_to_disk(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    def closeEvent(self, event):
        self._save_to_disk()
        event.accept()

    def add_recent_theme(self, name, settings_dict):
        recents = self.config.get('recent_themes', [])
        recents = [t for t in recents if t['name'] != name]
        recents.insert(0, {"name": name, "settings": settings_dict})
        self.config['recent_themes'] = recents[:3]
        self._save_to_disk()

    def setup_shortcuts(self):
        try:
            self.hotkey_listener = keyboard.GlobalHotKeys({'<cmd>+p': self.toggle_visibility})
            self.hotkey_listener.start()
        except: pass

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon.fromTheme("applications-system")) 
        menu = QMenu()
        menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        quit_action = QAction("Quit Launcher", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(lambda r: self.toggle_visibility() if r == QSystemTrayIcon.ActivationReason.Trigger else None)

    def toggle_visibility(self):
        if self.isVisible(): 
            self.hide()
            self.floating_btn.apply_settings()
        else: 
            self.showFullScreen()
            self.activateWindow()
            self.floating_btn.hide()

    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.showFullScreen()
        
        self.central_container = QWidget()
        self.setCentralWidget(self.central_container)
        self.apply_background()
        
        layout = QVBoxLayout(self.central_container)
        layout.setContentsMargins(40, 60, 40, 40)
        
        toolbar = QHBoxLayout()
        title_lbl = QLabel("Start")
        title_lbl.setStyleSheet("font-size: 30px; font-weight: 300; color: white; font-family: 'Segoe UI Light';")
        toolbar.addWidget(title_lbl)
        toolbar.addStretch()
        
        self.add_grp_btn = QPushButton("+ Group")
        self.add_grp_btn.clicked.connect(self.add_group)
        self.add_grp_btn.hide()
        self.style_toolbar_btn(self.add_grp_btn)
        toolbar.addWidget(self.add_grp_btn)
        
        self.edit_btn = QPushButton("✎ Edit")
        self.edit_btn.setCheckable(True)
        self.edit_btn.setFixedSize(100, 40)
        self.edit_btn.clicked.connect(self.toggle_edit_mode)
        self.style_toolbar_btn(self.edit_btn)
        toolbar.addWidget(self.edit_btn)
        
        self.cog_btn = QPushButton("⚙")
        self.cog_btn.setFixedSize(50, 40)
        self.cog_btn.clicked.connect(self.open_settings)
        self.style_toolbar_btn(self.cog_btn)
        toolbar.addWidget(self.cog_btn)
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(50, 40)
        self.close_btn.setStyleSheet("background-color: transparent; color: white; font-size: 20px; border: none;")
        self.close_btn.clicked.connect(self.toggle_visibility)
        toolbar.addWidget(self.close_btn)

        layout.addLayout(toolbar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.groups_container = QWidget()
        self.groups_container.setStyleSheet("background: transparent;")
        self.groups_layout = QHBoxLayout(self.groups_container)
        self.groups_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.groups_layout.setSpacing(0)
        self.scroll_area.setWidget(self.groups_container)
        layout.addWidget(self.scroll_area)
        
        self.refresh_ui()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            focus_widget = self.focusWidget()
            if isinstance(focus_widget, QPushButton):
                focus_widget.click() 
                return
        super().keyPressEvent(event)

    def style_toolbar_btn(self, btn):
        btn.setStyleSheet("QPushButton { background-color: rgba(0, 0, 0, 0.5); color: white; border: 1px solid rgba(255,255,255,0.3); font-size: 14px; border-radius: 5px; padding: 5px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.2); } QPushButton:checked { background-color: #e51400; border: none; }")

    def apply_background(self):
        settings = self.config.get('settings', {})
        bg_type = settings.get('background_type', 'color')
        if bg_type == 'image':
            path = settings.get('background_value', '').replace('\\', '/')
            if os.path.exists(path):
                self.central_container.setObjectName("BG")
                # FIX: Use border-image instead of background-size
                self.central_container.setStyleSheet(f"#BG {{ border-image: url({path}) 0 0 0 0 stretch stretch; }}")
                return
        color = settings.get('background_color', '#1d1d1d')
        self.central_container.setStyleSheet(f"background-color: {color};")

    def refresh_ui(self):
        # OPTIMIZATION: Disable updates during rebuild
        self.setUpdatesEnabled(False)
        
        while self.groups_layout.count():
            item = self.groups_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        groups = self.config.get('groups', [])
        for i, grp_data in enumerate(groups):
            grp_widget = GroupWidget(self, grp_data, i)
            self.groups_layout.addWidget(grp_widget)
        self.groups_layout.addStretch()
        
        self.setUpdatesEnabled(True)

    def toggle_edit_mode(self):
        self.is_edit_mode = self.edit_btn.isChecked()
        self.add_grp_btn.setVisible(self.is_edit_mode)
        self.refresh_ui()

    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec(): pass

    def add_group(self):
        dlg = QInputDialog(self)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        dlg.setWindowTitle("New Group")
        dlg.setLabelText("Group Name:")
        if dlg.exec():
            name = dlg.textValue()
            if name:
                self.config['groups'].append({"name": name, "apps": []})
                self.save_config()
                self.refresh_ui()

    def delete_group(self, index):
        del self.config['groups'][index]
        self.save_config()
        self.refresh_ui()

    def add_new_item(self, group_index):
        dlg = AppEditorDialog(self, self)
        if dlg.exec():
            new_data = dlg.get_data()
            if new_data['name']:
                self.config['groups'][group_index]['apps'].append(new_data)
                self.save_config()
                self.refresh_ui()

    def delete_item(self, group_index, item_index):
        msg = QMessageBox(self)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        msg.setWindowTitle("Delete")
        msg.setText("Remove item?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            del self.config['groups'][group_index]['apps'][item_index]
            self.save_config()
            self.refresh_ui()

    def handle_drop(self, src_grp, src_idx, dst_grp, dst_idx):
        def get_list(grp_idx):
            return self.config['groups'][grp_idx]['apps']
        src_list = get_list(src_grp)
        dst_list = get_list(dst_grp)
        item = src_list.pop(src_idx)
        
        # Adjust dst_idx if moving within same group
        if src_grp == dst_grp and src_idx < dst_idx:
            dst_idx -= 1
        
        if dst_idx == -1: 
            dst_list.append(item)
        else:
            dst_list.insert(dst_idx, item)
            
        self.refresh_ui() # Save config deferred to closeEvent/timer

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    window = LauncherWindow()
    sys.exit(app.exec())
