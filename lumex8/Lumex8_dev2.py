# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = [
#     "PyQt6",
#     "pynput",
#     "pygame",
# ]
# ///

import sys
import json
import subprocess
import os
import shutil
import time
import importlib.util
from pathlib import Path

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QGridLayout, 
                             QPushButton, QLabel, QVBoxLayout, QHBoxLayout, 
                             QMessageBox, QDialog, QLineEdit, QFileDialog, 
                             QColorDialog, QMenu, QFormLayout, QComboBox, 
                             QSystemTrayIcon, QScrollArea, QInputDialog, QStackedWidget,
                             QListWidget, QListWidgetItem, QTabWidget, QStyleOptionButton,
                             QCheckBox, QSlider, QFrame, QGroupBox, QSizePolicy, 
                             QSpinBox, QKeySequenceEdit, QToolButton)
from PyQt6.QtCore import (Qt, QMimeData, QPoint, QSize, QPropertyAnimation, 
                          QRect, QEasingCurve, pyqtProperty, QEvent, QTimer, QUrl, QThread, pyqtSignal)
from PyQt6.QtGui import (QAction, QPixmap, QFont, QColor, QDrag, QIcon, 
                         QPainter, QKeyEvent, QFontMetrics, QKeySequence, QPen, QBrush, QDesktopServices)
from pynput import keyboard
try:
    import pygame
    HAS_GAMEPAD_LIB = True
except ImportError:
    HAS_GAMEPAD_LIB = False
    print("Pygame not found. Run the script with 'uv run' to auto-install.")

# Global Cache Dictionary
ICON_CACHE = {}

# --- WORKER: Gamepad Input Listener  ---
class GamepadWorker(QThread):
    btn_pressed = pyqtSignal(str) # 'A', 'B', 'X', 'Y', 'START', 'SELECT'
    dpad = pyqtSignal(str)        # 'UP', 'DOWN', 'LEFT', 'RIGHT'

    def run(self):
        if not HAS_GAMEPAD_LIB: return
        
        # Initialize Pygame Joystick Subsystem
        try:
            pygame.init()
            pygame.joystick.init()
        except Exception as e:
            print(f"Gamepad Init Error: {e}")
            return

        if pygame.joystick.get_count() == 0:
            print("No Gamepad Detected.")
            return

        # Connect to the first controller
        try:
            joystick = pygame.joystick.Joystick(0)
            joystick.init()
            print(f"Gamepad Connected: {joystick.get_name()}")
        except: return

        # Main Loop
        while True:
            # Process Pygame Events
            for event in pygame.event.get():
                # --- BUTTONS ---
                if event.type == pygame.JOYBUTTONDOWN:
                    b = event.button
                    # Extended Linux/SDL2 Mappings
                    btn_name = f"BTN_{b}" # Fallback
                    
                    if b == 0: btn_name = 'A'
                    elif b == 1: btn_name = 'B'
                    elif b == 2: btn_name = 'X'
                    elif b == 3: btn_name = 'Y'
                    elif b == 4: btn_name = 'LB'
                    elif b == 5: btn_name = 'RB'
                    elif b == 6: btn_name = 'SELECT'
                    elif b == 7: btn_name = 'START'
                    elif b == 8: btn_name = 'GUIDE' # Xbox/PS Home Button
                    elif b == 9: btn_name = 'L3'
                    elif b == 10: btn_name = 'R3'
                    
                    self.btn_pressed.emit(btn_name)

                # --- D-PAD (HAT) ---
                elif event.type == pygame.JOYHATMOTION:
                    x, y = event.value
                    if x == -1: self.dpad.emit('LEFT')
                    elif x == 1: self.dpad.emit('RIGHT')
                    if y == 1: self.dpad.emit('UP')
                    elif y == -1: self.dpad.emit('DOWN')

            # Sleep slightly to save CPU
            self.msleep(10)
        # Connect to the first controller
        try:
            joystick = pygame.joystick.Joystick(0)
            joystick.init()
            print(f"Gamepad Connected: {joystick.get_name()}")
        except: return

        # Main Loop
        while True:
            # Process Pygame Events
            for event in pygame.event.get():
                # --- BUTTONS ---
                if event.type == pygame.JOYBUTTONDOWN:
                    b = event.button
                    # Standard Linux/SDL2 Mappings (Xbox/PlayStation style)
                    if b == 0: self.btn_pressed.emit('A')      # A / Cross
                    elif b == 1: self.btn_pressed.emit('B')    # B / Circle
                    elif b == 2: self.btn_pressed.emit('X')    # X / Square
                    elif b == 3: self.btn_pressed.emit('Y')    # Y / Triangle
                    elif b == 6: self.btn_pressed.emit('SELECT') # Back / Share
                    elif b == 7: self.btn_pressed.emit('START')  # Start / Options

                # --- D-PAD (HAT) ---
                elif event.type == pygame.JOYHATMOTION:
                    # hat value is a tuple (x, y)
                    # x: -1 left, 1 right
                    # y: -1 down, 1 up (Note: Pygame Y axis varies, usually 1 is UP for hats)
                    x, y = event.value
                    
                    if x == -1: self.dpad.emit('LEFT')
                    elif x == 1: self.dpad.emit('RIGHT')
                    
                    if y == 1: self.dpad.emit('UP')
                    elif y == -1: self.dpad.emit('DOWN')

            # Sleep slightly to save CPU
            self.msleep(10)
                
def get_cached_pixmap(path, w, h):
    key = f"{path}_{w}_{h}"
    if key in ICON_CACHE:
        return ICON_CACHE[key]
    
    if not os.path.exists(path): return None
    
    try:
        pix = QPixmap(path)
        if pix.isNull(): return None
        # Cache it
        ICON_CACHE[key] = pix
        return pix
    except: return None

# --- TERMINAL DEFINITIONS ---
# Name, Executable, Arguments to run a command
KNOWN_TERMINALS = [
    ("Gnome Terminal", "gnome-terminal", ["--"]),
    ("Konsole", "konsole", ["-e"]),
    ("XFCE Terminal", "xfce4-terminal", ["-x"]),
    ("Kitty", "kitty", ["--"]),
    ("Alacritty", "alacritty", ["-e"]),
    ("XTerm", "xterm", ["-e"]),
    ("Terminator", "terminator", ["-x"]),
    ("Foot", "foot", ["bash", "-c"]) 
]

def get_installed_terminals():
    available = []
    for name, cmd, args in KNOWN_TERMINALS:
        if shutil.which(cmd):
            available.append((name, cmd, args))
    return available

# --- PLUGIN MANAGER ---
class PluginManager:
    def __init__(self):
        self.plugins = {}
        self.plugin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plugins')
        if not os.path.exists(self.plugin_dir): os.makedirs(self.plugin_dir)
        self.reload_plugins()

    def reload_plugins(self):
        self.plugins = {}
        if not os.path.exists(self.plugin_dir): return
        for f in os.listdir(self.plugin_dir):
            if f.endswith('.py') and f != "__init__.py":
                plugin_id = f[:-3]
                path = os.path.join(self.plugin_dir, f)
                try:
                    spec = importlib.util.spec_from_file_location(plugin_id, path)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    if hasattr(mod, 'run'):
                        self.plugins[plugin_id] = {
                            "name": getattr(mod, 'NAME', plugin_id.replace('_', ' ').title()),
                            "icon": getattr(mod, 'ICON', None),
                            "module": mod
                        }
                except Exception as e: print(f"Error loading plugin {f}: {e}")

    def execute(self, plugin_id, launcher_window):
        if plugin_id in self.plugins:
            try: self.plugins[plugin_id]["module"].run(launcher_window)
            except Exception as e: print(f"Error running plugin {plugin_id}: {e}")

# --- ASSET MANAGEMENT ---
class AssetManager:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
    
    SYSTEM_DIR = os.path.join(ASSETS_DIR, 'system', 'default_theme')
    THEMES_DIR = os.path.join(ASSETS_DIR, 'themes') # <--- New Definition
    CUSTOM_BG_DIR = os.path.join(ASSETS_DIR, 'custom', 'backgrounds')
    CUSTOM_ICON_DIR = os.path.join(ASSETS_DIR, 'custom', 'icons')

    @staticmethod
    def ensure_directories():
        os.makedirs(AssetManager.SYSTEM_DIR, exist_ok=True)
        os.makedirs(AssetManager.THEMES_DIR, exist_ok=True) # <--- Create it!
        os.makedirs(AssetManager.CUSTOM_BG_DIR, exist_ok=True)
        os.makedirs(AssetManager.CUSTOM_ICON_DIR, exist_ok=True)

    @staticmethod
    def import_file(file_path, target_folder):
        if not file_path or not os.path.exists(file_path): 
            return None
        name, ext = os.path.splitext(os.path.basename(file_path))
        unique_name = f"{name}_{int(time.time())}{ext}"
        destination = os.path.join(target_folder, unique_name)
        try:
            shutil.copy2(file_path, destination)
            return destination
        except Exception as e:
            print(f"Failed to copy asset: {e}")
            return file_path

