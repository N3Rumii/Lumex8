# Lumex8 — Project State

**Version**: 0.8.0-dev
**Date**: May 16, 2026
**Python**: 3.12+ (uv-managed via inline PEP 723 metadata)

---

## Current Architecture

```
lumex8/
├── __init__.py              Package, version
├── __main__.py              Entry point, PEP 723 deps, sys.path fix, AT-SPI suppression
├── app.py                   LauncherWindow — fullscreen QMainWindow, paintEvent background, hotkeys
├── config.py                JSON config with deep-merge defaults
├── utils.py                 Icon pixmap cache
├── todolist.md              TODO tracking (cleared — all done)
├── install.sh               One-command installer (venv/uv, generates launch.sh + .desktop)
├── README.md                Full documentation
├── icons/                   SVG AppBar icons (tinted to accent color)
├── plugins/                 Drop-in .py plugin modules (desktop, trading, weather)
│   ├── desktop.py           Show Desktop — detects system wallpaper via gsettings/xfconf/KDE/feh/nitrogen/sway
│   ├── trading.py           Market Tracker — live currencies with configurable static mode
│   └── weather.py           Live Weather — configurable city/lat/lon with dropdown widget mode
├── dialogs/
│   ├── settings.py          Tabbed settings: Appearance (collapsible sections) + System + Themes
│   ├── app_editor.py        Tile properties editor (app/plugin modes, hide_label, plugin name auto-fill)
│   ├── app_importer.py      System app/flatpak/AppImage importer with searchable table
│   ├── hotkey_recorder.py   pynput-format hotkey binding UI
│   └── gamepad_recorder.py  Gamepad button binding UI
├── services/
│   ├── asset_manager.py     Themes/assets directory management
│   ├── plugin_manager.py    Dynamic plugin loading (importlib), NO_SLIDE flag support
│   ├── gamepad.py           Background QThread + pygame joystick
│   └── terminal.py          Auto-detect installed terminals
└── widgets/
    ├── tile.py              MetroTile — animated, draggable, live content, _image_is_file flag
    ├── group.py             GroupWidget — grid container with span-aware layout, plugin re-init on reuse
    ├── scroll.py            KineticScrollArea — momentum horizontal scroll
    ├── appbar.py            AppBar — bottom action bar with configurable dock background, alignment, spacing
    ├── appbar_button.py     Icon+label button with tinted SVG, hover/press states
    └── start_button.py      Floating desktop overlay button
```

---

## Key Features Implemented

### Visual
- Fullscreen tile grid with rounded corners and opacity (tile_alpha / tile_radius)
- 3 tile size modes via cycle_size: (1×1) → (1×2) → (2×2), reflowed by refresh_ui
- Background: solid color / single image (cached) / slideshow (folder, interval, cached frames)
- Recent wallpapers & start button icons thumbnail bars in settings
- Background opacity via QPainter
- Skin/theme system: save appearance + start button + appbar settings, self-contained .skin ZIP export/import with webp assets, swatch previews
- Recolor All Tiles batch tool with undo
- AppBar icons tinted to appbar_accent_color

### AppBar (Win8-style bottom action bar)
- Icon + text label buttons (text toggleable: appbar_show_labels)
- Configurable icon spacing (appbar_icon_spacing slider 0-40px)
- Dock-style colored background with opacity (appbar_dock_bar + appbar_dock_color + appbar_dock_opacity)
- Button alignment: Left, Center, Right (appbar_alignment)
- All AppBar settings saved in themes

### Tiles
- Hide Name toggle per tile (hide_label) — hides text, expands icon to full tile
- Text only auto-hides for real image files, not system theme icons
- Plugin tiles: NO_SLIDE flag prevents timer/slide, keeping static content only
- Desktop tile: detects actual Linux DE wallpaper (GNOME, KDE, XFCE, Cinnamon, MATE, Deepin, feh, nitrogen, Sway/Hyprland)
- Plugin name auto-fill in tile editor
- Tile re-creation preserves plugin state (init_plugin re-called on group repopulation)

