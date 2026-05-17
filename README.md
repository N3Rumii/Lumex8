# Lumex8

Windows 8 Metro-style tile launcher for Linux. Press **Super+P** to toggle.

**Version:** 0.9.0-dev · **License:** GPL v3

---

## Features

- Tile grid with hover animations, rounded corners, and 3 size modes (1×1, 1×2, 2×2)
- Right-click AppBar: Unpin, Resize, Edit, Color, Icon
- Hide labels per tile (icon fills the tile)
- System wallpaper detection (works on most desktop environments)
- Drag-and-drop reordering with plugin state preservation
- Slideshow background (folder + interval)
- AppBar: icon labels toggle, spacing slider, dock background with opacity, alignment
- Self-contained skin/theme system — save/export/import `.skin` ZIP archives
- Gamepad navigation (d-pad, A/B/Y/START)
- Plugin system — drop `.py` in `plugins/` for live tile content
- System app importer (desktop entries, flatpak, snap, AppImage)
- Hotkey recorder, system tray icon, floating start button
- Kinetic inertial scrolling, collapsible settings, recolor all tiles with undo
- Multi-terminal auto-detection

---

## Quick Start

```bash
./lumex8/install.sh
uv run python -m lumex8
```

Requires Python 3.12+ and `libxcb-cursor0`.

---

## Plugins

Drop a `.py` into `plugins/` with `NAME`, optional `setup(tile)`, `run(window)`, and `CONFIG_FIELDS` for custom settings UI. Set `NO_SLIDE = True` for static tiles.

---

## Changelog

- **0.8** — Theme system with webp assets and .skin export/import. AppBar overhaul, desktop tile, per-tile label toggle, collapsible settings, plugin improvements.
- **0.7** — Full modular package: gamepad, kinetic scroll, slideshow, recolor tool, plugin live tiles, multi-terminal, hotkey recorder, .skin export.
- **0.6** — Drag-and-drop optimization.
- **0.5** — Start button, keyboard nav.
- **0.4** — System app importer with icons.
- **0.3** — Custom local icons.
- **0.2** — Groups, tile reordering.
- **0.1** — Folders.