# --- HELPER: Floating "Start" Button ---
class FloatingStartButton(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.X11BypassWindowManagerHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.layout = QVBoxLayout(self); self.layout.setContentsMargins(0,0,0,0)
        self.btn = QPushButton(); self.btn.clicked.connect(self.safe_toggle); self.layout.addWidget(self.btn)
        self.keep_alive = QTimer(self); self.keep_alive.timeout.connect(self.ensure_visible); self.keep_alive.start(2000) 
        self.apply_settings()

    def ensure_visible(self):
        settings = self.parent_window.config.get('start_btn', {})
        if settings.get('visible', True) and not self.parent_window.isVisible():
            if not self.isVisible(): self.show()
            self.raise_() 

    def safe_toggle(self): self.parent_window.toggle_visibility()

    def apply_settings(self):
        settings = self.parent_window.config.get('start_btn', {})
        if self.parent_window.isVisible() or not settings.get('visible', True):
            self.hide(); return
        else: self.show(); self.raise_()

        h = settings.get('size', 60); pos = settings.get('position', 'Bottom Left')
        icon_type = settings.get('icon_type', 'text'); icon_val = settings.get('icon_val', '❖')
        autohide = settings.get('autohide', False)
        
        w = h 
        if icon_type == 'text':
            fm = QFontMetrics(QFont("Segoe UI", int(h * 0.5)))
            w = max(h, fm.horizontalAdvance(icon_val) + 30) 
            
        self.setFixedSize(w, h); self.btn.setFixedSize(w, h)
        
        geo = QApplication.primaryScreen().geometry()
        x = 0 if "Left" in pos else (geo.width() - w if "Right" in pos else (geo.width() - w) // 2)
        y = 0 if "Top" in pos else geo.height() - h
        self.move(x, y)
        
        r = "10px"; c = ""
        if "Bottom" in pos:
            if "Left" in pos: c = f"border-top-right-radius: {r};"
            elif "Right" in pos: c = f"border-top-left-radius: {r};"
            elif "Center" in pos: c = f"border-top-left-radius: {r}; border-top-right-radius: {r};"
        else: 
            if "Left" in pos: c = f"border-bottom-right-radius: {r};"
            elif "Right" in pos: c = f"border-bottom-left-radius: {r};"
            elif "Center" in pos: c = f"border-bottom-left-radius: {r}; border-bottom-right-radius: {r};"

        self.btn.setIcon(QIcon()); self.btn.setText("")      
        
        base_extra = ""; hover_extra = ""
        
        if icon_type == 'image' and os.path.exists(icon_val):
            img_rule = f"border-image: url({icon_val.replace('\\', '/')}) 0 0 0 0 stretch stretch; padding: 10px;"
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

        std_col = settings.get('color', 'rgba(255,255,255,0.2)')
        nbg = "transparent" if autohide else std_col
        ncol = "transparent" if autohide else "white"
        
        style = f"""
            QPushButton {{ 
                background-color: {nbg}; 
                color: {ncol}; 
                border: none; 
                {c} 
                {base_extra} 
            }} 
            QPushButton:hover {{ 
                background-color: {std_col}; 
                color: white; 
                {hover_extra} 
            }}
        """
        self.btn.setStyleSheet(style)
        
# --- CUSTOM WIDGET: Circular App Bar Button (STYLE REVAMP) ---
class AppBarButton(QWidget):
    def __init__(self, text, icon_name, callback, parent_bar):
        super().__init__(parent_bar)
        self.setFixedSize(80, 80)
        self.text = text
        self.callback = callback
        self.parent_bar = parent_bar
        self.is_pressed = False
        
        # Determine Icon Path
        theme_path = parent_bar.parent_window.get_theme_icon_path()
        
        def find_icon(base_path, name):
            for ext in [".png", ".svg", ".jpg"]:
                p = os.path.join(base_path, f"{name}{ext}")
                if os.path.exists(p): return p
            return None

        # Try Custom Theme -> Default Theme -> System Theme
        path = find_icon(theme_path, icon_name)
        if not path: path = find_icon(AssetManager.SYSTEM_DIR, icon_name)
        
        if path: self.icon = QIcon(path)
        else: self.icon = QIcon.fromTheme(icon_name)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Fetch Custom Color from Settings (Default to White if not set)
        accent_hex = self.parent_bar.parent_window.config['settings'].get('appbar_accent_color', '#FFFFFF')
        accent_col = QColor(accent_hex)
        
        rect = self.rect().adjusted(10, 5, -10, -25)
        
        if self.is_pressed:
            painter.setBrush(accent_col) # Fill with accent on click
            painter.setPen(Qt.PenStyle.NoPen)
            icon_mode = QIcon.Mode.Normal 
            text_color = "black" # Text becomes black on filled background
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            # THINNER BORDER: Width 1 instead of 2
            painter.setPen(QPen(accent_col, 1)) 
            icon_mode = QIcon.Mode.Normal
            text_color = accent_hex # Text matches accent color
            
        painter.drawEllipse(rect)
        
        if not self.icon.isNull():
            target_rect = rect.adjusted(10, 10, -10, -10)
            self.icon.paint(painter, target_rect, Qt.AlignmentFlag.AlignCenter, icon_mode)
        
        painter.setPen(QColor(text_color))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(QRect(0, 60, 80, 20), Qt.AlignmentFlag.AlignCenter, self.text)

    def mousePressEvent(self, e):
        self.is_pressed = True; self.update()
    
    def mouseReleaseEvent(self, e):
        self.is_pressed = False; self.update()
        if self.rect().contains(e.pos()) and self.callback: self.callback()
# --- CUSTOM WIDGET: App Bar (Bottom Menu) ---
class AppBar(QWidget):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.target_tile = None
        
        # Start hidden, positioned at bottom
        self.hide()
        self.setFixedHeight(100)
        
        # Visual Style
        self.setStyleSheet("background-color: #1f1f1f; border-top: 2px solid #00a300;")
        
        # Layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(20, 10, 20, 10)
        self.layout.setSpacing(20)

    def toggle_for_tile(self, tile):
        if self.isVisible() and self.target_tile == tile:
            self.hide_bar()
        else:
            self.show_for_tile(tile)

    def show_for_tile(self, tile):
        self.target_tile = tile
        self.refresh_menu()
        
        # --- FIX: Force the bar to the front layer ---
        self.raise_() 
        # ---------------------------------------------
        
        # Animate Slide Up
        self.setGeometry(0, self.parent_window.height(), self.parent_window.width(), 100)
        self.show()
        
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(200)
        self.anim.setStartValue(QRect(0, self.parent_window.height(), self.parent_window.width(), 100))
        self.anim.setEndValue(QRect(0, self.parent_window.height() - 100, self.parent_window.width(), 100))
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.anim.start()

    def hide_bar(self):
        self.target_tile = None
        self.hide()

    def refresh_menu(self):
        # 1. Clear old buttons
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget(): 
                item.widget().deleteLater()
            
        # --- FIX: Removed the first addStretch() to align Left ---
        # self.layout.addStretch()  <-- DELETED
        
        if self.target_tile:
            tile = self.target_tile
            
            # 1. Unpin
            self.layout.addWidget(AppBarButton("Unpin", "cmd_unpin", lambda: self.action_delete(), self))
            
            # 2. Resize
            self.layout.addWidget(AppBarButton("Resize", "cmd_resize", lambda: tile.cycle_size(), self))
            
            # 3. Edit
            self.layout.addWidget(AppBarButton("Edit", "cmd_edit", lambda: self.action_edit(), self))
            
            # 4. Color
            self.layout.addWidget(AppBarButton("Color", "cmd_color", lambda: tile.change_color(), self))
            
            # 5. Icon
            self.layout.addWidget(AppBarButton("Icon", "cmd_icon", lambda: tile.change_icon(), self))
            
        # Keep this one to push everything to the left
        self.layout.addStretch()

    def action_delete(self):
        if self.target_tile:
            self.target_tile.request_delete()
            self.hide_bar()

    def action_edit(self):
        if self.target_tile:
            self.target_tile.edit_details()
            self.hide_bar()
    # --- ACTIONS ---
    def action_delete(self):
        if self.target_tile:
            self.target_tile.request_delete()
            self.hide_bar()

    def action_edit(self):
        if self.target_tile:
            self.target_tile.edit_details()
            self.hide_bar()
            
    def action_resize(self):
        if self.target_tile:
            self.target_tile.cycle_size()

# --- CUSTOM WIDGET: Kinetic Scroll Area (FIXED TRANSPARENCY) ---
class KineticScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # FIX: Explicitly force transparency on the viewport
        self.viewport().setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Drag Variables
        self.is_dragging = False
        self.start_pos = None
        self.start_scroll_val = 0
        self.last_mouse_x = 0
        self.velocity = 0
        
        # Animation for inertia
        self.anim = QPropertyAnimation(self.horizontalScrollBar(), b"value")
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)

        # Style: Set QScrollArea background to transparent explicitly
        self.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:horizontal {
                height: 12px;
                background: transparent;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(255, 255, 255, 0.3);
                min-width: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal:hover {
                background: rgba(255, 255, 255, 0.5);
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.start_pos = event.pos()
            self.start_scroll_val = self.horizontalScrollBar().value()
            self.last_mouse_x = event.pos().x()
            self.velocity = 0
            self.anim.stop()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            delta = event.pos().x() - self.start_pos.x()
            self.horizontalScrollBar().setValue(self.start_scroll_val - delta)
            
            # Calculate instantaneous velocity
            current_x = event.pos().x()
            self.velocity = current_x - self.last_mouse_x
            self.last_mouse_x = current_x
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_dragging:
            self.is_dragging = False
            
            # Apply Inertia if flicked fast enough
            if abs(self.velocity) > 2:
                current_val = self.horizontalScrollBar().value()
                # Predict where it should land based on velocity
                end_val = current_val - (self.velocity * 30) 
                # Clamp to boundaries
                end_val = max(self.horizontalScrollBar().minimum(), min(end_val, self.horizontalScrollBar().maximum()))
                
                self.anim.setDuration(600)
                self.anim.setStartValue(current_val)
                self.anim.setEndValue(end_val)
                self.anim.start()
                
        super().mouseReleaseEvent(event)

# --- HELPER: App Importer (UPDATED FOR APPIMAGES) ---
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
        self.list_widget = QListWidget(); self.layout.addWidget(self.list_widget)
        self.icon_check = QCheckBox("Import System Icon"); self.icon_check.setChecked(True); self.layout.addWidget(self.icon_check)
        self.btn_box = QHBoxLayout()
        import_btn = QPushButton("Import"); import_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel"); cancel_btn.clicked.connect(self.reject)
        self.btn_box.addWidget(import_btn); self.btn_box.addWidget(cancel_btn)
        self.layout.addLayout(self.btn_box)
        self.system_apps = []; self.load_system_apps()

    def load_system_apps(self):
        # 1. Standard Desktop Paths
        paths = ["/usr/share/applications", os.path.expanduser("~/.local/share/applications"),
                 "/var/lib/flatpak/exports/share/applications", os.path.expanduser("~/.local/share/flatpak/exports/share/applications"), 
                 "/var/lib/snapd/desktop/applications"]
        
        unique_names = set()
        
        # Scan Desktop Files
        for path in paths:
            if not os.path.exists(path): continue
            for root, _, files in os.walk(path):
                for file in files:
                    if file.endswith(".desktop"):
                        try:
                            data = self.parse_desktop_file(os.path.join(root, file))
                            if data:
                                key = f"{data['name']}|{data['exec']}"
                                if key not in unique_names: self.system_apps.append(data); unique_names.add(key)
                        except: pass
        
        # 2. NEW: Scan for AppImages in ~/Applications
        appimage_dir = os.path.expanduser("~/Applications")
        if os.path.exists(appimage_dir):
            for f in os.listdir(appimage_dir):
                if f.lower().endswith(".appimage"):
                    full_path = os.path.join(appimage_dir, f)
                    # Clean up name (e.g., "Krita-5.0.0.AppImage" -> "Krita 5.0.0")
                    name = f.replace(".AppImage", "").replace(".appimage", "").replace("-", " ").replace("_", " ")
                    
                    data = {
                        "name": name,
                        "exec": full_path,
                        "icon_name": "application-x-executable", # Default icon
                        "path": full_path
                    }
                    
                    key = f"{name}|{full_path}"
                    if key not in unique_names:
                        self.system_apps.append(data)
                        unique_names.add(key)

        self.system_apps.sort(key=lambda x: x['name'].lower()); self.populate_list(self.system_apps)

    def parse_desktop_file(self, path):
        name, loc_name, exec_cmd, icon = None, None, None, None
        no_display, hidden, in_main_section = False, False, False
        try:
            with open(path, 'r', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'): continue
                    if line.startswith('['):
                        if line == "[Desktop Entry]": in_main_section = True; continue
                        else: 
                            if in_main_section: break 
                            else: continue 
                    if in_main_section and "=" in line:
                        key, value = line.split("=", 1)
                        key, value = key.strip(), value.strip()
                        if key == "Name": name = value
                        elif key.startswith("Name["): loc_name = value 
                        elif key == "Exec": exec_cmd = value
                        elif key == "Icon": icon = value
                        elif key == "NoDisplay" and value.lower() == "true": no_display = True
                        elif key == "Hidden" and value.lower() == "true": hidden = True
                        elif key == "Type" and value.lower() != "application": return None 
        except: return None
        if no_display or hidden: return None
        final_name = name if name else loc_name
        if not final_name or not exec_cmd: return None
        return {"name": final_name, "exec": exec_cmd.split('%')[0].strip(), "icon_name": icon, "path": path}

    def populate_list(self, apps):
        self.list_widget.clear()
        for app in apps:
            item = QListWidgetItem(app['name'])
            if app['icon_name']:
                icon = QIcon.fromTheme(app['icon_name']) if not os.path.exists(app['icon_name']) else QIcon(app['icon_name'])
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
# --- HELPER: App Editor Dialog (UPDATED ASSETS) ---
class AppEditorDialog(QDialog):
    def __init__(self, parent=None, parent_window=None, app_data=None):
        super().__init__(parent)
        self.parent_window = parent_window
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Properties")
        self.setFixedWidth(400)
        self.app_data = app_data or {}
        self.plugin_inputs = {} 

        layout = QFormLayout(self)
        self.name_input = QLineEdit(self.app_data.get('name', ''))
        layout.addRow("Name:", self.name_input)
        
        self.mode_combo = QComboBox(); self.mode_combo.addItems(["Run Application", "Plugin"]); layout.addRow("Tile Mode:", self.mode_combo)
        self.plugin_combo = QComboBox(); layout.addRow("Select Plugin:", self.plugin_combo)
        
        self.plugin_fields_widget = QWidget(); self.plugin_fields_layout = QFormLayout(self.plugin_fields_widget); self.plugin_fields_layout.setContentsMargins(0,0,0,0); layout.addRow(self.plugin_fields_widget)

        self.grp_paths = QWidget(); path_layout = QFormLayout(self.grp_paths); path_layout.setContentsMargins(0,0,0,0)
        self.script_input = QLineEdit(self.app_data.get('script_path', '')); self.script_btn = QPushButton("Browse..."); self.script_btn.clicked.connect(lambda: self.browse_file(self.script_input, "exec")); s_row = QHBoxLayout(); s_row.addWidget(self.script_input); s_row.addWidget(self.script_btn); s_con = QWidget(); s_con.setLayout(s_row); path_layout.addRow("Script/Exec:", s_con)
        self.python_input = QLineEdit(self.app_data.get('python_path', sys.executable)); self.python_btn = QPushButton("Browse..."); self.python_btn.clicked.connect(lambda: self.browse_file(self.python_input, "exec")); p_row = QHBoxLayout(); p_row.addWidget(self.python_input); p_row.addWidget(self.python_btn); p_con = QWidget(); p_con.setLayout(p_row); path_layout.addRow("Python Path:", p_con)
        self.import_sys_btn = QPushButton("Import from System..."); self.import_sys_btn.clicked.connect(self.import_system_app); path_layout.addRow("", self.import_sys_btn)
        layout.addRow(self.grp_paths)
        
        # --- NEW ICON PICKER ---
        self.icon_path_input = QLineEdit(self.app_data.get('icon', ''))
        self.icon_browse_btn = QPushButton("Browse Image...")
        self.icon_browse_btn.clicked.connect(self.browse_icon_file)
        i_row = QHBoxLayout(); i_row.addWidget(self.icon_path_input); i_row.addWidget(self.icon_browse_btn)
        i_con = QWidget(); i_con.setLayout(i_row)
        layout.addRow("Icon:", i_con)
        # -----------------------

        self.full_tile_check = QCheckBox("Full Tile Mode (Image fills tile)"); self.full_tile_check.setChecked(self.app_data.get('full_tile', False)); layout.addRow("", self.full_tile_check)
        
        self.size_map = {0: (1, 1, "Small (1x1)"), 1: (1, 2, "Wide (2x1)"), 2: (2, 2, "Large (2x2)"), 3: (1, 3, "Wide (3x1)"), 4: (2, 3, "Large (3x2)"), 5: (3, 3, "Huge (3x3)")}
        self.size_slider = QSlider(Qt.Orientation.Horizontal); self.size_slider.setRange(0, 5); self.size_slider.setTickPosition(QSlider.TickPosition.TicksBelow); self.size_slider.setTickInterval(1)
        cur_r = self.app_data.get('row_span', 1); cur_c = self.app_data.get('col_span', 2 if self.app_data.get('wide_tile') else 1)
        best_idx = 0
        for k, v in self.size_map.items():
            if v[0] == cur_r and v[1] == cur_c: best_idx = k; break
        self.size_slider.setValue(best_idx)
        self.size_label = QLabel(self.size_map[best_idx][2]); self.size_slider.valueChanged.connect(lambda v: self.size_label.setText(self.size_map[v][2]))
        layout.addRow("Tile Size:", self.size_label); layout.addRow(self.size_slider)
        
        self.color_btn = QPushButton("Pick Color"); def_col = self.parent_window.config['settings'].get('default_tile_color', '#00a300') if self.parent_window else '#00a300'; self.selected_color = self.app_data.get('color', def_col); self.color_btn.setStyleSheet(f"background-color: {self.selected_color}"); self.color_btn.clicked.connect(self.pick_color); layout.addRow("Tile Color:", self.color_btn)
        
        btn_box = QHBoxLayout(); save_btn = QPushButton("Save"); save_btn.clicked.connect(self.accept); cancel_btn = QPushButton("Cancel"); cancel_btn.clicked.connect(self.reject); btn_box.addWidget(save_btn); btn_box.addWidget(cancel_btn); layout.addRow(btn_box)
        
        # ... (previous code in AppEditorDialog.__init__) ...
        
        self.populate_plugins()
        self.mode_combo.currentTextChanged.connect(self.refresh_layout)
        self.plugin_combo.currentIndexChanged.connect(self.refresh_plugin_fields)
        
        # --- FIXED LOGIC HERE ---
        if self.app_data.get('type') == 'plugin':
            self.mode_combo.setCurrentText("Plugin")
            idx = self.plugin_combo.findData(self.app_data.get('plugin_id'))
            if idx >= 0: 
                self.plugin_combo.setCurrentIndex(idx)
        else:
            self.mode_combo.setCurrentText("Run Application")
            
        self.refresh_layout()

    # --- UPDATED: COPIES ICON TO ASSETS ---
    def browse_icon_file(self):
        dlg = QFileDialog(self, "Select Icon", filter="Images (*.png *.jpg *.svg *.ico)")
        if dlg.exec():
            # This now returns a path like ".../assets/custom/icons/icon_174921.png"
            new_path = AssetManager.import_file(dlg.selectedFiles()[0], AssetManager.CUSTOM_ICON_DIR)
            
            # Update the text box immediately
            self.icon_path_input.setText(new_path)

    # Standard file browse for scripts (no copy)
    # FIX: Added 'type_filter' so it can accept the "exec" argument
    def browse_file(self, line_edit, type_filter=None):
        if type_filter == "exec":
            f = "All Files (*);;AppImages (*.AppImage *.appimage);;Python Scripts (*.py);;Executables (*.exe *.sh *.bin)" 
        else:
            f = "All Files (*)"
            
        dlg = QFileDialog(self, "Select File", filter=f)
        if dlg.exec(): 
            line_edit.setText(dlg.selectedFiles()[0])

    # [Keep populate_plugins, refresh_layout, refresh_plugin_fields, pick_color, import_system_app, get_data exactly as they were]
    def populate_plugins(self):
        if self.parent_window and self.parent_window.plugin_manager:
            for pid, pdata in self.parent_window.plugin_manager.plugins.items(): self.plugin_combo.addItem(pdata['name'], pid)
    def refresh_layout(self):
        is_app = (self.mode_combo.currentText() == "Run Application")
        self.grp_paths.setVisible(is_app); self.plugin_combo.setVisible(not is_app); self.plugin_fields_widget.setVisible(not is_app)
        if not is_app: self.refresh_plugin_fields()
    def refresh_plugin_fields(self):
        if not hasattr(self, 'plugin_fields_layout'): return
        while self.plugin_fields_layout.count():
            child = self.plugin_fields_layout.takeAt(0); 
            if child.widget(): child.widget().deleteLater()
        self.plugin_inputs = {}
        plugin_id = self.plugin_combo.currentData()
        if not plugin_id or not self.parent_window: return
        plugin = self.parent_window.plugin_manager.plugins.get(plugin_id)
        if plugin and hasattr(plugin['module'], 'CONFIG_FIELDS'):
            fields = getattr(plugin['module'], 'CONFIG_FIELDS', [])
            if fields: header = QLabel("Plugin Settings:"); header.setStyleSheet("font-weight: bold; margin-top: 5px;"); self.plugin_fields_layout.addRow(header)
            for field in fields:
                key = field['key']; label = field['label']; default = field['default']; current_val = self.app_data.get(key, default)
                if 'options' in field and isinstance(field['options'], list): inp = QComboBox(); inp.addItems(field['options']); inp.setCurrentText(str(current_val))
                else: inp = QLineEdit(str(current_val))
                self.plugin_fields_layout.addRow(f"{label}:", inp); self.plugin_inputs[key] = inp
    def pick_color(self):
        c = QColorDialog.getColor(QColor(self.selected_color), self)
        if c.isValid(): self.selected_color = c.name(); self.color_btn.setStyleSheet(f"background-color: {self.selected_color}")
    def import_system_app(self):
        dlg = AppImporterDialog(self)
        if dlg.exec():
            app = dlg.get_selected_app()
            if app: 
                self.name_input.setText(app['name']); self.script_input.setText(app['exec']); self.python_input.setText("SYSTEM") 
                if dlg.icon_check.isChecked() and app['icon_name']: self.icon_path_input.setText(app['icon_name'])
    def get_data(self):
        mode = self.mode_combo.currentText(); internal_type = 'plugin' if mode == "Plugin" else 'app'
        slider_val = self.size_slider.value(); r_span, c_span, _ = self.size_map[slider_val]
        # FIX: Ensure we save the icon path from the input box
        data = { "name": self.name_input.text(), "type": internal_type, "color": self.selected_color, "icon": self.icon_path_input.text(),
            "full_tile": self.full_tile_check.isChecked(), "row_span": r_span, "col_span": c_span, "wide_tile": (c_span > 1) }
        if internal_type == 'app': data['script_path'] = self.script_input.text(); data['python_path'] = self.python_input.text()
        else:
            data['plugin_id'] = self.plugin_combo.currentData()
            for key, widget in self.plugin_inputs.items():
                if isinstance(widget, QComboBox): data[key] = widget.currentText()
                else: data[key] = widget.text()
        return data
    # --- UPDATED: Read from Dropdowns ---
    def get_data(self):
        mode = self.mode_combo.currentText()
        internal_type = 'plugin' if mode == "Plugin" else 'app'
        
        slider_val = self.size_slider.value()
        r_span, c_span, _ = self.size_map[slider_val]
        
        data = { 
            "name": self.name_input.text(), 
            "type": internal_type, 
            "color": self.selected_color, 
            "icon": self.app_data.get('icon', None),
            "full_tile": self.full_tile_check.isChecked(), 
            "row_span": r_span,
            "col_span": c_span,
            "wide_tile": (c_span > 1) 
        }
        
        if internal_type == 'app':
            data['script_path'] = self.script_input.text()
            data['python_path'] = self.python_input.text()
        else:
            data['plugin_id'] = self.plugin_combo.currentData()
            for key, widget in self.plugin_inputs.items():
                # Check if it's a Dropdown or Textbox
                if isinstance(widget, QComboBox):
                    data[key] = widget.currentText()
                else:
                    data[key] = widget.text()
                
        return data
    # --- KEEP EXISTING HELPER METHODS SAME AS BEFORE ---
    def populate_plugins(self):
        if self.parent_window and self.parent_window.plugin_manager:
            for pid, pdata in self.parent_window.plugin_manager.plugins.items():
                self.plugin_combo.addItem(pdata['name'], pid)

    def refresh_layout(self):
        is_app = (self.mode_combo.currentText() == "Run Application")
        self.grp_paths.setVisible(is_app)
        self.plugin_combo.setVisible(not is_app)
        self.plugin_fields_widget.setVisible(not is_app)
        if not is_app: self.refresh_plugin_fields()

    def refresh_plugin_fields(self):
        if not hasattr(self, 'plugin_fields_layout'): return
        while self.plugin_fields_layout.count():
            child = self.plugin_fields_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self.plugin_inputs = {}

        plugin_id = self.plugin_combo.currentData()
        if not plugin_id or not self.parent_window: return

        plugin = self.parent_window.plugin_manager.plugins.get(plugin_id)
        if plugin and hasattr(plugin['module'], 'CONFIG_FIELDS'):
            fields = getattr(plugin['module'], 'CONFIG_FIELDS', [])
            if fields:
                header = QLabel("Plugin Settings:"); header.setStyleSheet("font-weight: bold; margin-top: 5px;")
                self.plugin_fields_layout.addRow(header)
            for field in fields:
                key = field['key']; label = field['label']; default = field['default']
                current_val = self.app_data.get(key, default)
                inp = QLineEdit(str(current_val))
                self.plugin_fields_layout.addRow(f"{label}:", inp)
                self.plugin_inputs[key] = inp

    def pick_color(self):
        c = QColorDialog.getColor(QColor(self.selected_color), self)
        if c.isValid(): self.selected_color = c.name(); self.color_btn.setStyleSheet(f"background-color: {self.selected_color}")

    def import_system_app(self):
        dlg = AppImporterDialog(self)
        if dlg.exec():
            app = dlg.get_selected_app()
            if app:
                self.name_input.setText(app['name']); self.script_input.setText(app['exec']); self.python_input.setText("SYSTEM") 
                if dlg.icon_check.isChecked() and app['icon_name']: self.app_data['icon'] = app['icon_name']

    def get_data(self):
        mode = self.mode_combo.currentText()
        internal_type = 'plugin' if mode == "Plugin" else 'app'
        
        # Calculate row/col from slider
        slider_val = self.size_slider.value()
        r_span, c_span, _ = self.size_map[slider_val]
        
        data = { 
            "name": self.name_input.text(), 
            "type": internal_type, 
            "color": self.selected_color, 
            "icon": self.app_data.get('icon', None),
            "full_tile": self.full_tile_check.isChecked(), 
            "row_span": r_span,
            "col_span": c_span,
            "wide_tile": (c_span > 1) 
        }
        
        if internal_type == 'app':
            data['script_path'] = self.script_input.text()
            data['python_path'] = self.python_input.text()
        else:
            data['plugin_id'] = self.plugin_combo.currentData()
            for key, inp in self.plugin_inputs.items():
                data[key] = inp.text()
                
        return data
# --- HELPER: Hotkey Recorder Button ---
class HotkeyRecorder(QPushButton):
    def __init__(self, current_hotkey, parent=None):
        super().__init__(current_hotkey, parent)
        self.setCheckable(True)
        self.current_hotkey = current_hotkey if current_hotkey else "<cmd>+p"
        self.setText(self.current_hotkey)
        self.clicked.connect(self.toggle_mode)
        
    def toggle_mode(self, checked):
        if checked:
            self.setText("Press Combo... (Esc to cancel)")
            self.grabKeyboard() # Capture all input
        else:
            self.releaseKeyboard()
            self.setText(self.current_hotkey)

    def keyPressEvent(self, event):
        if not self.isChecked():
            super().keyPressEvent(event)
            return
        
        key = event.key()
        
        # Cancel if Esc is pressed
        if key == Qt.Key.Key_Escape:
            self.setChecked(False)
            self.releaseKeyboard()
            self.setText(self.current_hotkey)
            return
        
        # Don't record if only a modifier is pressed (wait for the actual key)
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return

        # 1. Map Modifiers
        parts = []
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier: parts.append("<ctrl>")
        if mods & Qt.KeyboardModifier.ShiftModifier: parts.append("<shift>")
        if mods & Qt.KeyboardModifier.AltModifier: parts.append("<alt>")
        if mods & Qt.KeyboardModifier.MetaModifier: parts.append("<cmd>") # Super/Windows Key

        # 2. Map Key
        txt = QKeySequence(key).toString().lower()
        
        # Special Pynput Mappings
        special_map = {
            Qt.Key.Key_Space: "<space>",
            Qt.Key.Key_Return: "<enter>", Qt.Key.Key_Enter: "<enter>",
            Qt.Key.Key_Tab: "<tab>",
            Qt.Key.Key_Backspace: "<backspace>",
            Qt.Key.Key_Delete: "<delete>",
            Qt.Key.Key_Left: "<left>", Qt.Key.Key_Right: "<right>",
            Qt.Key.Key_Up: "<up>", Qt.Key.Key_Down: "<down>",
            Qt.Key.Key_Home: "<home>", Qt.Key.Key_End: "<end>",
            Qt.Key.Key_PageUp: "<pageup>", Qt.Key.Key_PageDown: "<pagedown>",
            Qt.Key.Key_Insert: "<insert>"
        }
        
        if key in special_map:
            txt = special_map[key]
        elif key >= Qt.Key.Key_F1 and key <= Qt.Key.Key_F12:
            txt = f"<{txt}>"
        
        parts.append(txt)
        final = "+".join(parts)
        
        # 3. Save & Exit
        self.current_hotkey = final
        self.setText(final)
        self.setChecked(False)
        self.releaseKeyboard()
        
# --- HELPER: Gamepad Recorder Button ---
class GamepadRecorder(QPushButton):
    def __init__(self, current_val, main_window, parent=None):
        super().__init__(current_val, parent)
        self.main_window = main_window
        self.setCheckable(True)
        self.default_text = current_val if current_val else "None"
        self.setText(self.default_text)
        self.clicked.connect(self.toggle_mode)
        
    def toggle_mode(self, checked):
        if checked:
            self.setText("Press Gamepad Button...")
            # Connect to the main window's existing worker
            if hasattr(self.main_window, 'gamepad_thread'):
                self.main_window.gamepad_thread.btn_pressed.connect(self.record_input)
        else:
            self.stop_recording()
            self.setText(self.default_text)

    def record_input(self, btn_name):
        self.default_text = btn_name
        self.setText(btn_name)
        self.setChecked(False)
        self.stop_recording()

    def stop_recording(self):
        # Disconnect safely
        if hasattr(self.main_window, 'gamepad_thread'):
            try:
                self.main_window.gamepad_thread.btn_pressed.disconnect(self.record_input)
            except: pass
            
# --- HELPER: Settings & Themes Dialog (WITH BG TRANSPARENCY) ---
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Settings")
        self.resize(500, 650)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        
        # --- TAB 1: GENERAL SETTINGS ---
        gen_tab = QWidget(); gen_layout = QVBoxLayout(gen_tab)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget(); form = QFormLayout(scroll_content)
        
        # COLORS
        form.addRow(QLabel("<b><font size='4'>Colors & Background</font></b>"))
        self.bg_type = QComboBox(); self.bg_type.addItems(["color", "image"]); self.bg_type.setCurrentText(parent.config['settings'].get('background_type', 'color'))
        form.addRow("Background Type:", self.bg_type)
        self.bg_value = QLineEdit(parent.config['settings'].get('background_value', '')); browse_bg = QPushButton("Browse Image"); browse_bg.clicked.connect(self.browse_bg)
        form.addRow("Image Path:", self.bg_value); form.addRow("", browse_bg)
        
        self.bg_color_btn = QPushButton("Pick Background Color"); self.current_bg_color = parent.config['settings'].get('background_color', '#1d1d1d')
        self.bg_color_btn.setStyleSheet(f"background-color: {self.current_bg_color}"); self.bg_color_btn.clicked.connect(lambda: self.pick_color('bg'))
        form.addRow("Background Color:", self.bg_color_btn)
        
        # --- NEW: Background Opacity Slider ---
        self.bg_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.bg_opacity_slider.setRange(1, 100) # 1% to 100%
        current_op = parent.config['settings'].get('background_opacity', 100)
        self.bg_opacity_slider.setValue(current_op)
        self.bg_opacity_lbl = QLabel(f"{current_op}%")
        self.bg_opacity_slider.valueChanged.connect(lambda v: self.bg_opacity_lbl.setText(f"{v}%"))
        
        form.addRow("Background Opacity:", self.bg_opacity_lbl)
        form.addRow(self.bg_opacity_slider)
        # --------------------------------------
        
        self.appbar_col_btn = QPushButton("Pick Menu Accent Color"); self.current_appbar_color = parent.config['settings'].get('appbar_accent_color', '#ffffff')
        self.appbar_col_btn.setStyleSheet(f"background-color: {self.current_appbar_color}"); self.appbar_col_btn.clicked.connect(lambda: self.pick_color('appbar'))
        form.addRow("Right-Click Menu Color:", self.appbar_col_btn)
        
        self.def_tile_btn = QPushButton("Pick Default Tile Color"); self.current_tile_color = parent.config['settings'].get('default_tile_color', '#00a300')
        self.def_tile_btn.setStyleSheet(f"background-color: {self.current_tile_color}"); self.def_tile_btn.clicked.connect(lambda: self.pick_color('tile'))
        form.addRow("Default Tile Color:", self.def_tile_btn)
        
        sb_config = parent.config.get('start_btn', {})
        self.sb_color_btn = QPushButton("Pick Start Button Color"); self.current_sb_color = sb_config.get('color', 'rgba(255, 255, 255, 0.2)')
        self.sb_color_btn.setStyleSheet(f"background-color: {self.current_sb_color}"); self.sb_color_btn.clicked.connect(lambda: self.pick_color('sb'))
        form.addRow("Start Button Color:", self.sb_color_btn)

        form.addRow(QLabel("")) # Spacer

        # TILE & LAYOUT
        form.addRow(QLabel("<b><font size='4'>Tile & Layout</font></b>"))
        self.size_slider = QSlider(Qt.Orientation.Horizontal); self.size_slider.setRange(80, 240); self.size_slider.setValue(parent.config['settings'].get('tile_size', 140))
        self.size_lbl = QLabel(f"{self.size_slider.value()} px"); self.size_slider.valueChanged.connect(lambda v: self.size_lbl.setText(f"{v} px"))
        form.addRow("Tile Size:", self.size_lbl); form.addRow(self.size_slider)
        
        self.col_spin = QSpinBox(); self.col_spin.setRange(1, 10); self.col_spin.setValue(parent.config['settings'].get('group_columns', 2))
        form.addRow("Columns per Group:", self.col_spin)
        
        self.radius_slider = QSlider(Qt.Orientation.Horizontal); self.radius_slider.setRange(0, 50); self.radius_slider.setValue(parent.config['settings'].get('tile_radius', 0))
        self.radius_lbl = QLabel(f"{self.radius_slider.value()} px"); self.radius_slider.valueChanged.connect(lambda v: self.radius_lbl.setText(f"{v} px"))
        form.addRow("Corner Radius:", self.radius_lbl); form.addRow(self.radius_slider)
        
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal); self.opacity_slider.setRange(0, 100); self.opacity_slider.setValue(int((parent.config['settings'].get('tile_alpha', 255) / 255) * 100))
        self.opacity_lbl = QLabel(f"{self.opacity_slider.value()}%"); self.opacity_slider.valueChanged.connect(lambda v: self.opacity_lbl.setText(f"{v}%"))
        form.addRow("Tile Opacity:", self.opacity_lbl); form.addRow(self.opacity_slider)
        
        form.addRow(QLabel("<i>Start Button Settings:</i>"))
        self.sb_visible = QCheckBox("Show Start Button"); self.sb_visible.setChecked(sb_config.get('visible', True)); form.addRow(self.sb_visible)
        self.sb_autohide = QCheckBox("Auto-Hide (Invisible until hovered)"); self.sb_autohide.setChecked(sb_config.get('autohide', False)); form.addRow(self.sb_autohide)
        self.sb_pos = QComboBox(); self.sb_pos.addItems(["Bottom Left", "Bottom Center", "Bottom Right", "Top Left", "Top Center", "Top Right"]); self.sb_pos.setCurrentText(sb_config.get('position', 'Bottom Left'))
        form.addRow("Position:", self.sb_pos)
        self.sb_size = QSlider(Qt.Orientation.Horizontal); self.sb_size.setRange(30, 100); self.sb_size.setValue(sb_config.get('size', 60))
        self.sb_size_lbl = QLabel(f"{self.sb_size.value()} px"); self.sb_size.valueChanged.connect(lambda v: self.sb_size_lbl.setText(f"{v} px"))
        form.addRow("Button Size:", self.sb_size_lbl); form.addRow(self.sb_size)
        self.sb_icon_type = QComboBox(); self.sb_icon_type.addItems(["text", "image"]); self.sb_icon_type.setCurrentText(sb_config.get('icon_type', 'text'))
        form.addRow("Icon Type:", self.sb_icon_type)
        self.sb_icon_val = QLineEdit(sb_config.get('icon_val', '❖')); sb_browse = QPushButton("Browse Icon"); sb_browse.clicked.connect(self.browse_sb_icon)
        form.addRow("Icon/Text:", self.sb_icon_val); form.addRow("", sb_browse)

        scroll.setWidget(scroll_content); gen_layout.addWidget(scroll)
        tabs.addTab(gen_tab, "General Settings")

        # --- TAB 2: SYSTEM ---
        sys_tab = QWidget(); sys_form = QFormLayout(sys_tab)
        
        # Keyboard Hotkey
        current_hk = parent.config['settings'].get('global_hotkey', '<cmd>+p')
        self.hotkey_recorder = HotkeyRecorder(current_hk)
        sys_form.addRow("Keyboard Hotkey:", self.hotkey_recorder)
        
        # Gamepad Toggle
        current_gp = parent.config['settings'].get('gamepad_hotkey', 'GUIDE')
        self.gamepad_recorder = GamepadRecorder(current_gp, parent, self)
        sys_form.addRow("Gamepad Toggle:", self.gamepad_recorder)
        
        sys_form.addRow(QLabel("<font color='gray' size='2'>(Restart app to apply hotkey changes)</font>"))
        
        # Terminal Settings
        self.term_combo = QComboBox()
        self.available_terms = get_installed_terminals()
        current_term_app = parent.config['settings'].get('terminal_app', '')
        for name, cmd, args in self.available_terms:
            self.term_combo.addItem(name, (cmd, args))
            if cmd == current_term_app: self.term_combo.setCurrentIndex(self.term_combo.count() - 1)
        sys_form.addRow("Preferred Console:", self.term_combo)
        
        tabs.addTab(sys_tab, "System")

        # --- TAB 3: THEMES ---
        theme_tab = QWidget(); theme_layout = QVBoxLayout(theme_tab)
        theme_form = QFormLayout()
        
        self.icon_theme_combo = QComboBox(); self.icon_theme_combo.addItem("Default System", "default_theme")
        open_folder_btn = QPushButton("📂 Open Themes Folder")
        open_folder_btn.clicked.connect(self.open_themes_folder)
        
        themes_dir = AssetManager.THEMES_DIR
        if os.path.exists(themes_dir):
            for d in os.listdir(themes_dir):
                if os.path.isdir(os.path.join(themes_dir, d)): self.icon_theme_combo.addItem(d, d)
        
        current_theme = parent.config['settings'].get('icon_theme', 'default_theme')
        idx = self.icon_theme_combo.findData(current_theme)
        if idx >= 0: self.icon_theme_combo.setCurrentIndex(idx)
        
        r_layout = QHBoxLayout(); r_layout.addWidget(self.icon_theme_combo); r_layout.addWidget(open_folder_btn)
        theme_form.addRow("Icon Theme:", r_layout); theme_layout.addLayout(theme_form)

        theme_layout.addWidget(QLabel("Recent Configurations:"))
        self.recent_list = QListWidget(); self.populate_recent(); self.recent_list.itemDoubleClicked.connect(self.load_recent_theme); theme_layout.addWidget(self.recent_list)
        hbox = QHBoxLayout(); export_btn = QPushButton("Export Current"); export_btn.clicked.connect(self.export_theme); import_btn = QPushButton("Import Theme"); import_btn.clicked.connect(self.import_theme); hbox.addWidget(export_btn); hbox.addWidget(import_btn)
        theme_layout.addLayout(hbox)
        reset_btn = QPushButton("Reset to Defaults"); reset_btn.setStyleSheet("background-color: #e51400; color: white; font-weight: bold; margin-top: 20px;"); reset_btn.clicked.connect(self.reset_defaults); theme_layout.addWidget(reset_btn)
        tabs.addTab(theme_tab, "Themes")
        
        layout.addWidget(tabs)
        save_btn = QPushButton("Save & Close"); save_btn.clicked.connect(self.save_and_close); layout.addWidget(save_btn)

    def open_themes_folder(self):
        self.close() 
        self.parent_window.toggle_visibility() 
        QDesktopServices.openUrl(QUrl.fromLocalFile(AssetManager.THEMES_DIR))

    def get_current_settings(self):
        term_cmd, term_flags = self.term_combo.currentData() if self.term_combo.currentData() else ("xterm", ["-e"])
        return {
            "window_title": "Pop Metro Launcher", 
            "background_type": self.bg_type.currentText(), 
            "background_value": self.bg_value.text(),
            "background_color": self.current_bg_color,
            "background_opacity": self.bg_opacity_slider.value(), # <--- SAVE OPACITY
            
            "default_tile_color": self.current_tile_color, 
            "tile_size": self.size_slider.value(),
            "group_columns": self.col_spin.value(), 
            "tile_radius": self.radius_slider.value(), 
            "tile_alpha": int((self.opacity_slider.value() / 100) * 255),
            "global_hotkey": self.hotkey_recorder.text(), 
            "gamepad_hotkey": self.gamepad_recorder.text(), 
            "terminal_app": term_cmd, 
            "terminal_flags": term_flags,
            "icon_theme": self.icon_theme_combo.currentData(),
            "appbar_accent_color": self.current_appbar_color
        }

    # [Keep pick_color, reset_defaults, browse_bg, browse_sb_icon, populate_recent, get_sb_settings, save_and_close, export_theme, import_theme, load_recent_theme unchanged]
    def pick_color(self, target):
        initial = '#000000'
        if target == 'bg': initial = self.current_bg_color
        elif target == 'tile': initial = self.current_tile_color
        elif target == 'sb': initial = self.current_sb_color
        elif target == 'appbar': initial = self.current_appbar_color
        c = QColorDialog.getColor(QColor(initial), self)
        if c.isValid():
            name = c.name()
            if target == 'bg': self.current_bg_color = name; self.bg_color_btn.setStyleSheet(f"background-color: {name}")
            elif target == 'tile': self.current_tile_color = name; self.def_tile_btn.setStyleSheet(f"background-color: {name}")
            elif target == 'appbar': self.current_appbar_color = name; self.appbar_col_btn.setStyleSheet(f"background-color: {name}")
            elif target == 'sb': name = f"rgba({c.red()},{c.green()},{c.blue()},{c.alpha()/255})"; self.current_sb_color = name; self.sb_color_btn.setStyleSheet(f"background-color: {name}")
    def reset_defaults(self):
        if QMessageBox.question(self, "Reset Theme", "Reset all visual settings to default?") == QMessageBox.StandardButton.Yes:
            self.parent_window.config['settings'] = { "window_title": "Pop Metro Launcher", "background_type": "color", "background_value": "", "background_color": "#1d1d1d", "background_opacity": 100, "default_tile_color": "#00a300", "tile_size": 140, "group_columns": 2, "tile_radius": 0, "tile_alpha": 255, "global_hotkey": "<cmd>+p", "terminal_app": "xterm", "terminal_flags": ["-e"], "icon_theme": "default_theme", "appbar_accent_color": "#ffffff" }
            self.parent_window.config['start_btn'] = { "visible": True, "autohide": False, "position": "Bottom Left", "size": 60, "icon_type": "text", "icon_val": "❖", "color": "rgba(255, 255, 255, 0.2)" }
            self.parent_window.save_config(); self.parent_window.apply_background(); self.parent_window.refresh_ui(); self.parent_window.floating_btn.apply_settings(); self.close(); QMessageBox.information(self.parent_window, "Reset", "Theme settings have been reset.")
    def browse_bg(self):
        dlg = QFileDialog(self, "Select Image"); 
        if dlg.exec(): new_path = AssetManager.import_file(dlg.selectedFiles()[0], AssetManager.CUSTOM_BG_DIR); self.bg_value.setText(new_path); self.bg_type.setCurrentText("image")
    def browse_sb_icon(self):
        dlg = QFileDialog(self, "Select Icon"); 
        if dlg.exec(): new_path = AssetManager.import_file(dlg.selectedFiles()[0], AssetManager.CUSTOM_ICON_DIR); self.sb_icon_val.setText(new_path); self.sb_icon_type.setCurrentText("image")
    def populate_recent(self):
        recents = self.parent_window.config.get('recent_themes', []); 
        for theme in recents: self.recent_list.addItem(theme['name'])
    def get_sb_settings(self): return { "visible": self.sb_visible.isChecked(), "autohide": self.sb_autohide.isChecked(), "position": self.sb_pos.currentText(), "size": self.sb_size.value(), "icon_type": self.sb_icon_type.currentText(), "icon_val": self.sb_icon_val.text(), "color": self.current_sb_color }
    def save_and_close(self): self.parent_window.config['settings'] = self.get_current_settings(); self.parent_window.config['start_btn'] = self.get_sb_settings(); self.parent_window.save_config(); self.parent_window.apply_background(); self.parent_window.refresh_ui(); self.parent_window.floating_btn.apply_settings(); self.accept()
    def export_theme(self): 
        dlg = QFileDialog(self, "Export Theme"); dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave); 
        if dlg.exec(): fname = dlg.selectedFiles()[0]; 
        with open(fname, 'w') as f: json.dump({"name": os.path.basename(fname), "settings": self.get_current_settings(), "start_btn": self.get_sb_settings()}, f)
    def import_theme(self):
        dlg = QFileDialog(self, "Import Theme"); 
        if dlg.exec():
            try:
                with open(dlg.selectedFiles()[0], 'r') as f:
                    data = json.load(f)
                    if 'settings' in data: self.parent_window.config['settings'] = data['settings']
                    if 'start_btn' in data: self.parent_window.config['start_btn'] = data['start_btn']
                    self.parent_window.add_recent_theme(data.get('name','Theme'), data); self.save_and_close()
            except: pass
    def load_recent_theme(self, item):
        name = item.text()
        for t in self.parent_window.config.get('recent_themes', []):
            if t['name'] == name:
                s = t['settings']; 
                if 'settings' in s: self.parent_window.config['settings'] = s['settings']; self.parent_window.config['start_btn'] = s.get('start_btn', {})
                else: self.parent_window.config['settings'] = s
                self.parent_window.save_config(); self.parent_window.apply_background(); self.parent_window.refresh_ui(); self.parent_window.floating_btn.apply_settings(); self.close()
# --- CORE: Animated Tile Widget (LIVE TILE EDITION) ---
class MetroTile(QPushButton):
    def __init__(self, app_data, parent_window, group_index, item_index, is_add=False, is_back=False):
        super().__init__()
        self.app_data = app_data
        self.parent_window = parent_window
        self.group_index = group_index 
        self.item_index = item_index
        self.is_add = is_add
        
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        
        self.drag_start_position = None
        self.drop_target_mode = None
        self.insert_side = 'left' 
        
        # --- FIX: Initialize variables BEFORE creating animations ---
        self._scale = 1.0
        self._slide_y = 0.0  # <--- This must exist before QPropertyAnimation reads 'slide_pos'
        self.display_pixmap = None 
        self.is_showing_live = False

        # SCALE Animation
        self.anim = QPropertyAnimation(self, b"scale_prop")
        self.anim.setDuration(100)
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)

        # LIVE SLIDE Animation
        self.slide_anim = QPropertyAnimation(self, b"slide_pos")
        self.slide_anim.setDuration(500)
        self.slide_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # Live Tile Timer
        self.live_timer = QTimer(self)
        self.live_timer.timeout.connect(self.cycle_live_content)

        self.init_widgets()
        self.update_fixed_size() 
        self.update_icon_data()
        
        # Initialize Plugin
        if not self.is_add and self.app_data.get('type') == 'plugin':
            self.init_plugin()

    # --- PROPERTIES ---
    def get_scale_prop(self): return self._scale
    def set_scale_prop(self, val): self._scale = val; self.update() 
    scale_prop = pyqtProperty(float, get_scale_prop, set_scale_prop)

    def get_slide_pos(self): return self._slide_y
    def set_slide_pos(self, val): 
        self._slide_y = val
        if hasattr(self, 'slide_container'):
            self.slide_container.move(0, int(val))
    slide_pos = pyqtProperty(float, get_slide_pos, set_slide_pos)

    # --- INITIALIZATION ---
    def init_widgets(self):
        self.slide_container = QWidget(self)
        self.slide_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.static_face = QWidget(self.slide_container)
        self.icon_label = QLabel(self.static_face)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label = QLabel(self.static_face)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
        self.text_label.setWordWrap(True)
        
        self.live_face = QWidget(self.slide_container)
        self.live_layout = QVBoxLayout(self.live_face)
        self.live_layout.setContentsMargins(0,0,0,0)
        self.live_layout.setSpacing(0)

        self.delete_btn = QPushButton("×", self)
        self.delete_btn.setStyleSheet("background-color: red; color: white; border: none; font-weight: bold; font-size: 16px;")
        self.delete_btn.clicked.connect(self.request_delete)
        self.delete_btn.hide()

    def update_fixed_size(self):
        size = self.parent_window.config['settings'].get('tile_size', 140)
        spacing = 4 
        
        try: max_cols = int(self.parent_window.config['settings'].get('group_columns', 2))
        except: max_cols = 2
        
        rows = self.app_data.get('row_span', 1)
        requested_cols = self.app_data.get('col_span', 2 if self.app_data.get('wide_tile') else 1)
        cols = min(requested_cols, max_cols)
        
        width = (size * cols) + (spacing * (cols - 1))
        height = (size * rows) + (spacing * (rows - 1))
        self.setFixedSize(width, height)
        
        self.slide_container.setFixedSize(width, height * 2)
        self.static_face.setFixedSize(width, height)
        self.live_face.setFixedSize(width, height)
        self.live_face.move(0, height)

    def init_plugin(self):
        plugin_id = self.app_data.get('plugin_id')
        if plugin_id and self.parent_window.plugin_manager:
            plugin = self.parent_window.plugin_manager.plugins.get(plugin_id)
            if plugin and hasattr(plugin['module'], 'setup'):
                try:
                    plugin['module'].setup(self)
                    is_interactive = getattr(plugin['module'], 'WANT_INTERACTIVITY', False)
                    
                    if is_interactive:
                        self.slide_to_live()
                    else:
                        import random
                        delay = random.randint(3000, 8000)
                        self.live_timer.start(delay)
                        
                except Exception as e: print(f"Live Tile Error ({plugin_id}): {e}")

    # --- LIVE CYCLE LOGIC ---
    def cycle_live_content(self):
        if self.is_showing_live: self.slide_to_static()
        else: self.slide_to_live()
            
    def slide_to_live(self):
        self.slide_anim.stop()
        self.slide_anim.setStartValue(self._slide_y)
        self.slide_anim.setEndValue(-self.height())
        self.slide_anim.start()
        self.is_showing_live = True
        
    def slide_to_static(self):
        self.slide_anim.stop()
        self.slide_anim.setStartValue(self._slide_y)
        self.slide_anim.setEndValue(0)
        self.slide_anim.start()
        self.is_showing_live = False

    # --- VISUALS ---
    def update_icon_data(self):
        if self.is_add: self.icon_label.setText("➕"); self.text_label.setText("")
        else: self.text_label.setText(self.app_data.get('name', 'Unknown'))
        
        icon_path = self.app_data.get('icon')
        size = self.parent_window.config['settings'].get('tile_size', 140)
        spacing = 4
        
        rows = self.app_data.get('row_span', 1)
        try: max_cols = int(self.parent_window.config['settings'].get('group_columns', 2))
        except: max_cols = 2
        requested_cols = self.app_data.get('col_span', 2 if self.app_data.get('wide_tile') else 1)
        cols = min(requested_cols, max_cols)
        
        target_w = (size * cols) + (spacing * (cols - 1))
        target_h = (size * rows) + (spacing * (rows - 1))
        
        is_full = self.app_data.get('full_tile', False)
        if not is_full: 
            target_w = int(size * 0.5); target_h = int(size * 0.5)
            
        cached = get_cached_pixmap(icon_path, target_w, target_h) if icon_path else None
        
        if cached:
            if is_full:
                scaled = cached.scaled(target_w, target_h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                self.display_pixmap = scaled.copy((scaled.width()-target_w)//2, (scaled.height()-target_h)//2, target_w, target_h)
            else: self.display_pixmap = cached
            self.icon_label.setText("") 
        elif icon_path and QIcon.hasThemeIcon(icon_path):
            self.display_pixmap = QIcon.fromTheme(icon_path).pixmap(target_w, target_h); self.icon_label.setText("")
        else:
            self.display_pixmap = None; 
            if not self.is_add: self.icon_label.setText(self.app_data.get('name', '??')[:2].upper())
            
        if self.is_add: self.icon_label.setStyleSheet(f"font-size: {int(size*0.3)}px; color: #888; background: transparent;")
        else:
            self.icon_label.setStyleSheet(f"font-size: {int(size*0.3)}px; font-weight: bold; color: white; background: transparent;")
            self.text_label.setStyleSheet(f"font-size: {max(10, int(size*0.09))}px; font-weight: 500; color: white; background: transparent; padding: 2px;")
        self.update() 

    def resizeEvent(self, event):
        w, h = self.width(), self.height()
        self.slide_container.setFixedSize(w, h * 2)
        self.static_face.setFixedSize(w, h)
        self.live_face.setFixedSize(w, h)
        self.live_face.move(0, h)
        
        is_full = self.app_data.get('full_tile', False)
        if self.is_add:
            self.icon_label.setGeometry(0, 0, w, h); self.text_label.hide()
        elif is_full:
            self.icon_label.setGeometry(0, 0, w, h)
            self.text_label.setGeometry(5, 0, w-10, h-5); self.text_label.show() 
        else:
            th = int(h * 0.30); ih = h - th
            self.icon_label.setGeometry(0, 0, w, ih)
            self.text_label.setGeometry(5, ih, w-10, th); self.text_label.show()
            
        self.delete_btn.setGeometry(w-30, 0, 25, 25)
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self.rect().center(); painter.translate(c); painter.scale(self._scale, self._scale); painter.translate(-c)
        
        def_color = self.parent_window.config['settings'].get('default_tile_color', '#00a300')
        bg_color = QColor(self.app_data.get('color', def_color))
        alpha = self.parent_window.config['settings'].get('tile_alpha', 255); bg_color.setAlpha(alpha)
        if self.is_add: bg_color = QColor(60, 60, 60, alpha)
        
        radius = self.parent_window.config['settings'].get('tile_radius', 0)
        from PyQt6.QtGui import QPainterPath
        clip_path = QPainterPath(); clip_path.addRoundedRect(0.0, 0.0, float(self.width()), float(self.height()), float(radius), float(radius))
        painter.setClipPath(clip_path)
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(bg_color); painter.drawRect(self.rect())
        
        if not self.is_showing_live and self.display_pixmap and not self.display_pixmap.isNull():
             if self.app_data.get('full_tile', False): 
                 painter.drawPixmap(self.rect(), self.display_pixmap)
             else:
                 px = (self.width() - self.display_pixmap.width()) // 2
                 py = (self.height() - self.display_pixmap.height()) // 2
                 if not self.app_data.get('full_tile', False): 
                     py = (self.height() - int(self.height()*0.30) - self.display_pixmap.height()) // 2
                 painter.drawPixmap(px, py, self.display_pixmap)

        painter.setClipping(False) 
        if self.hasFocus(): 
            painter.setPen(QColor(0, 120, 215)); painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(1,1,-1,-1), radius, radius)
        if self.drop_target_mode == 'insert' and not self.is_add:
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor(255, 255, 255))
            if self.insert_side == 'left': painter.drawRect(0, 0, 4, self.height())
            else: painter.drawRect(self.width()-4, 0, 4, self.height())
        painter.end() 

    # --- EVENTS ---
    def enterEvent(self, event):
        self.anim.stop(); self.anim.setStartValue(self._scale); self.anim.setEndValue(1.05); self.anim.start(); super().enterEvent(event)
    def leaveEvent(self, event):
        self.anim.stop(); self.anim.setStartValue(self._scale); self.anim.setEndValue(1.0); self.anim.start(); super().leaveEvent(event)
    def focusInEvent(self, event): self.update(); super().focusInEvent(event)
    def focusOutEvent(self, event): self.update(); super().focusOutEvent(event)

    def mousePressEvent(self, e):
        e.accept()
        if e.button() == Qt.MouseButton.LeftButton: self.drag_start_position = e.position().toPoint()
        else: self.drag_start_position = None
        self.anim.stop(); self.anim.setStartValue(self._scale); self.anim.setEndValue(0.95); self.anim.start()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        e.accept()
        # 1. Reset Scale Animation (Visual "Click" effect)
        if hasattr(self, 'anim'):
            self.anim.stop()
            self.anim.setStartValue(self._scale)
            self.anim.setEndValue(1.0)
            self.anim.start()
        
        super().mouseReleaseEvent(e)
        
        # 2. Handle Right Click (Open Menu)
        if e.button() == Qt.MouseButton.RightButton:
            if not self.is_add:
                # Open the App Bar
                self.parent_window.app_bar.toggle_for_tile(self)
            return

        # 3. Handle Left Click (Launch App)
        if e.button() == Qt.MouseButton.LeftButton:
            if self.rect().contains(e.position().toPoint()):
                if self.drag_start_position:
                    dist = (e.position().toPoint() - self.drag_start_position).manhattanLength()
                    if dist < 5: 
                        self.trigger_action()

    def cycle_size(self):
        try: max_cols = int(self.parent_window.config['settings'].get('group_columns', 2))
        except: max_cols = 2
        all_sizes = [(1, 1), (1, 2), (2, 2)]
        valid_sizes = [s for s in all_sizes if s[1] <= max_cols]
        if not valid_sizes: valid_sizes = [(1, 1)]
        current = (self.app_data.get('row_span', 1), self.app_data.get('col_span', 2 if self.app_data.get('wide_tile') else 1))
        if current in valid_sizes: new_size = valid_sizes[(valid_sizes.index(current) + 1) % len(valid_sizes)]
        else: new_size = valid_sizes[0]
        self.app_data['row_span'] = new_size[0]; self.app_data['col_span'] = new_size[1]; self.app_data['wide_tile'] = (new_size[1] > 1)
        self.parent_window.save_config(); self.parent_window.refresh_ui()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton): event.ignore(); return
        if self.is_add: return
        if self.drag_start_position is None: return
        if (event.position().toPoint() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance(): return
        event.accept() 
        drag = QDrag(self)
        mime_data = QMimeData(); mime_data.setText(f"{self.group_index}|{self.item_index}")
        drag.setMimeData(mime_data); drag.setPixmap(self.grab()); drag.setHotSpot(event.position().toPoint())
        drag.exec(Qt.DropAction.MoveAction)
        self.drag_start_position = None

    def trigger_action(self):
        if self.is_add: self.parent_window.add_new_item(self.group_index)
        elif not self.parent_window.is_edit_mode:
            if self.app_data.get('type') == 'plugin': self.parent_window.plugin_manager.execute(self.app_data.get('plugin_id'), self.parent_window)
            else: self.launch_app()

    def launch_app(self):
        script = self.app_data.get('script_path', '')
        exe = self.app_data.get('python_path', '')
        
        # --- PRIORITY 1: Handle AppImages & Direct Binaries ---
        # We check this FIRST to avoid the "SYSTEM" logic breaking paths with spaces
        if (script and script.lower().endswith(".appimage")) or exe == "BINARY":
            if os.path.exists(script):
                try:
                    # 1. Force Executable Permissions (chmod +x)
                    st = os.stat(script)
                    os.chmod(script, st.st_mode | 0o111)
                except Exception as e: 
                    print(f"Permission Warning: {e}")

                try:
                    # 2. Launch directly as a list (Handles spaces in path correctly!)
                    # We DO NOT use shell=True or split() here.
                    subprocess.Popen([script], cwd=os.path.dirname(script))
                    self.parent_window.toggle_visibility()
                    return # Done, stop here
                except Exception as e:
                    self.show_error(f"AppImage Error:\n{e}")
                    return
            else:
                self.show_error(f"File not found:\n{script}")
                return

        # --- PRIORITY 2: Standard System Commands (e.g. 'firefox') ---
        if exe == "SYSTEM":
            try: 
                # shlex.split handles quotes correctly, unlike .split()
                import shlex
                subprocess.Popen(shlex.split(script)) 
                self.parent_window.toggle_visibility() 
            except Exception as e: self.show_error(str(e))
            
        # --- PRIORITY 3: Python Scripts / Terminal Commands ---
        elif script and os.path.exists(script):
            # Get configured terminal
            term_app = self.parent_window.config['settings'].get('terminal_app', 'xterm')
            term_flags = self.parent_window.config['settings'].get('terminal_flags', ['-e'])
            
            try:
                # Construct Command: terminal [flags] bash -c "python script.py; exec bash"
                full_cmd = [term_app] + term_flags + ['bash', '-c', f'"{exe}" "{script}"; exec bash']
                
                subprocess.Popen(full_cmd, cwd=os.path.dirname(script))
                self.parent_window.toggle_visibility()
                
            except Exception as e: self.show_error(f"Failed to launch terminal ({term_app}):\n{e}")
            
        else: self.show_error(f"Script not found:\n{script}")

    def dragEnterEvent(self, event):
        if event.source() and isinstance(event.source(), MetroTile): event.accept()
        else: event.ignore()
    def dragMoveEvent(self, event):
        if event.source() and isinstance(event.source(), MetroTile): 
             pos = event.position().toPoint(); self.insert_side = 'left' if pos.x() < self.width() / 2 else 'right'
             self.drop_target_mode = 'insert'; self.update(); event.setDropAction(Qt.DropAction.MoveAction); event.accept()
    def dragLeaveEvent(self, event): self.drop_target_mode = None; self.update(); super().dragLeaveEvent(event)
    def dropEvent(self, event):
        self.drop_target_mode = None; self.update(); source = event.source()
        if source and source != self:
            if self.is_add: self.parent_window.handle_drop(source.group_index, source.item_index, self.group_index, -1)
            else: 
                off = 0 if self.insert_side == 'left' else 1
                self.parent_window.handle_drop(source.group_index, source.item_index, self.group_index, self.item_index + off)
    def show_error(self, text): QMessageBox.critical(self, "Error", text)
    def request_delete(self): self.parent_window.delete_item(self.group_index, self.item_index)
    def change_name(self):
        n, ok = QInputDialog.getText(self, "Rename", "Name:", text=self.app_data['name'])
        if ok and n: self.app_data['name'] = n; self.text_label.setText(n); self.parent_window.save_config()
    def change_icon(self):
        p, _ = QFileDialog.getOpenFileName(self, "Select Icon", filter="Images (*.png *.jpg *.svg *.ico)")
        if p:
            # Copy to assets/custom/icons
            new_path = AssetManager.import_file(p, AssetManager.CUSTOM_ICON_DIR)
            self.app_data['icon'] = new_path
            self.update_icon_data()
            self.parent_window.save_config()
    def remove_icon(self): self.app_data['icon'] = None; self.update_icon_data(); self.parent_window.save_config()
    def change_color(self):
        c = QColorDialog.getColor(QColor(self.app_data.get('color', '#000')), self)
        if c.isValid(): self.app_data['color'] = c.name(); self.update(); self.parent_window.save_config()
    def edit_details(self):
        dlg = AppEditorDialog(self, self.parent_window, self.app_data)
        if dlg.exec(): self.app_data.update(dlg.get_data()); self.parent_window.save_config(); self.parent_window.refresh_ui()
# --- GROUP WIDGET (Required for layout) ---
class GroupWidget(QWidget):
    def __init__(self, parent_window, group_data, group_index):
        super().__init__()
        self.parent_window = parent_window
        self.group_data = group_data
        self.group_index = group_index
        
        try:
            size = int(self.parent_window.config['settings'].get('tile_size', 140))
            cols = int(self.parent_window.config['settings'].get('group_columns', 2))
        except:
            size = 140
            cols = 2
            
        spacing = 4
        self.setFixedWidth((size * cols) + (spacing * (cols - 1)) + 40)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 40, 0)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        header = QHBoxLayout()
        self.title = QLabel(group_data.get('name', 'Group'))
        self.title.setStyleSheet("color: white; font-size: 20px; font-family: 'Segoe UI Light';")
        header.addWidget(self.title)
        
        if self.parent_window.is_edit_mode:
            d = QPushButton("Del")
            d.setStyleSheet("color: red; border: none;")
            d.clicked.connect(self.delete_self)
            header.addWidget(d)
            
            r = QPushButton("Ren")
            r.setStyleSheet("color: #aaa; border: none;")
            r.clicked.connect(self.rename_self)
            header.addWidget(r)
            
        self.main_layout.addLayout(header)
        
        self.grid = QGridLayout()
        self.grid.setSpacing(spacing)
        self.grid.setContentsMargins(0, 10, 0, 0)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        g_wid = QWidget()
        g_wid.setLayout(self.grid)
        self.main_layout.addWidget(g_wid)
        self.main_layout.addStretch()
        
        self.populate_grid()

    def populate_grid(self):
        grid_map = {} 
        try:
            max_cols = int(self.parent_window.config['settings'].get('group_columns', 2))
        except: max_cols = 2
        if max_cols < 1: max_cols = 1

        def is_available(r, c, r_span, c_span):
            if c + c_span > max_cols: return False
            for ir in range(r_span):
                for ic in range(c_span):
                    if grid_map.get((r + ir, c + ic), False):
                        return False
            return True

        def mark_occupied(r, c, r_span, c_span):
            for ir in range(r_span):
                for ic in range(c_span):
                    grid_map[(r + ir, c + ic)] = True

        for i, app in enumerate(self.group_data.get('apps', [])):
            r_span = app.get('row_span', 1)
            c_span = app.get('col_span', 2 if app.get('wide_tile') else 1)
            
            # Safety clamp: if tile is wider than the group, force it to fit
            if c_span > max_cols: c_span = max_cols

            found = False
            search_r = 0
            
            # Loop limit prevents infinite loop crash
            while not found and search_r < 1000: 
                for search_c in range(max_cols):
                    if is_available(search_r, search_c, r_span, c_span):
                        tile = MetroTile(app, self.parent_window, self.group_index, i)
                        if self.parent_window.is_edit_mode: tile.delete_btn.show()
                        self.grid.addWidget(tile, search_r, search_c, r_span, c_span)
                        mark_occupied(search_r, search_c, r_span, c_span)
                        found = True
                        break
                if not found:
                    search_r += 1
                    
        if self.parent_window.is_edit_mode:
            add_r = 0
            found_add = False
            while not found_add and add_r < 1000:
                for add_c in range(max_cols):
                    if is_available(add_r, add_c, 1, 1):
                        self.grid.addWidget(MetroTile({}, self.parent_window, self.group_index, -1, is_add=True), add_r, add_c)
                        found_add = True
                        break
                add_r += 1

    def delete_self(self):
        if QMessageBox.question(self, "Delete", "Delete group?") == QMessageBox.StandardButton.Yes: self.parent_window.delete_group(self.group_index)
    def rename_self(self):
        n, ok = QInputDialog.getText(self, "Rename", "Name:", text=self.group_data['name'])
        if ok: self.group_data['name'] = n; self.title.setText(n); self.parent_window.save_config()
