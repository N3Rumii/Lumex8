"""Plugin manager — dynamic loading of plugin modules."""

import importlib.util
import os


class PluginManager:
    """Discovers and executes plugins from a ``plugins/`` directory."""

    def __init__(self, base_dir: str | None = None) -> None:
        self.plugins: dict[str, dict] = {}
        base = base_dir or os.path.dirname(os.path.abspath(__file__))
        self.plugin_dir = os.path.join(os.path.dirname(base), "plugins")
        if not os.path.exists(self.plugin_dir):
            os.makedirs(self.plugin_dir)
        self.reload_plugins()

    def reload_plugins(self) -> None:
        """Scan the plugins directory and load all valid modules."""
        self.plugins = {}
        if not os.path.exists(self.plugin_dir):
            return
        for f in os.listdir(self.plugin_dir):
            if not f.endswith(".py") or f == "__init__.py":
                continue
            plugin_id = f[:-3]
            path = os.path.join(self.plugin_dir, f)
            try:
                spec = importlib.util.spec_from_file_location(plugin_id, path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "run"):
                    self.plugins[plugin_id] = {
                        "name": getattr(mod, "NAME", plugin_id.replace("_", " ").title()),
                        "icon": getattr(mod, "ICON", None),
                        "module": mod,
                    }
            except Exception as e:
                print(f"Error loading plugin {f}: {e}")

    def execute(self, plugin_id: str, launcher_window) -> None:
        """Run a loaded plugin by its id."""
        if plugin_id in self.plugins:
            try:
                self.plugins[plugin_id]["module"].run(launcher_window)
            except Exception as e:
                print(f"Error running plugin {plugin_id}: {e}")
