# Lumex8 Plugin API

Drop a `.py` file into `plugins/` — it gets loaded on next launch (or via `PluginManager.reload_plugins()`).

---

## Minimal Plugin

```python
NAME = "My Plugin"

def run(window):
    """Called when the tile is clicked."""
    pass
```

---

## Plugin Hooks

| Hook | Required | Called |
|------|----------|--------|
| `run(window)` | **Yes** | On tile click. `window` is the `LauncherWindow` instance. |
| `setup(tile)` | No | On tile creation. Build live-content UI here. |

### Module-Level Attributes

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `NAME` | `str` | filename → title | Display name in the tile editor |
| `ICON` | `str` or `None` | `None` | System icon name (e.g. `"user-desktop"`) |
| `NO_SLIDE` | `bool` | `False` | If `True`, tile stays static — no live/static cycling |
| `WANT_INTERACTIVITY` | `bool` | `False` | If `True`, skips timer — tile starts on live face immediately |
| `CONFIG_FIELDS` | `list[dict]` | `[]` | Custom settings rendered in the tile editor dialog |

---

## `setup(tile)` — Tile API

### Live Content

```python
def setup(tile):
    # Add widgets to the live face layout
    label = QLabel("Hello")
    tile.live_layout.addWidget(label)
```

`tile.live_layout` is a `QVBoxLayout`. Clear it before rebuilding:

```python
while tile.live_layout.count():
    item = tile.live_layout.takeAt(0)
    if item.widget():
        item.widget().deleteLater()
```

### Timers

```python
tile.data_timer = QTimer(tile)
tile.data_timer.timeout.connect(refresh_fn)
tile.data_timer.start(60000)  # ms
```

`tile.live_timer` is used internally for slide cycling. If you need to control it:

```python
# Force tile to always show live content
tile.slide_to_live()
tile.live_timer.stop()

# Or set a custom cycle interval
tile.live_timer.setInterval(8000)
```

### Tile State

```python
tile.app_data          # dict — plugin config values (CONFIG_FIELDS)
tile.parent_window     # LauncherWindow — access global state
tile.width()           # current pixel width
tile.height()          # current pixel height
```

### Background Image

```python
tile.display_pixmap = QPixmap(...).scaled(w, h, ...)
tile._image_is_file = True
tile.update()
```

### Hiding UI Elements

```python
tile.icon_label.setText("")
tile.text_label.hide()
```

---

## `CONFIG_FIELDS` — Custom Settings

Each field dict:

```python
CONFIG_FIELDS = [
    {
        "key": "city",           # stored in tile.app_data["city"]
        "label": "City Name",    # shown in the editor
        "default": "Warsaw",     # fallback value
    },
    {
        "key": "static_mode",
        "label": "Widget Mode",
        "default": "False",
        "options": ["False", "True"],  # renders a dropdown
    },
]
```

Values are stored as strings in `tile.app_data`. Access them with:

```python
mode = tile.app_data.get("static_mode", "False")
```

---

## Widget Mode Pattern

Plugins that slide between a static face and live content should check `static_mode`:

```python
def setup(tile):
    build_content(tile)
    refresh_data()

    def apply_view_mode():
        if tile.app_data.get("static_mode", "False") == "True":
            tile.live_timer.setInterval(8000)   # cycle between static/live
        else:
            tile.slide_to_live()                 # always show live
            tile.live_timer.stop()

    QTimer.singleShot(100, apply_view_mode)
```

---

## Reference: Existing Plugins

- **`desktop.py`** — Static-only (`NO_SLIDE = True`), displays system wallpaper via `tile.display_pixmap`
- **`weather.py`** — Live content with periodic API fetch and optional slide cycling
- **`trading.py`** — Live rate data with dynamic label creation per tracked asset
