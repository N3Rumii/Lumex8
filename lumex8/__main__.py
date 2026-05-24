# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = [
#     "PyQt6",
#     "pynput",
# ]
# ///

"""Lumex8 — A Windows 8 Metro-style tile launcher for Linux.

Run with:
    uv run python -m lumex8               (from parent of lumex8/)
    uv run /path/to/lumex8/__main__.py    (anywhere — picks up inline deps)
"""

import os
import sys

# ── Work around KDE/GNOME hybrid environments ──────────────────────
# Must be set BEFORE any PyQt6 import, otherwise the platform plugin
# and theme engine are already loaded with the wrong configuration.

# 1. plasma-integration forces KDE's Breeze theme — breaks rendering
#    and window placement on GNOME/Wayland.
if os.environ.get("QT_QPA_PLATFORMTHEME", "").startswith(("kde", "KDE")):
    del os.environ["QT_QPA_PLATFORMTHEME"]

# 2. On Wayland, client-side window placement is unsupported.  Force
#    the XCB (X11) backend so move(), Tool, and X11Bypass hint work
#    via Xwayland.
if os.environ.get("XDG_SESSION_TYPE", "") == "wayland":
    os.environ["QT_QPA_PLATFORM"] = "xcb"

# Allow running as a standalone script (uv run __main__.py)
# while keeping package-relative imports working.
_this_dir = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_this_dir)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from lumex8.app import LauncherWindow


def main() -> None:
    """Application entry point."""
    # Suppress AT-SPI accessibility bus warnings on Linux
    if sys.platform.startswith("linux"):
        os.environ.setdefault("QT_ACCESSIBILITY", "0")
        os.environ.setdefault("QT_LOGGING_RULES",
                              "qt.accessibility.atspi.warning=false")

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 3. Belt-and-suspenders: Fusion style is Qt6's built-in cross-
    #    platform style — works everywhere regardless of installed
    #    theme plugins (KDE Breeze, GTK, etc.).
    app.setStyle("Fusion")

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = LauncherWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
