"""Configuration management — loading, saving, defaults."""

import json
import os


DEFAULT_CONFIG = {
    "settings": {
        "window_title": "Pop Metro Launcher",
        "title_text": "",
        "title_alignment": "Left",
        "background_type": "color",
        "background_value": "",
        "background_color": "#1d1d1d",
        "background_opacity": 100,
        "default_tile_color": "#00a300",
        "tile_size": 140,
        "group_columns": 2,
        "tile_radius": 0,
        "tile_alpha": 255,
        "global_hotkey": "<cmd>+p",
        "gamepad_hotkey": "GUIDE",
        "terminal_app": "gnome-terminal",
        "terminal_flags": ["--"],
        "icon_theme": "default_theme",
        "appbar_accent_color": "#ffffff",
        "appbar_tint_icons": True,
    },
    "groups": [
        {"name": "Start", "apps": []},
    ],
    "start_btn": {
        "visible": True,
        "autohide": False,
        "position": "Bottom Left",
        "size": 60,
        "icon_type": "text",
        "icon_val": "\u2756",
        "color": "rgba(255, 255, 255, 0.2)",
    },
    "recent_themes": [],
    "themes": [],
    "active_theme": "Default",
}


def load_config(config_file: str) -> dict:
    """Load config from a JSON file, merging defaults for missing keys."""
    if not os.path.exists(config_file):
        return _deep_merge({}, DEFAULT_CONFIG)

    try:
        with open(config_file, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _deep_merge({}, DEFAULT_CONFIG)

    return _deep_merge(data, DEFAULT_CONFIG)


def save_config(config_file: str, config: dict) -> None:
    """Save config to a JSON file."""
    with open(config_file, "w") as f:
        json.dump(config, f, indent=4)


def _deep_merge(src: dict, defaults: dict) -> dict:
    """Recursively merge src into defaults, keeping defaults for missing keys."""
    result = {}
    for key in set(list(src.keys()) + list(defaults.keys())):
        if key in src and key in defaults:
            if isinstance(defaults[key], dict) and isinstance(src[key], dict):
                result[key] = _deep_merge(src[key], defaults[key])
            else:
                result[key] = src[key]
        elif key in src:
            result[key] = src[key]
        else:
            result[key] = defaults[key]
    return result
