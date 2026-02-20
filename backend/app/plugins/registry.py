"""Plugin registry for dynamic loading and management of plugins."""

import importlib
import inspect
from typing import Any, Dict, List, Optional, Type
from pathlib import Path
import logging

from .base import BasePlugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Registry for managing plugin loading and discovery.

    Provides functionality to dynamically load plugins from specified directories
    and manage their lifecycle.
    """

    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}
        self._plugin_classes: Dict[str, Type[BasePlugin]] = {}

    async def load_plugin_from_path(self, plugin_path: str, plugin_name: str) -> Optional[BasePlugin]:
        """Load a plugin from a Python module path.

        Args:
            plugin_path: The module path (e.g., 'plugins.stt.mock_stt').
            plugin_name: Unique name for the plugin instance.

        Returns:
            The loaded plugin instance, or None if loading failed.
        """
        try:
            module = importlib.import_module(plugin_path)
            plugin_class = None

            # Find the plugin class in the module
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and
                    issubclass(obj, BasePlugin) and
                    obj != BasePlugin):
                    plugin_class = obj
                    break

            if plugin_class is None:
                logger.error(f"No BasePlugin subclass found in {plugin_path}")
                return None

            # Create and initialize the plugin
            plugin = plugin_class()
            await plugin.initialize()
            self._plugins[plugin_name] = plugin
            self._plugin_classes[plugin_name] = plugin_class

            logger.info(f"Loaded plugin {plugin_name} from {plugin_path}")
            return plugin

        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_name} from {plugin_path}: {e}")
            return None

    async def load_plugins_from_directory(self, directory: Path, plugin_type: str) -> List[str]:
        """Load all plugins from a directory.

        Args:
            directory: Path to the directory containing plugin modules.
            plugin_type: Type of plugins (e.g., 'stt', 'llm').

        Returns:
            List of loaded plugin names.
        """
        loaded_plugins = []

        if not directory.exists():
            logger.warning(f"Plugin directory {directory} does not exist")
            return loaded_plugins

        for plugin_file in directory.glob("*.py"):
            if plugin_file.name.startswith("__"):
                continue

            plugin_name = f"{plugin_type}_{plugin_file.stem}"
            module_path = f"plugins.{plugin_type}.{plugin_file.stem}"

            plugin = await self.load_plugin_from_path(module_path, plugin_name)
            if plugin:
                loaded_plugins.append(plugin_name)

        return loaded_plugins

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Get a loaded plugin by name.

        Args:
            name: The plugin name.

        Returns:
            The plugin instance, or None if not found.
        """
        return self._plugins.get(name)

    def get_plugin_class(self, name: str) -> Optional[Type[BasePlugin]]:
        """Get a plugin class by name.

        Args:
            name: The plugin name.

        Returns:
            The plugin class, or None if not found.
        """
        return self._plugin_classes.get(name)

    def list_plugins(self) -> List[str]:
        """List all loaded plugin names.

        Returns:
            List of plugin names.
        """
        return list(self._plugins.keys())

    async def unload_plugin(self, name: str) -> bool:
        """Unload a plugin by name.

        Args:
            name: The plugin name.

        Returns:
            True if successfully unloaded, False otherwise.
        """
        plugin = self._plugins.get(name)
        if plugin:
            try:
                await plugin.shutdown()
                del self._plugins[name]
                del self._plugin_classes[name]
                logger.info(f"Unloaded plugin {name}")
                return True
            except Exception as e:
                logger.error(f"Error unloading plugin {name}: {e}")
                return False
        return False

    async def shutdown_all(self) -> None:
        """Shutdown all loaded plugins."""
        for name in list(self._plugins.keys()):
            await self.unload_plugin(name)