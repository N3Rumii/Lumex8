# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = [
#     "PyQt6",
#     "pynput",
#     "pygame",
# ]
# ///

"""Lumex8 — A Windows 8 Metro-style tile launcher for Linux.

Run with:
    uv run python -m lumex8               (from parent of lumex8/)
    uv run /path/to/lumex8/__main__.py    (anywhere — picks up inline deps)
"""

import os
import sys

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

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = LauncherWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