# --- MAIN WINDOW (UPDATED FOR TRANSPARENCY) ---
class LauncherWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 1. Initialize Assets & Config
        AssetManager.ensure_directories()
        
        self.config_file = 'config.json'
        self.is_edit_mode = False
        self.load_config() 
        
        # 2. App Bar
        self.app_bar = AppBar(self)
        
        self.plugin_manager = PluginManager() 
        self.init_ui() 
        
        # 3. Gamepad Worker
        self.gamepad_thread = GamepadWorker()
        self.gamepad_thread.btn_pressed.connect(self.handle_gamepad_btn)
        self.gamepad_thread.dpad.connect(self.handle_gamepad_nav)
        self.gamepad_thread.start()

        self.setup_tray()
        self.setup_shortcuts()
        self.floating_btn = FloatingStartButton(self); self.floating_btn.hide()
        self.save_timer = QTimer(self); self.save_timer.setSingleShot(True); self.save_timer.timeout.connect(self._save_to_disk)

    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.showFullScreen()
        
        # --- CRITICAL: Allow Transparency ---
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # ------------------------------------
        
        self.central = QWidget(); self.setCentralWidget(self.central)
        self.apply_background() # Sets central to transparent now
        
        layout = QVBoxLayout(self.central); layout.setContentsMargins(40, 60, 40, 40)
        
        tb = QHBoxLayout()
        title = QLabel("Start"); title.setStyleSheet("font-size: 30px; font-weight: 300; color: white; font-family: 'Segoe UI Light';"); tb.addWidget(title); tb.addStretch()
        
        self.add_grp = QPushButton("+ Group"); self.add_grp.clicked.connect(self.add_group); self.add_grp.hide(); self.style_btn(self.add_grp); tb.addWidget(self.add_grp)
        self.edit_btn = QPushButton("✎ Edit"); self.edit_btn.setCheckable(True); self.edit_btn.setFixedSize(100, 40); self.edit_btn.clicked.connect(self.toggle_edit); self.style_btn(self.edit_btn); tb.addWidget(self.edit_btn)
        cog = QPushButton("⚙"); cog.setFixedSize(50, 40); cog.clicked.connect(self.open_settings); self.style_btn(cog); tb.addWidget(cog)
        close = QPushButton("✕"); close.setFixedSize(50, 40); close.setStyleSheet("background: transparent; color: white; font-size: 20px; border: none;"); close.clicked.connect(self.toggle_visibility); tb.addWidget(close)
        layout.addLayout(tb)

        self.scroll = KineticScrollArea() 
        self.g_con = QWidget(); self.g_con.setStyleSheet("background: transparent;")
        self.g_layout = QHBoxLayout(self.g_con); self.g_layout.setAlignment(Qt.AlignmentFlag.AlignLeft); self.g_layout.setSpacing(0)
        self.scroll.setWidget(self.g_con); layout.addWidget(self.scroll)
        self.refresh_ui()

    # --- NEW: Paint Event Handles Background & Opacity ---
    def paintEvent(self, event):
        painter = QPainter(self)
        
        # 1. Get Opacity (1-100 -> 0.0-1.0)
        s = self.config.get('settings', {})
        opacity = s.get('background_opacity', 100) / 100.0
        painter.setOpacity(opacity)
        
        # 2. Draw Background
        bg_type = s.get('background_type', 'color')
        
        if bg_type == 'image' and os.path.exists(s.get('background_value', '')):
            path = s.get('background_value')
            # Use cached loader or load fresh
            if path in ICON_CACHE: pix = ICON_CACHE[path]
            else: pix = QPixmap(path); ICON_CACHE[path] = pix
            
            if not pix.isNull():
                # Scale to cover window (Crop center)
                scaled = pix.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                x = (self.width() - scaled.width()) // 2
                y = (self.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
        else:
            # Draw Color
            c_hex = s.get('background_color', '#1d1d1d')
            painter.fillRect(self.rect(), QColor(c_hex))
            
    # --- UPDATED: Removes Stylesheet Conflict ---
    def apply_background(self):
        # We now paint the background in paintEvent, so we make the 
        # container transparent to let the paintEvent show through.
        self.central.setStyleSheet("background: transparent;")
        self.central.setObjectName("BG")
        self.update() # Trigger repaint

    # --- GAMEPAD LOGIC ---
    def handle_gamepad_btn(self, btn):
        toggle_btn = self.config['settings'].get('gamepad_hotkey', 'GUIDE')
        if btn == toggle_btn:
            self.toggle_visibility(); return

        if not self.isVisible(): return
        
        focus_widget = self.focusWidget()
        if btn == 'A': 
            if isinstance(focus_widget, MetroTile): focus_widget.trigger_action()
            elif isinstance(focus_widget, QPushButton): focus_widget.click()
        elif btn == 'B': 
            if hasattr(self, 'app_bar') and self.app_bar.isVisible(): self.app_bar.hide_bar()
        elif btn == 'Y': 
            if isinstance(focus_widget, MetroTile): self.app_bar.toggle_for_tile(focus_widget)
        elif btn == 'START': self.edit_btn.click()

    def handle_gamepad_nav(self, direction):
        if not self.isVisible(): return
        all_tiles = []
        for i in range(self.g_layout.count()):
            item = self.g_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), GroupWidget):
                group = item.widget()
                for j in range(group.grid.count()):
                    tile = group.grid.itemAt(j).widget()
                    if tile and tile.isVisible(): all_tiles.append(tile)

        if not all_tiles: return
        current = self.focusWidget()
        if not current or not isinstance(current, MetroTile): all_tiles[0].setFocus(); return

        try: idx = all_tiles.index(current)
        except ValueError: idx = 0

        next_idx = idx
        if direction == 'RIGHT': next_idx = min(idx + 1, len(all_tiles) - 1)
        elif direction == 'LEFT': next_idx = max(idx - 1, 0)
        elif direction == 'DOWN': next_idx = min(idx + 2, len(all_tiles) - 1)
        elif direction == 'UP': next_idx = max(idx - 2, 0)

        target = all_tiles[next_idx]
        target.setFocus(); self.scroll.ensureWidgetVisible(target)

    # [Keep resizeEvent, mousePressEvent, load_config, save_config, _save_to_disk, closeEvent, add_recent_theme, setup_shortcuts, setup_tray, toggle_visibility, get_theme_icon_path, refresh_ui, keyPressEvent, focusOutEvent, style_btn, toggle_edit, open_settings, add_group, delete_group, add_new_item, delete_item, handle_drop exactly as they were]
    def resizeEvent(self, event):
        if hasattr(self, 'app_bar') and self.app_bar.isVisible():
            self.app_bar.setGeometry(0, self.height() - 100, self.width(), 100)
            self.app_bar.raise_()
        super().resizeEvent(event)
    def mousePressEvent(self, event):
        if hasattr(self, 'app_bar') and self.app_bar.isVisible():
            if not self.app_bar.geometry().contains(event.pos()): self.app_bar.hide_bar()
        super().mousePressEvent(event)
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f: self.config = json.load(f)
            except: self.config = {}
        else: self.config = {}
        if "groups" not in self.config: self.config["groups"] = [{"name": "Start", "apps": []}]
        if "recent_themes" not in self.config: self.config["recent_themes"] = []
        if "settings" not in self.config: self.config["settings"] = {}
        unique_groups = []; seen = set()
        for g in self.config['groups']:
            sig = json.dumps(g, sort_keys=True)
            if sig not in seen: unique_groups.append(g); seen.add(sig)
        if len(unique_groups) < len(self.config['groups']): self.config['groups'] = unique_groups; self._save_to_disk()
        if 'terminal_app' not in self.config['settings']:
            available = get_installed_terminals()
            if available: self.config['settings']['terminal_app'] = available[0][1]; self.config['settings']['terminal_flags'] = available[0][2]
            else: self.config['settings']['terminal_app'] = "xterm"; self.config['settings']['terminal_flags'] = ["-e"]
    def save_config(self): self.save_timer.start(2000)
    def _save_to_disk(self): 
        with open(self.config_file, 'w') as f: json.dump(self.config, f, indent=4)
    def closeEvent(self, event): self._save_to_disk(); event.accept()
    def add_recent_theme(self, name, s):
        rec = [t for t in self.config.get('recent_themes', []) if t['name'] != name]; rec.insert(0, {"name": name, "settings": s}); self.config['recent_themes'] = rec[:3]; self._save_to_disk()
    def setup_shortcuts(self):
        hk = self.config['settings'].get('global_hotkey', '<cmd>+p')
        try: keyboard.GlobalHotKeys({hk: self.toggle_visibility}).start()
        except: pass
    def setup_tray(self):
        self.tray = QSystemTrayIcon(QIcon.fromTheme("applications-system"), self)
        m = QMenu(); q = QAction("Quit", self); q.triggered.connect(QApplication.instance().quit); m.addAction(q)
        self.tray.setContextMenu(m); self.tray.show()
        self.tray.activated.connect(lambda r: self.toggle_visibility() if r == QSystemTrayIcon.ActivationReason.Trigger else None)
    def toggle_visibility(self):
        if self.isVisible(): self.hide(); self.floating_btn.apply_settings()
        else: self.showFullScreen(); self.activateWindow(); self.floating_btn.hide(); self.setFocus()
    def get_theme_icon_path(self):
        theme_name = self.config['settings'].get('icon_theme', 'default_theme')
        custom_path = os.path.join(AssetManager.THEMES_DIR, theme_name)
        if os.path.exists(custom_path): return custom_path
        return AssetManager.SYSTEM_DIR
    def refresh_ui(self):
        if hasattr(self, 'app_bar'): self.app_bar.hide_bar()
        self.setUpdatesEnabled(False)
        while self.g_layout.count(): 
            item = self.g_layout.takeAt(0); widget = item.widget()
            if widget is not None: widget.setParent(None); widget.deleteLater()
        for i, g in enumerate(self.config.get('groups', [])): self.g_layout.addWidget(GroupWidget(self, g, i))
        self.g_layout.addStretch(); self.setUpdatesEnabled(True)
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            focus_widget = self.focusWidget()
            if isinstance(focus_widget, MetroTile): focus_widget.trigger_action(); return
            elif isinstance(focus_widget, QPushButton): focus_widget.click(); return
        super().keyPressEvent(event)
    def focusOutEvent(self, event):
        if hasattr(self, 'app_bar'): self.app_bar.hide_bar()
        super().focusOutEvent(event)
    def style_btn(self, b): b.setStyleSheet("QPushButton { background-color: rgba(0,0,0,0.5); color: white; border: 1px solid rgba(255,255,255,0.3); font-size: 14px; border-radius: 5px; padding: 5px; } QPushButton:checked { background-color: #e51400; border: none; }")
    def toggle_edit(self): self.is_edit_mode = self.edit_btn.isChecked(); self.add_grp.setVisible(self.is_edit_mode); self.refresh_ui()
    def open_settings(self): SettingsDialog(self).exec()
    def add_group(self):
        n, ok = QInputDialog.getText(self, "New Group", "Name:")
        if ok and n: self.config['groups'].append({"name": n, "apps": []}); self.save_config(); self.refresh_ui()
    def delete_group(self, idx): 
        if 0 <= idx < len(self.config['groups']): del self.config['groups'][idx]; self.save_config(); self.refresh_ui()
    def add_new_item(self, group_index):
        dlg = AppEditorDialog(self, self)
        if dlg.exec():
            new_data = dlg.get_data()
            if new_data.get('name'): self.config['groups'][group_index]['apps'].append(new_data); self.save_config(); self.refresh_ui()
    def delete_item(self, g_idx, i_idx):
        if QMessageBox.question(self, "Delete", "Remove item?") == QMessageBox.StandardButton.Yes: del self.config['groups'][g_idx]['apps'][i_idx]; self.save_config(); self.refresh_ui()
    def handle_drop(self, s_g, s_i, d_g, d_i):
        item = self.config['groups'][s_g]['apps'].pop(s_i)
        if s_g == d_g and s_i < d_i: d_i -= 1
        if d_i == -1: self.config['groups'][d_g]['apps'].append(item)
        else: self.config['groups'][d_g]['apps'].insert(d_i, item)
        self.save_config(); QTimer.singleShot(10, self.refresh_ui)
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    window = LauncherWindow()
    sys.exit(app.exec())
