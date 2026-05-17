"""Application Importer — QDialog for importing system applications."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QFileDialog,
    QMessageBox,
)


# ---------------------------------------------------------------------------
# Desktop-file parser helpers
# ---------------------------------------------------------------------------

DESKTOP_SEARCH_PATHS: list[str] = [
    "/usr/share/applications",
    "/usr/local/share/applications",
    os.path.expanduser("~/.local/share/applications"),
    "/var/lib/flatpak/exports/share/applications",
    os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
    "/var/lib/snapd/desktop/applications",
    "/snap/bin",
]


def _parse_desktop_file(path: str) -> dict[str, str] | None:
    """Parse a ``.desktop`` file and return relevant fields.

    Returns ``None`` if the file is not a valid ``Type=Application`` entry.
    """
    fields: dict[str, str] = {}
    in_entry = False
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("["):
                    if in_entry:
                        break  # next section — stop reading
                    in_entry = True
                    continue
                if not in_entry or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                fields[key.strip()] = value.strip()
    except (OSError, IOError):
        return None

    if fields.get("Type") != "Application":
        return None
    if fields.get("NoDisplay", "false").lower() == "true":
        return None
    if fields.get("Hidden", "false").lower() == "true":
        return None

    exec_cmd = fields.get("Exec", "")
    # Strip %F, %U, %f, %u, %i, %c, %k etc.
    exec_cmd = exec_cmd.split("%")[0].strip()

    return {
        "name": fields.get("Name", Path(path).stem),
        "exec": exec_cmd,
        "icon": fields.get("Icon", ""),
        "comment": fields.get("Comment", ""),
        "path": path,
        "source": "desktop",
    }


def _scan_desktop_apps() -> list[dict[str, str]]:
    """Walk all known desktop-file directories and return parsed entries."""
    seen: set[str] = set()
    apps: list[dict[str, str]] = []

    for directory in DESKTOP_SEARCH_PATHS:
        try:
            for entry in sorted(os.listdir(directory)):
                if not entry.endswith(".desktop"):
                    continue
                full = os.path.join(directory, entry)
                if full in seen:
                    continue
                seen.add(full)
                parsed = _parse_desktop_file(full)
                if parsed is not None:
                    apps.append(parsed)
        except FileNotFoundError:
            continue
        except PermissionError:
            continue
        except NotADirectoryError:
            continue

    return apps


# ---------------------------------------------------------------------------
# AppImage scanner
# ---------------------------------------------------------------------------

def _scan_appimages(root: str) -> list[dict[str, str]]:
    """Walk *root* and return entries for every ``.AppImage`` file found."""
    apps: list[dict[str, str]] = []
    try:
        for dirpath, _dirnames, filenames in os.walk(root, followlinks=True):
            for fn in filenames:
                if fn.endswith(".AppImage") or fn.endswith(".appimage"):
                    full = os.path.join(dirpath, fn)
                    name = os.path.splitext(fn)[0]
                    apps.append(
                        {
                            "name": name,
                            "exec": f'"{full}"',
                            "icon": "",
                            "comment": full,
                            "path": full,
                            "source": "appimage",
                        }
                    )
    except (PermissionError, OSError):
        pass
    return apps


# ---------------------------------------------------------------------------
# AppImporter dialog
# ---------------------------------------------------------------------------

class AppImporterDialog(QDialog):
    """Dialog that lets the user browse and import system applications.

    Shows a searchable table of applications found from **.desktop** files
    and (optionally) **.AppImage** files discovered via a directory scan.

    Signals
    -------
    apps_selected(apps: list[dict[str, str]])
        Emitted with the selected application data when the user confirms.
    """

    apps_selected = pyqtSignal(list)

    _ICON_COL = 0
    _NAME_COL = 1
    _EXEC_COL = 2
    _SOURCE_COL = 3
    _COMMENT_COL = 4
    _DATA_COL = 5  # hidden column storing the full dict

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import System Applications")
        self.setMinimumSize(680, 480)
        self._all_apps: list[dict[str, str]] = []

        self._build_ui()
        self._load_desktop_apps()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ---- Search bar -------------------------------------------------
        search_layout = QHBoxLayout()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search applications…")
        self.search_bar.textChanged.connect(self._filter_table)
        search_layout.addWidget(self.search_bar)
        layout.addLayout(search_layout)

        # ---- Table ------------------------------------------------------
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["", "Name", "Executable", "Source", "Description", ""]
        )
        self.table.setColumnHidden(self._DATA_COL, True)  # hidden data column
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self._ICON_COL, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(self._ICON_COL, 32)
        header.setSectionResizeMode(self._NAME_COL, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            self._EXEC_COL, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            self._SOURCE_COL, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            self._COMMENT_COL, QHeaderView.ResizeMode.Stretch
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.MultiSelection
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        # ---- Options ----------------------------------------------------
        opts_layout = QHBoxLayout()

        self.import_icon_cb = QCheckBox("Import System Icon")
        self.import_icon_cb.setChecked(True)
        opts_layout.addWidget(self.import_icon_cb)

        opts_layout.addStretch()

        self.scan_btn = QPushButton("Scan for AppImages…")
        self.scan_btn.clicked.connect(self._on_scan_appimages)
        opts_layout.addWidget(self.scan_btn)

        layout.addLayout(opts_layout)

        # ---- Dialog buttons ---------------------------------------------
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def _load_desktop_apps(self) -> None:
        self._all_apps = _scan_desktop_apps()
        self._populate_table(self._all_apps)

    def _populate_table(self, apps: list[dict[str, str]]) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        for row, app in enumerate(apps):
            self.table.insertRow(row)

            # Icon column
            icon_item = QTableWidgetItem()
            icon = self._resolve_icon(app["icon"])
            if icon is not None:
                icon_item.setIcon(icon)
            icon_item.setFlags(icon_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, self._ICON_COL, icon_item)

            # Name
            name_item = QTableWidgetItem(app["name"])
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, self._NAME_COL, name_item)

            # Executable
            exec_item = QTableWidgetItem(app.get("exec", ""))
            exec_item.setFlags(exec_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, self._EXEC_COL, exec_item)

            # Source
            source_item = QTableWidgetItem(app.get("source", ""))
            source_item.setFlags(source_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, self._SOURCE_COL, source_item)

            # Comment / description
            comment_item = QTableWidgetItem(app.get("comment", ""))
            comment_item.setFlags(comment_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, self._COMMENT_COL, comment_item)

            # Hidden data
            data_item = QTableWidgetItem()
            data_item.setData(Qt.ItemDataRole.UserRole, app)
            self.table.setItem(row, self._DATA_COL, data_item)

        self.table.setSortingEnabled(True)

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------
    def _filter_table(self, text: str) -> None:
        lower = text.strip().lower()
        if not lower:
            self._populate_table(self._all_apps)
            return

        filtered = [
            app
            for app in self._all_apps
            if lower in app["name"].lower()
            or lower in app.get("exec", "").lower()
            or lower in app.get("comment", "").lower()
        ]
        self._populate_table(filtered)

    # ------------------------------------------------------------------
    # AppImage scanning
    # ------------------------------------------------------------------
    def _on_scan_appimages(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Select directory to scan for AppImages", str(Path.home())
        )
        if not directory:
            return

        found = _scan_appimages(directory)
        if not found:
            QMessageBox.information(
                self,
                "No AppImages Found",
                f"No .AppImage files were found in:\n{directory}",
            )
            return

        # Merge – avoid duplicates by path
        existing_paths: set[str] = {a["path"] for a in self._all_apps}
        added = 0
        for app in found:
            if app["path"] not in existing_paths:
                self._all_apps.append(app)
                existing_paths.add(app["path"])
                added += 1

        QMessageBox.information(
            self,
            "Scan Complete",
            f"Found {len(found)} AppImage(s), {added} new.\n"
            f"Total applications listed: {len(self._all_apps)}",
        )
        self._filter_table(self.search_bar.text().strip())

    # ------------------------------------------------------------------
    # Acceptance
    # ------------------------------------------------------------------
    def _on_accept(self) -> None:
        selected_rows = {
            idx.row() for idx in self.table.selectedIndexes()
        }
        if not selected_rows:
            QMessageBox.information(
                self, "No Selection", "Please select at least one application."
            )
            return

        selected: list[dict[str, str]] = []
        for row in sorted(selected_rows):
            item = self.table.item(row, self._DATA_COL)
            if item is not None:
                app: dict[str, str] = item.data(Qt.ItemDataRole.UserRole)
                app = dict(app)  # shallow copy
                app["import_icon"] = self.import_icon_cb.isChecked()
                selected.append(app)

        self.apps_selected.emit(selected)
        self.accept()

    # ------------------------------------------------------------------
    # Icon resolution
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_icon(icon_name: str) -> QIcon | None:
        """Try to locate *icon_name* as a themed icon or file path."""
        if not icon_name:
            return None

        # Direct path
        if icon_name.startswith("/"):
            if os.path.isfile(icon_name):
                return QIcon(icon_name)
            return None

        # Themed icon (Qt lookup)
        icon = QIcon.fromTheme(icon_name)
        if not icon.isNull():
            return icon

        # Fall back to pixmap search via xdg
        try:
            result = subprocess.run(
                ["xdg-icon-resource", "get", icon_name],
                capture_output=True,
                text=True,
            )
            path = result.stdout.strip()
            if path and os.path.isfile(path):
                return QIcon(path)
        except FileNotFoundError:
            pass

        return None
