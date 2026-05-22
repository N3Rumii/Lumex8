import os
import re
import subprocess

from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

NAME = "Show Desktop"
ICON = "user-desktop"  # System icon name
NO_SLIDE = True  # This tile never cycles live — wallpaper only


# ------------------------------------------------------------------
# System wallpaper detection
# ------------------------------------------------------------------

def _run(*args: str) -> str:
    """Run a command and return stripped stdout, or empty string on failure."""
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=4,
        )
        return proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _unwrap_uri(raw: str) -> str:
    """Strip ``file://`` prefix, trailing newline/quotes, and percent-decode."""
    val = raw.strip().strip("'").strip('"')
    if val.startswith("file://"):
        val = val[7:]
    # Handle percent-encoded characters (e.g. %20 → space)
    from urllib.parse import unquote
    return unquote(val)


def _detect_system_wallpaper() -> str:
    """Probe the running desktop environment for the current wallpaper path.

    Returns the absolute filesystem path, or an empty string if detection fails.
    """
    # 1 — GNOME / Budgie / Unity (gsettings)
    uri = _run("gsettings", "get", "org.gnome.desktop.background", "picture-uri-dark")
    if not uri:
        uri = _run("gsettings", "get", "org.gnome.desktop.background", "picture-uri")
    if uri and uri != "''":
        path = _unwrap_uri(uri)
        if os.path.isfile(path):
            return path

    # 2 — Cinnamon
    uri = _run("gsettings", "get", "org.cinnamon.desktop.background", "picture-uri")
    if uri and uri != "''":
        path = _unwrap_uri(uri)
        if os.path.isfile(path):
            return path

    # 3 — MATE
    path = _run("gsettings", "get", "org.mate.background", "picture-filename")
    if path and path != "''":
        path = path.strip("'").strip('"')
        if os.path.isfile(path):
            return path

    # 4 — XFCE (try common monitor paths)
    for monitor in ("monitor0", "monitor1", "monitorDP-0", "monitorHDMI-0",
                    "monitorVGA-0", "monitoreDP-1", "monitorHDMI-1"):
        path = _run("xfconf-query", "-c", "xfce4-desktop",
                    "-p", f"/backdrop/screen0/{monitor}/workspace0/last-image")
        if path and os.path.isfile(path):
            return path

    # 5 — KDE Plasma 5/6 (read config file)
    kde_config = os.path.expanduser(
        "~/.config/plasma-org.kde.plasma.desktop-appletsrc"
    )
    if os.path.isfile(kde_config):
        try:
            with open(kde_config, "r") as f:
                content = f.read()
            # Match Image=... in the wallpaper plugin section
            for match in re.finditer(r"^Image=(.+)$", content, re.MULTILINE):
                candidate = _unwrap_uri(match.group(1))
                if os.path.isfile(candidate):
                    return candidate
        except OSError:
            pass

    # 6 — Deepin
    uri = _run("gsettings", "get", "com.deepin.dde.appearance",
               "background-uris")
    if uri and uri != "''" and uri != "[]":
        # Returns a list; take first entry
        first = uri.strip("[]").split(",")[0].strip().strip("'").strip('"')
        path = _unwrap_uri(first) if first.startswith("file://") else first
        if os.path.isfile(path):
            return path

    # 7 — feh (standalone, common on minimal WMs)
    fehbg = os.path.expanduser("~/.fehbg")
    if os.path.isfile(fehbg):
        try:
            with open(fehbg, "r") as f:
                for line in f:
                    if "feh" in line and "--bg-" in line:
                        # last argument is the image path
                        parts = line.strip().split()
                        for part in reversed(parts):
                            candidate = part.strip("'").strip('"')
                            if os.path.isfile(candidate):
                                return candidate
        except OSError:
            pass

    # 8 — nitrogen
    nitrogen_cfg = os.path.expanduser("~/.config/nitrogen/bg-saved.cfg")
    if os.path.isfile(nitrogen_cfg):
        try:
            with open(nitrogen_cfg, "r") as f:
                for line in f:
                    if line.startswith("file="):
                        candidate = line[5:].strip()
                        if os.path.isfile(candidate):
                            return candidate
        except OSError:
            pass

    # 9 — swaybg / hyprpaper (wlroots)
    # Check sway config
    sway_cfg = os.path.expanduser("~/.config/sway/config")
    for cfg_path in (sway_cfg, os.path.expanduser("~/.config/hypr/hyprpaper.conf")):
        if os.path.isfile(cfg_path):
            try:
                with open(cfg_path, "r") as f:
                    for line in f:
                        # sway: output * bg /path/to/wallpaper fill
                        # hyprpaper: wallpaper = ,/path/to/wallpaper
                        if "output" in line and "bg" in line:
                            parts = line.strip().split()
                            for part in parts[2:]:
                                candidate = part.strip().strip('"').strip("'")
                                if os.path.isfile(candidate):
                                    return candidate
                        if "wallpaper" in line and "=" in line:
                            candidate = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if "," in candidate:
                                candidate = candidate.split(",", 1)[1].strip()
                            if os.path.isfile(candidate):
                                return candidate
            except OSError:
                pass

    return ""


# ------------------------------------------------------------------
# Plugin hooks
# ------------------------------------------------------------------

def setup(tile):
    """Show the user's actual system desktop wallpaper as the tile image."""
    # Try system wallpaper first, fall back to Lumex8's own background
    wallpaper = _detect_system_wallpaper()
    if not wallpaper:
        config = tile.parent_window.config
        settings = config.get("settings", {})
        wallpaper = settings.get("background_value", "")

    if wallpaper and os.path.exists(wallpaper):
        pix = QPixmap(wallpaper)
        if not pix.isNull():
            w = tile.width()
            h = tile.height()
            tile.display_pixmap = pix.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            tile._image_is_file = True
            tile.icon_label.setText("")
            tile.text_label.hide()
            # Ensure icon fills entire tile (resizeEvent already ran)
            tile.icon_label.setGeometry(0, 0, w, h)
            # Persist so re-creations (drag/drop) keep full layout
            tile.app_data["hide_label"] = True
            # Force repaint with the new wallpaper
            tile.update()


def run(launcher):
    # This toggles the launcher visibility, effectively showing the desktop
    launcher.toggle_visibility()
