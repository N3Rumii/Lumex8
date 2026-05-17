# Lumex8 TODO

## ✅ v0.9 - Bugfixes

1. ✅ **Special tiles widget mode** — app_editor.py saved plugin config using label text instead of CONFIG_FIELDS key. Fixed by storing `config_key` property on each widget. Now "Widget Mode" → True = cycle between live and icon, False = always show live content.

2. ✅ **Remove obsolete "Recent Configurations"** from Settings → Themes tab. Removed QLabel, QListWidget, populate_recent(), load_recent_theme(), and add_recent_theme().

3. ✅ **QObject::setParent thread warning** — Deferred gamepad handler operations via QTimer.singleShot(0, ...) to avoid race conditions with refresh_ui.

## ✅ v0.9 - Changes

1. ✅ **Default group name → username** — Toolbar title now shows OS username (configurable via Settings → System). Added `title_text` and `title_alignment` fields.

2. ✅ **Icon theme system** — AppBar icons now load from active icon pack (fallback to built-in). Added pack picker with preview, Save/Export/Import in Settings → Appearance → Icon Packs.

3. ✅ **Icon packs in .skin themes** — Export/import skin now includes icon pack SVGs if non-default. Restored on import as a separate icon pack.

## ✅ Pre-release 0.9v - Cleanup

1. ✅ **Move non-lumex8 files outside** — Removed stale config.json from lumex8/ directory. Config path now uses absolute path to project root.

2. ✅ **Update README and LICENSE** — Version bumped to 0.9.0-dev. LICENSE (GPLv3) created at project root.