### Interaction
- Right-click tile → AppBar slides up (Unpin, Resize, Edit, Color, Icon)
- Drag-and-drop: same-group moves use in-place widget reuse with plugin re-init
- Gamepad: d-pad navigation, A=launch, B=back, Y=AppBar, START=edit
- Global hotkeys: toggle visibility (Super+P) + edit mode (configurable)
- Cog dropdown: Add Tiles (edit mode) + Settings
- Hover: scale animation 1.0→1.05, painted rounded border (clearFocus on leave)

### Apps & Plugins
- Import system apps (desktop/flatpak/snap) — icons auto-imported
- AppImage support: chmod +x, list-based Popen
- Plugin tiles: live content via setup(tile), custom CONFIG_FIELDS in editor
- Terminal selection with auto-detection and flags persistence
- Widget Mode dropdown (True/False) unified across plugins — True=slideshow, False=always show live

### Self-Contained Themes
- Save & Export copy all images as webp into the theme directory
- .skin files are ZIP archives containing skin.json + assets/
- Import extracts assets to theme directory, updating paths to absolute
- Themes include: colors, wallpapers, tile settings, start button, appbar, per-tile overrides

---

## Bugs Fixed This Session

1. **PyQt6 import mismatches** — QKeyEvent, QAction, QFont, QFontMetrics, QApplication, QKeySequence moved to correct modules
2. **Multi-line f-strings** — literal newlines inside strings replaced with escapes
3. **Settings crash** — _sync_color_buttons called before override_color_btn created
4. **Icon color override** — replaced toggle + tint with Recolor All Tiles batch tool
5. **Background wallpaper lag** — pixmap + scaled version cached, only reload/scale on change
6. **Slideshow lag** — frames pre-cached in _advance_slideshow
7. **Hover ghost border** — removed CSS stylesheet border, now painted in paintEvent with radius
8. **Edit hotkey thread safety** — refresh_ui deferred via QTimer.singleShot
9. **cycle_size wrong logic** — rewritten to dev2's (row_span, col_span) tuple cycling
10. **Group grid span-aware** — ported dev2's populate_grid with is_available for row_span/col_span
11. **Terminal flags not saved** — combo now stores (cmd, flags) tuple
12. **Edit deletes icons** — get_data preserves original icon unless _imported_icon set
13. **launch.sh broken** — uses uv run ./lumex8/__main__.py (reads inline deps)
14. **Special tiles non-functional** — removed dead function_combo, migrated type:special→plugin in config, tile.py handles both
15. **Desktop tile used Lumex8 background** — now probes system DE (gsettings, xfconf, KDE config, feh, nitrogen, Sway) with fallback
16. **Desktop tile blank after drag** — group.py reuse path now re-calls init_plugin() for plugin tiles
17. **Desktop tile "DE" text overlay** — _image_is_file flag + explicit icon_label clear + tile.update() repaint
18. **Text missing on all tiles** — _image_is_file no longer controls text visibility; only hide_label does
19. **AppImages missing names** — text auto-hide now only fires for real image files, not theme icons
20. **AppBar dock bar was 3px line** — now full-height colored background behind buttons with opacity slider
21. **AppBar buttons unaligned** — added appbar_alignment: Left/Center/Right
22. **Border-top lines on AppBar** — removed all accent border-top, border:none
23. **Themes not saving start button** — save_current_skin & apply_theme_from_list include all SB + AppBar fields
24. **Reset to Defaults incomplete** — now resets slideshow, terminal, hotkeys, gamepad, icon theme, AppBar
25. **AT-SPI console spam** — QT_ACCESSIBILITY=0 + QT_LOGGING_RULES set before QApplication
26. **Missing hide_label in editor** — checkbox added, saved in get_data(), honored in tile.py

---

## Running

```bash
./launch.sh                           # Double-click
uv run ./lumex8/__main__.py           # Terminal
uv run python -m lumex8               # From parent dir (needs venv with deps)
```
