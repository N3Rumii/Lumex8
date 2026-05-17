"""Utility functions — icon caching."""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

# Global cache dictionary
ICON_CACHE: dict[tuple[str, int, int], QPixmap] = {}


def get_cached_pixmap(path: str, w: int, h: int) -> QPixmap | None:
    """Get a scaled pixmap from cache, or load and cache it.

    Returns None if the path doesn't exist or the pixmap is invalid.
    """
    key = (path, w, h)
    if key in ICON_CACHE:
        return ICON_CACHE[key]

    if not os.path.exists(path):
        return None

    pix = QPixmap(path)
    if pix.isNull():
        return None

    scaled = pix.scaled(
        w, h,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    ICON_CACHE[key] = scaled
    return scaled
