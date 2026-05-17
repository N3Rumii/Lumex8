# Lumex8

A Windows 8 Metro-style tile launcher for Linux — built for touchscreens and graphic tablets.

**Version**: 0.9.0-dev  
**License**: GPL v3

Press **Super+P** to toggle the fullscreen tile dashboard.

---

## Features

- **Big, colorful, touch-friendly tile grid** with scale-on-hover animations and rounded corners
- **Drag-and-drop reordering** with instant within-group repositioning and plugin state preservation
- **3 tile size modes** — normal (1×1), wide (1×2), large (2×2)
- **AppBar** — right-click a tile for Unpin, Resize, Edit, Color, and Icon actions
- **Hide Name per tile** — toggle to hide the label and expand the icon to fill the tile
- **Full-tile image mode** — tiles display a stretched background image
- **Desktop tile with system wallpaper detection** — probes GNOME, KDE, XFCE, Cinnamon, MATE, Deepin, feh, nitrogen, Sway/Hyprland
- **Gamepad navigation** — d-pad movement, A=launch, B=back, Y=AppBar, START=edit
- **Self-contained skin/theme system** — save all appearance settings (colors, wallpapers, start button, appbar, per-tile icons), export to `.skin` ZIP archives with webp assets, import and share with anyone
- **Background slideshow** — point to a folder of wallpapers, set interval, auto-cycle
- **Recent wallpapers & start button icons** — horizontal thumbnail bars in settings for quick switching
- **Recolor All Tiles** — batch-recolor every tile with undo
- **Configurable AppBar** — icon labels toggleable, spacing slider, dock-style colored background with opacity, Left/Center/Right alignment
- **Collapsible settings sections** — toggle visibility of Colors, AppBar, Recolor, Tile & Layout, Start Button
- **Multi-terminal support** — auto-detects GNOME/Konsole/Kitty/Alacritty/XTerm/Foot/Terminator
- **Kinetic inertial scrolling** — flick-scroll through tile groups with momentum
- **Plugin system** — drop `.py` files into `plugins/`, tiles get live content and custom settings
- **System app import** — pull apps from desktop entries, flatpak, snap
- **AppImage discovery** — scan folders for `.AppImage` executables
- **Hotkey recorder** — rebind the global toggle and edit mode shortcuts from within settings
- **System tray icon** — left-click to toggle, right-click menu with quit
- **Floating desktop start button** — configurable position, size, icon, auto-hide
- **Background opacity, tile corner radius, tile opacity** — full visual control

---

## Prerequisites

- **Python 3.12+**
- `libxcb-cursor0` (for Qt cursor support on X11)

---

## Quick Install

```bash
cd /path/to/lumex8
chmod +x install.sh
./install.sh
```

The installer:
1. Finds Python 3.12+
2. Prefers **uv** (fast package manager) or falls back to venv + pip
3. Installs PyQt6, pynput, pygame
4. Creates `launch.sh` and `lumex8.desktop`

---

## Usage

```bash
./launch.sh                     # Double-click or terminal
uv run python -m lumex8         # From the parent directory
```

Install the desktop entry to your app launcher:

```bash
cp lumex8.desktop ~/.local/share/applications/
```

---

## Controls

| Action | Shortcut |
|--------|----------|
| Toggle launcher | **Super+P** (configurable) |
| Toggle edit mode | Configurable in Settings → System |
| Launch tile | Left-click |
| AppBar (actions) | Right-click tile |
| Settings | ⚙ dropdown → Settings |
| Add tiles mode | ⚙ dropdown → Add Tiles |

**Gamepad:**

| Button | Action |
|--------|--------|
| Guide/PS | Toggle launcher |
| A | Launch focused tile |
| B | Hide AppBar |
| Y | AppBar on focused tile |
| START | Toggle edit mode |
| D-Pad | Move between tiles |

---

## Plugins

Drop a `.py` file into `lumex8/plugins/`. It must have:

```python
NAME = "Plugin Name"

# Set to True if your tile should never cycle live (static-only)
NO_SLIDE = True

def run(launcher_window):
    """Called when the plugin tile is clicked."""
    pass

def setup(tile):
    """Called when tile is created — build live content UI here."""
    pass

# Optional: custom settings UI
CONFIG_FIELDS = [
    {"key": "my_setting", "label": "Setting Name", "default": "value",
     "options": ["False", "True"]},  # options makes it a dropdown
]
```

---

## FAQ

**Does this work on KDE?** Yes. Pick Konsole in Settings → System. Lumex8 auto-detects installed terminals. The desktop tile detects KDE wallpapers via `plasma-org.kde.plasma.desktop-appletsrc`.

**Why doesn't it show all my system apps?** It's a launcher for *your* scripts and hand-picked apps. Use "Import from System/Flatpak…" when adding tiles.

**Why Windows 8 style?** Built for graphic tablets and touchscreens. Big tiles, touch-friendly, scale animations.

**How do I add custom icon themes?** Create a folder in `lumex8/assets/themes/` with icon SVGs matching the names in `lumex8/icons/`. Select it in Settings → Themes.

**Can I share my theme?** Yes! Use Export Skin to create a `.skin` file — it bundles all images as webp in a ZIP archive. Anyone can import it via Settings → Themes.

---

## Changelog

- **0.8** — Self-contained theme system (webp assets, .skin ZIP export/import). AppBar overhaul: icon labels, spacing slider, dock background with opacity, alignment. Desktop tile detects actual system wallpaper. Hide Name toggle per tile. Collapsible settings sections. Plugin name auto-fill. NO_SLIDE plugin flag. Widget Mode unified as dropdown. Fixed: special tiles, desktop tile blank after drag, AppImage names, AT-SPI warnings, text visibility, themes missing start button/appbar, Reset to Defaults completeness.
- **0.7** — Modular package. Gamepad navigation, AppBar, kinetic scroll, skin system, slideshow, wallpaper thumbnails, recolor tool, plugin live tiles, multi-terminal, AppImage support, hotkey recorder, .skin export/import, rounded corners, tile opacity, background opacity.
- **0.6** — Performance optimization for drag-and-drop.
- **0.5** — Floating start button, keyboard navigation.
- **0.4** — System app / flatpak import with icons.
- **0.3** — Custom icons from local drive.
- **0.2** — Groups, tile dragging/reordering.
- **0.1** — Folders.
