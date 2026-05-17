"""GroupWidget — container for a labelled group of MetroTile widgets."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QPushButton, QMessageBox, QInputDialog)

from lumex8.widgets.tile import MetroTile


class GroupWidget(QWidget):
    """A labelled group of tiles in a grid layout.

    Supports wide-tile grid placement, group rename/delete in edit mode,
    and an add-tile placeholder.
    """

    def __init__(self, parent_window, group_data, group_index) -> None:
        super().__init__()
        self.parent_window = parent_window
        self.group_data = group_data
        self.group_index = group_index

        tile_size = self.parent_window.config["settings"].get("tile_size", 140)
        spacing = 4
        cols = self.parent_window.config["settings"].get("group_columns", 2)
        width = (tile_size * cols) + (spacing * (cols - 1)) + 40
        self.setFixedWidth(width)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 40, 0)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header_layout = QHBoxLayout()
        self.title = QLabel(group_data.get("name", "Group"))
        self.title.setStyleSheet(
            "color: white; font-size: 20px; font-family: 'Segoe UI Light', sans-serif;"
        )
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

    def populate_grid(self, reuse_tiles: dict | None = None) -> None:
        """Populate the grid, optionally reusing existing tile widgets."""
        grid_map: dict = {}
        try:
            max_cols = int(
                self.parent_window.config["settings"].get("group_columns", 2)
            )
        except (ValueError, TypeError):
            max_cols = 2
        if max_cols < 1:
            max_cols = 1

        def is_available(r, c, r_span, c_span):
            if c + c_span > max_cols:
                return False
            for ir in range(r_span):
                for ic in range(c_span):
                    if grid_map.get((r + ir, c + ic), False):
                        return False
            return True

        def mark_occupied(r, c, r_span, c_span):
            for ir in range(r_span):
                for ic in range(c_span):
                    grid_map[(r + ir, c + ic)] = True

        for i, app in enumerate(self.group_data.get("apps", [])):
            r_span = app.get("row_span", 1)
            c_span = app.get("col_span", 2 if app.get("wide_tile") else 1)

            if c_span > max_cols:
                c_span = max_cols

            found = False
            search_r = 0

            while not found and search_r < 1000:
                for search_c in range(max_cols):
                    if is_available(search_r, search_c, r_span, c_span):
                        # Reuse existing tile or create new
                        if reuse_tiles and i in reuse_tiles:
                            tile = reuse_tiles[i]
                            tile.item_index = i
                            tile.app_data = app
                            tile.update_fixed_size()
                            tile.update_icon_data()
                            # Re-run plugin init so live/setup tiles refresh
                            if app.get("type") in ("plugin", "special"):
                                tile.init_plugin()
                        else:
                            tile = MetroTile(
                                app, self.parent_window, self.group_index, i
                            )
                        if self.parent_window.is_edit_mode:
                            tile.delete_btn.show()
                        self.grid.addWidget(
                            tile, search_r, search_c, r_span, c_span
                        )
                        mark_occupied(search_r, search_c, r_span, c_span)
                        found = True
                        break
                search_r += 1

        if self.parent_window.is_edit_mode and not reuse_tiles:
            # Find first free cell for add-tile
            add_r = 0
            while add_r < 1000:
                add_found = False
                for add_c in range(max_cols):
                    if not grid_map.get((add_r, add_c), False):
                        add_tile = MetroTile(
                            {}, self.parent_window, self.group_index, -1, is_add=True
                        )
                        self.grid.addWidget(add_tile, add_r, add_c)
                        add_found = True
                        break
                if add_found:
                    break
                add_r += 1

    def delete_self(self) -> None:
        msg = QMessageBox(self)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        msg.setWindowTitle("Delete Group")
        msg.setText("Delete this group and all apps inside?")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.parent_window.delete_group(self.group_index)

    def rename_self(self) -> None:
        dlg = QInputDialog(self)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        dlg.setWindowTitle("Rename Group")
        dlg.setLabelText("Name:")
        dlg.setTextValue(self.group_data["name"])
        if dlg.exec():
            new_name = dlg.textValue()
            if new_name:
                self.group_data["name"] = new_name
                self.title.setText(new_name)
                self.parent_window.save_config()
