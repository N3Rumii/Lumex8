"""MetroTile — animated, draggable tile widget with context actions."""

import os
import shlex
import subprocess

from PyQt6.QtCore import Qt, QMimeData, QPropertyAnimation, QEasingCurve, pyqtProperty, QTimer
from PyQt6.QtGui import QPixmap, QColor, QDrag, QIcon, QPainter, QFont, QFontMetrics, QPainterPath
from PyQt6.QtWidgets import (QPushButton, QLabel, QStyle, QSizePolicy, QMessageBox,
                             QFileDialog, QColorDialog, QMenu, QInputDialog,
                             QApplication, QWidget, QVBoxLayout)

from lumex8.utils import get_cached_pixmap
from lumex8.dialogs.app_editor import AppEditorDialog


class MetroTile(QPushButton):
    """An individual animated tile in the launcher grid.

    Supports drag-and-drop reordering, scale animation on hover/press,
    wide-tile (2x1) and full-tile modes, custom colours and icons,
    and a contextual AppBar / right-click menu for editing.
    """

    def __init__(self, app_data, parent_window, group_index, item_index,
                 is_add=False, is_back=False) -> None:
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
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        self.drag_start_position = None
        self.drop_target_mode = None
        self._hover_border = False
        self.insert_side = "left"

        self._scale = 1.0
        self.anim = QPropertyAnimation(self, b"scale_prop")
        self.anim.setDuration(100)
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)

        # Live slide variables
        self._slide_y = 0.0
        self.display_pixmap = None
        self._image_is_file = False  # True when pixmap loaded from a real file
        self.is_showing_live = False

        self.slide_anim = QPropertyAnimation(self, b"slide_pos")
        self.slide_anim.setDuration(500)
        self.slide_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.live_timer = QTimer(self)
        self.live_timer.timeout.connect(self.cycle_live_content)

        self.init_widgets()
        self.update_fixed_size()
        self.update_icon_data()

        # Init plugin if tile is a plugin type (including legacy "special")
        if not self.is_add and self.app_data.get("type") in ("plugin", "special"):
            self.init_plugin()

    # --- Property for animation ---
    def get_scale_prop(self):
        return self._scale

    def set_scale_prop(self, val):
        self._scale = val
        self.update()

    scale_prop = pyqtProperty(float, get_scale_prop, set_scale_prop)

    def get_slide_pos(self):
        return self._slide_y

    def set_slide_pos(self, val):
        self._slide_y = val
        if hasattr(self, "slide_container"):
            self.slide_container.move(0, int(val))

    slide_pos = pyqtProperty(float, get_slide_pos, set_slide_pos)

    # --- Widget children ---
    def init_widgets(self) -> None:
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
        self.live_layout.setContentsMargins(0, 0, 0, 0)
        self.live_layout.setSpacing(0)

        self.delete_btn = QPushButton("\u00d7", self)
        self.delete_btn.setStyleSheet(
            "background-color: red; color: white; border: none; font-weight: bold; font-size: 16px;"
        )
        self.delete_btn.clicked.connect(self.request_delete)
        self.delete_btn.hide()

        self.update_content()

    def update_fixed_size(self) -> None:
        size = self.parent_window.config["settings"].get("tile_size", 140)
        spacing = 4

        try:
            max_cols = int(self.parent_window.config["settings"].get("group_columns", 2))
        except (ValueError, TypeError):
            max_cols = 2

        rows = self.app_data.get("row_span", 1)
        requested_cols = self.app_data.get("col_span", 2 if self.app_data.get("wide_tile") else 1)
        cols = min(requested_cols, max_cols)

        width = (size * cols) + (spacing * (cols - 1))
        height = (size * rows) + (spacing * (rows - 1))
        self.setFixedSize(width, height)

        self.slide_container.setFixedSize(width, height * 2)
        self.static_face.setFixedSize(width, height)
        self.live_face.setFixedSize(width, height)
        self.live_face.move(0, height)

    def _add_tile_icon(self) -> None:
        """Set the add-tile icon, preferring theme icon over unicode."""
        add_icon = QIcon.fromTheme("list-add")
        if not add_icon.isNull():
            px = add_icon.pixmap(self.icon_label.size(),
                                 mode=QIcon.Mode.Normal,
                                 state=QIcon.State.Off)
            self.icon_label.setPixmap(px)
        else:
            # Fallback: bold '+' character (works on any font)
            self.icon_label.setText("+")

    def update_content(self) -> None:
        if self.is_add:
            self._add_tile_icon()
            self.text_label.setText("")
            self.text_label.hide()
        elif self.is_back:
            pass
        else:
            name_text = self.app_data.get("name", "Unknown")
            self.text_label.setText(name_text)
            self.update_icon_data()
            # Hide text if hide_label is set
            hide_label = self.app_data.get("hide_label", False)
            if hide_label:
                self.text_label.hide()
            else:
                self.text_label.show()

    def update_icon_data(self) -> None:
        if self.is_add:
            self._add_tile_icon()
            return
        else:
            self.text_label.setText(self.app_data.get("name", "Unknown"))

        icon_path = self.app_data.get("icon")
        name = self.app_data.get("name", "??")
        size = self.parent_window.config["settings"].get("tile_size", 140)
        spacing = 4

        rows = self.app_data.get("row_span", 1)
        try:
            max_cols = int(self.parent_window.config["settings"].get("group_columns", 2))
        except (ValueError, TypeError):
            max_cols = 2
        requested_cols = self.app_data.get("col_span", 2 if self.app_data.get("wide_tile") else 1)
        cols = min(requested_cols, max_cols)

        target_w = (size * cols) + (spacing * (cols - 1))
        target_h = (size * rows) + (spacing * (rows - 1))

        is_full = self.app_data.get("full_tile", False)
        if not is_full:
            target_w = int(size * 0.5)
            target_h = int(size * 0.5)

        cached = get_cached_pixmap(icon_path, target_w, target_h) if icon_path else None

        if cached:
            self._image_is_file = True
            if is_full:
                scaled = cached.scaled(
                    target_w, target_h,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.display_pixmap = scaled.copy(
                    (scaled.width() - target_w) // 2,
                    (scaled.height() - target_h) // 2,
                    target_w, target_h,
                )
            else:
                self.display_pixmap = cached
            self.icon_label.setText("")
        elif icon_path and QIcon.hasThemeIcon(icon_path):
            self._image_is_file = False
            self.display_pixmap = QIcon.fromTheme(icon_path).pixmap(target_w, target_h)
            self.icon_label.setText("")
        else:
            self._image_is_file = False
            self.display_pixmap = None
            if not self.is_add:
                self.icon_label.setText(name[:2].upper())

        if self.is_add:
            self.icon_label.setStyleSheet(
                f"font-size: {int(size*0.3)}px; color: #888; background: transparent;"
            )
        else:
            self.icon_label.setStyleSheet(
                f"font-size: {int(size*0.3)}px; font-weight: bold; color: white; background: transparent;"
            )
            self.text_label.setStyleSheet(
                f"font-size: {max(10, int(size*0.09))}px; font-weight: 500; color: white; background: transparent; padding: 2px;"
            )

        # Hide text only when hide_label is explicitly set
        hide_label = self.app_data.get("hide_label", False)
        if hide_label:
            self.text_label.hide()
        elif not self.is_add:
            self.text_label.show()

        self.update()

    def resizeEvent(self, event) -> None:
        w = self.width()
        h = self.height()
        self.slide_container.setFixedSize(w, h * 2)
        self.static_face.setFixedSize(w, h)
        self.live_face.setFixedSize(w, h)
        self.live_face.move(0, h)

        is_full = self.app_data.get("full_tile", False)
        hide_label = self.app_data.get("hide_label", False)
        show_text = not hide_label

        if self.is_add:
            self.icon_label.setGeometry(0, 0, w, h)
            self._add_tile_icon()
            self.text_label.hide()
        elif not show_text:
            # No text — icon fills entire tile
            self.icon_label.setGeometry(0, 0, w, h)
            self.text_label.hide()
        elif is_full:
            self.icon_label.setGeometry(0, 0, w, h)
            self.text_label.setGeometry(5, 0, w - 10, h - 5)
            self.text_label.setVisible(show_text)
        else:
            th = int(h * 0.30)
            ih = h - th
            self.icon_label.setGeometry(0, 0, w, ih)
            self.text_label.setGeometry(5, ih, w - 10, th)
            self.text_label.setVisible(show_text)

        self.delete_btn.setGeometry(w - 30, 0, 25, 25)
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self.rect().center()
        painter.translate(c)
        painter.scale(self._scale, self._scale)
        painter.translate(-c)

        def_color = self.parent_window.config["settings"].get("default_tile_color", "#00a300")
        bg_color = QColor(self.app_data.get("color", def_color))
        alpha = self.parent_window.config["settings"].get("tile_alpha", 255)
        bg_color.setAlpha(alpha)
        if self.is_add:
            bg_color = QColor(60, 60, 60, alpha)

        radius = self.parent_window.config["settings"].get("tile_radius", 0)
        clip_path = QPainterPath()
        clip_path.addRoundedRect(
            0.0, 0.0,
            float(self.width()), float(self.height()),
            float(radius), float(radius),
        )
        painter.setClipPath(clip_path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawRect(self.rect())

        # Draw icon pixmap if not showing live face
        if not self.is_showing_live and self.display_pixmap and not self.display_pixmap.isNull():
            if self.app_data.get("full_tile", False):
                painter.drawPixmap(self.rect(), self.display_pixmap)
            else:
                px = (self.width() - self.display_pixmap.width()) // 2
                py = (self.height() - int(self.height() * 0.30) - self.display_pixmap.height()) // 2
                painter.drawPixmap(px, py, self.display_pixmap)

        painter.setClipping(False)
        if self.hasFocus():
            painter.setPen(QColor(0, 120, 215))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), radius, radius)

        if self._hover_border:
            painter.setPen(QColor(255, 255, 255, 120))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), radius, radius)

        if self.drop_target_mode == "insert" and not self.is_add:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255))
            if self.insert_side == "left":
                painter.drawRect(0, 0, 4, self.height())
            else:
                painter.drawRect(self.width() - 4, 0, 4, self.height())

        painter.end()

    def enterEvent(self, event) -> None:
        self.anim.stop()
        self.anim.setStartValue(self._scale)
        self.anim.setEndValue(1.05)
        self.anim.start()
        self._hover_border = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.anim.stop()
        self.anim.setStartValue(self._scale)
        self.anim.setEndValue(1.0)
        self.anim.start()
        self._hover_border = False
        self.clearFocus()
        self.update()
        super().leaveEvent(event)

    def focusInEvent(self, event) -> None:
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        self.update()
        super().focusOutEvent(event)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = e.position().toPoint()
        self.anim.stop()
        self.anim.setStartValue(self._scale)
        self.anim.setEndValue(0.95)
        self.anim.start()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        super().mouseReleaseEvent(e)
        if hasattr(self, 'anim'):
            self.anim.stop()
            self.anim.setStartValue(self._scale)
            self.anim.setEndValue(1.0)
            self.anim.start()

        # Right-click → AppBar
        if e.button() == Qt.MouseButton.RightButton:
            if not self.is_add:
                if hasattr(self.parent_window, 'app_bar'):
                    self.parent_window.app_bar.toggle_for_tile(self)
            return

        # Left-click → launch (only if not a drag)
        if e.button() == Qt.MouseButton.LeftButton:
            if self.rect().contains(e.position().toPoint()):
                if self.drag_start_position:
                    dist = (e.position().toPoint() - self.drag_start_position).manhattanLength()
                    if dist < 5:
                        self.trigger_action()

    def mouseMoveEvent(self, event) -> None:
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if self.is_add:
            return
        if self.drag_start_position is None:
            return
        current_pos = event.position().toPoint()
        if (current_pos - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(f"{self.group_index}|{self.item_index}")
        drag.setMimeData(mime_data)
        drag.setPixmap(self.grab())
        drag.setHotSpot(current_pos)
        drag.exec(Qt.DropAction.MoveAction)

    def trigger_action(self) -> None:
        if self.is_add:
            self.parent_window.add_new_item(self.group_index)
        elif not self.parent_window.is_edit_mode:
            if self.app_data.get("type") in ("plugin", "special"):
                self.parent_window.plugin_manager.execute(
                    self.app_data.get("plugin_id"), self.parent_window
                )
            else:
                self.launch_app()

    def launch_app(self) -> None:
        script = self.app_data.get("script_path", "")
        exe = self.app_data.get("python_path", "")

        # --- PRIORITY 1: Handle AppImages & Direct Binaries ---
        if (script.lower().endswith(".appimage")) or exe == "BINARY":
            if os.path.exists(script):
                # Force executable permissions
                try:
                    st = os.stat(script)
                    os.chmod(script, st.st_mode | 0o111)
                except Exception:
                    pass

                try:
                    # Launch as a list (handles spaces in path correctly)
                    subprocess.Popen([script], cwd=os.path.dirname(script))
                    self.parent_window.toggle_visibility()
                    return
                except Exception as e:
                    self.show_error(f"Launch Error:\n{e}")
                    return
            else:
                self.show_error(f"File not found:\n{script}")
                return

        # --- PRIORITY 2: Standard System Commands ---
        if exe == "SYSTEM":
            try:
                # shlex.split handles quoted paths correctly
                subprocess.Popen(shlex.split(script))
                self.parent_window.toggle_visibility()
            except Exception as e:
                self.show_error(str(e))
            return

        # --- PRIORITY 3: Python Scripts / Terminal Commands ---
        if script and os.path.exists(script):
            settings = self.parent_window.config.get("settings", {})
            term_app = settings.get("terminal_app", "xterm")
            term_flags = settings.get("terminal_flags", ["-e"])

            try:
                full_cmd = (
                    [term_app]
                    + term_flags
                    + ["bash", "-c", f'"{exe}" "{script}"; exec bash']
                )
                subprocess.Popen(full_cmd, cwd=os.path.dirname(script))
                self.parent_window.toggle_visibility()
            except Exception as e:
                self.show_error(f"Failed to launch terminal ({term_app}):\n{e}")
        else:
            self.show_error(f"Script not found:\n{script}")

    # ------------------------------------------------------------------
    # Plugin / Live Content
    # ------------------------------------------------------------------
    def init_plugin(self) -> None:
        plugin_id = self.app_data.get("plugin_id")
        if plugin_id and self.parent_window.plugin_manager:
            plugin = self.parent_window.plugin_manager.plugins.get(plugin_id)
            if plugin and hasattr(plugin["module"], "setup"):
                try:
                    plugin["module"].setup(self)
                    no_slide = getattr(
                        plugin["module"], "NO_SLIDE", False
                    )
                    if no_slide:
                        return  # static-only tile, no timer/slide
                    is_interactive = getattr(
                        plugin["module"], "WANT_INTERACTIVITY", False
                    )
                    if is_interactive:
                        self.slide_to_live()
                    else:
                        import random
                        delay = random.randint(3000, 8000)
                        self.live_timer.start(delay)
                except Exception as e:
                    print(f"Live Tile Error ({plugin_id}): {e}")

    def cycle_live_content(self) -> None:
        if self.is_showing_live:
            self.slide_to_static()
        else:
            self.slide_to_live()

    def slide_to_live(self) -> None:
        self.slide_anim.stop()
        self.slide_anim.setStartValue(self._slide_y)
        self.slide_anim.setEndValue(-self.height())
        self.slide_anim.start()
        self.is_showing_live = True

    def slide_to_static(self) -> None:
        self.slide_anim.stop()
        self.slide_anim.setStartValue(self._slide_y)
        self.slide_anim.setEndValue(0)
        self.slide_anim.start()
        self.is_showing_live = False

    def show_error(self, text: str) -> None:
        msg = QMessageBox(self)
        msg.setWindowTitle("Error")
        msg.setText(text)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        msg.exec()

    def request_delete(self) -> None:
        self.parent_window.delete_item(self.group_index, self.item_index)

    def change_name(self) -> None:
        name, ok = QInputDialog.getText(
            self, "Rename", "Name:", text=self.app_data.get("name", "")
        )
        if ok and name:
            self.app_data["name"] = name
            self.text_label.setText(name)
            self.parent_window.save_config()

    def change_color(self) -> None:
        initial = QColor(self.app_data.get("color", "#000"))
        dlg = QColorDialog(initial, self)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        if dlg.exec():
            color = dlg.selectedColor()
            if color.isValid():
                self.app_data["color"] = color.name()
                self.update()
                self.parent_window.save_config()

    def change_icon(self) -> None:
        dlg = QFileDialog(self, "Select Icon")
        dlg.setNameFilter("Images (*.png *.jpg *.svg)")
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        if dlg.exec():
            files = dlg.selectedFiles()
            if files:
                self.app_data["icon"] = files[0]
                self.update_icon_data()
                self.parent_window.save_config()

    def remove_icon(self) -> None:
        self.app_data["icon"] = None
        self.update_icon_data()
        self.parent_window.save_config()

    def cycle_size(self) -> None:
        try:
            max_cols = int(self.parent_window.config["settings"].get("group_columns", 2))
        except (ValueError, TypeError):
            max_cols = 2
        all_sizes = [(1, 1), (1, 2), (2, 2)]
        valid_sizes = [s for s in all_sizes if s[1] <= max_cols]
        if not valid_sizes:
            valid_sizes = [(1, 1)]
        current = (
            self.app_data.get("row_span", 1),
            self.app_data.get("col_span", 2 if self.app_data.get("wide_tile") else 1),
        )
        if current in valid_sizes:
            new_size = valid_sizes[(valid_sizes.index(current) + 1) % len(valid_sizes)]
        else:
            new_size = valid_sizes[0]
        self.app_data["row_span"] = new_size[0]
        self.app_data["col_span"] = new_size[1]
        self.app_data["wide_tile"] = new_size[1] > 1
        self.parent_window.save_config()
        self.parent_window.refresh_ui()

    def edit_details(self) -> None:
        dlg = AppEditorDialog(self, self.parent_window, self.app_data)
        if dlg.exec():
            self.app_data.update(dlg.get_data())
            self.parent_window.refresh_ui()
            self.parent_window.save_config()

    def contextMenuEvent(self, event) -> None:
        if self.is_add:
            return
        # Route to AppBar (same as right-click)
        if hasattr(self.parent_window, 'app_bar'):
            self.parent_window.app_bar.toggle_for_tile(self)
        else:
            # Fallback simple menu
            menu = QMenu(self)
            menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            menu.addAction("Delete", self.request_delete)
            menu.exec(self.mapToGlobal(event.pos()))

    # --- Drag-and-drop events ---
    def dragEnterEvent(self, event) -> None:
        if event.source() and isinstance(event.source(), MetroTile):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.source() and isinstance(event.source(), MetroTile):
            pos = event.position().toPoint()
            if pos.x() < self.width() / 2:
                self.insert_side = "left"
            else:
                self.insert_side = "right"
            self.drop_target_mode = "insert"
            self.update()
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()

    def dragLeaveEvent(self, event) -> None:
        self.drop_target_mode = None
        self.update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        self.drop_target_mode = None
        self.update()
        source_tile = event.source()
        if source_tile and source_tile is not self:
            if self.is_add:
                self.parent_window.handle_drop(
                    source_tile.group_index, source_tile.item_index, self.group_index, -1
                )
            else:
                offset = 0 if self.insert_side == "left" else 1
                self.parent_window.handle_drop(
                    source_tile.group_index, source_tile.item_index,
                    self.group_index, self.item_index + offset,
                )
