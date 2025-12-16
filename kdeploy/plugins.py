"""Plugin system for kdeploy."""

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional
import pluggy

from kdeploy.utils import print_info, print_error

# Plugin hook specification
hookspec = pluggy.HookspecMarker("kdeploy")
hookimpl = pluggy.HookimplMarker("kdeploy")


class KDeployHookSpec:
    """Hook specification for kdeploy plugins."""

    @hookspec
    def kdeploy_pre_build(self, app_name: str, config: Any) -> None:
        """Called before building an application."""
        pass

    @hookspec
    def kdeploy_post_build(self, app_name: str, config: Any, template_count: int) -> None:
        """Called after building an application."""
        pass

    @hookspec
    def kdeploy_pre_deploy(self, app_name: str, config: Any, namespace: str) -> None:
        """Called before deploying an application."""
        pass

    @hookspec
    def kdeploy_post_deploy(
        self,
        app_name: str,
        config: Any,
        namespace: str,
        success: bool,
        stats: Dict[str, int]
    ) -> None:
        """Called after deploying an application."""
        pass

    @hookspec
    def kdeploy_add_commands(self) -> Dict[str, Callable]:
        """
        Add custom CLI commands.

        Returns:
            Dictionary mapping command names to Click command functions
        """
        pass

    @hookspec
    def kdeploy_template_filters(self) -> Dict[str, Callable]:
        """
        Add custom Jinja2 template filters.

        Returns:
            Dictionary mapping filter names to filter functions
        """
        pass


class PluginManager:
    """Plugin manager for kdeploy."""

    def __init__(self, plugin_dirs: Optional[List[Path]] = None):
        """
        Initialize plugin manager.

        Args:
            plugin_dirs: List of directories to search for plugins
        """
        self.pm = pluggy.PluginManager("kdeploy")
        self.pm.add_hookspecs(KDeployHookSpec)
        self._plugin_dirs = plugin_dirs or []
        self._loaded_plugins: Dict[str, Any] = {}

    def load_plugins(self) -> None:
        """Load all plugins from plugin directories."""
        for plugin_dir in self._plugin_dirs:
            if not plugin_dir.exists() or not plugin_dir.is_dir():
                continue

            self._load_plugins_from_dir(plugin_dir)

    def _load_plugins_from_dir(self, plugin_dir: Path) -> None:
        """
        Load plugins from a directory.

        Args:
            plugin_dir: Directory containing plugin files
        """
        for plugin_file in plugin_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue

            try:
                self._load_plugin_file(plugin_file)
            except Exception as e:
                print_error(f"Failed to load plugin {plugin_file.name}: {e}")

    def _load_plugin_file(self, plugin_file: Path) -> None:
        """
        Load a plugin from a Python file.

        Args:
            plugin_file: Path to plugin file
        """
        plugin_name = plugin_file.stem

        # Load module from file
        spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
        if spec is None or spec.loader is None:
            return

        module = importlib.util.module_from_spec(spec)
        sys.modules[plugin_name] = module
        spec.loader.exec_module(module)

        # Register plugin hooks
        if hasattr(module, "register"):
            # Plugin has a register function
            plugin_instance = module.register()
            self.pm.register(plugin_instance, name=plugin_name)
            self._loaded_plugins[plugin_name] = plugin_instance
            print_info(f"Loaded plugin: {plugin_name}")
        elif hasattr(module, "KDeployPlugin"):
            # Plugin has a KDeployPlugin class
            plugin_instance = module.KDeployPlugin()
            self.pm.register(plugin_instance, name=plugin_name)
            self._loaded_plugins[plugin_name] = plugin_instance
            print_info(f"Loaded plugin: {plugin_name}")

    def call_hook(self, hook_name: str, **kwargs) -> List[Any]:
        """
        Call a plugin hook.

        Args:
            hook_name: Name of hook to call
            **kwargs: Hook arguments

        Returns:
            List of results from all plugin implementations
        """
        hook = getattr(self.pm.hook, hook_name, None)
        if hook is None:
            return []

        try:
            return hook(**kwargs)
        except Exception as e:
            print_error(f"Error calling hook {hook_name}: {e}")
            return []

    def get_custom_commands(self) -> Dict[str, Callable]:
        """
        Get custom commands from plugins.

        Returns:
            Dictionary mapping command names to Click command functions
        """
        commands = {}
        results = self.call_hook("kdeploy_add_commands")

        for result in results:
            if result and isinstance(result, dict):
                commands.update(result)

        return commands

    def get_template_filters(self) -> Dict[str, Callable]:
        """
        Get custom template filters from plugins.

        Returns:
            Dictionary mapping filter names to filter functions
        """
        filters = {}
        results = self.call_hook("kdeploy_template_filters")

        for result in results:
            if result and isinstance(result, dict):
                filters.update(result)

        return filters

    def list_plugins(self) -> List[str]:
        """
        Get list of loaded plugin names.

        Returns:
            List of plugin names
        """
        return list(self._loaded_plugins.keys())


# Example plugin implementation
class ExamplePlugin:
    """Example plugin demonstrating hook implementations."""

    @hookimpl
    def kdeploy_pre_build(self, app_name: str, config: Any) -> None:
        """Called before building an application."""
        print_info(f"[Example Plugin] Pre-build: {app_name}")

    @hookimpl
    def kdeploy_post_build(self, app_name: str, config: Any, template_count: int) -> None:
        """Called after building an application."""
        print_info(f"[Example Plugin] Post-build: {app_name} ({template_count} templates)")

    @hookimpl
    def kdeploy_template_filters(self) -> Dict[str, Callable]:
        """Add custom template filters."""
        def uppercase(text: str) -> str:
            return text.upper()

        def lowercase(text: str) -> str:
            return text.lower()

        return {
            "uppercase": uppercase,
            "lowercase": lowercase,
        }
