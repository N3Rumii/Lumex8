"""Asset management — directory structure, file imports, theme paths."""

import os
import shutil
import time


class AssetManager:
    """Manages the asset directory tree under the script's base directory."""

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")

    SYSTEM_DIR = os.path.join(ASSETS_DIR, "system", "default_theme")
    THEMES_DIR = os.path.join(ASSETS_DIR, "themes")
    CUSTOM_BG_DIR = os.path.join(ASSETS_DIR, "custom", "backgrounds")
    CUSTOM_ICON_DIR = os.path.join(ASSETS_DIR, "custom", "icons")

    @staticmethod
    def ensure_directories() -> None:
        """Create all required asset directories if they don't exist."""
        os.makedirs(AssetManager.SYSTEM_DIR, exist_ok=True)
        os.makedirs(AssetManager.THEMES_DIR, exist_ok=True)
        os.makedirs(AssetManager.CUSTOM_BG_DIR, exist_ok=True)
        os.makedirs(AssetManager.CUSTOM_ICON_DIR, exist_ok=True)

    @staticmethod
    def import_file(file_path: str, target_folder: str) -> str | None:
        """Copy a file into the target folder with a unique name.

        Returns the destination path, or the original path if the file
        doesn't exist or copying fails.
        """
        if not file_path or not os.path.exists(file_path):
            return None
        name, ext = os.path.splitext(os.path.basename(file_path))
        unique_name = f"{name}_{int(time.time())}{ext}"
        destination = os.path.join(target_folder, unique_name)
        try:
            shutil.copy2(file_path, destination)
            return destination
        except OSError:
            return file_path
