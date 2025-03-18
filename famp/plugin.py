"""Plugin system for FAMP."""

import importlib
import inspect
import logging
import pkgutil
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type

from nodriver import Tab

from famp.core.account import FacebookAccount

logger = logging.getLogger(__name__)


class Plugin(ABC):
    """Base class for FAMP plugins."""

    name: str = "base_plugin"
    description: str = "Base plugin class"
    version: str = "0.1.0"

    def __init__(self):
        """Initialize plugin."""
        self.config: Dict[str, Any] = {}

    @abstractmethod
    async def run(self, tab: Tab, account: FacebookAccount) -> Dict[str, Any]:
        """Run the plugin.

        Args:
            tab: nodriver Tab object
            account: Facebook account to use

        Returns:
            Dictionary with execution results
        """
        raise NotImplementedError("Plugin must implement run method")

    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the plugin.

        Args:
            config: Configuration dictionary
        """
        self.config = config

    @property
    def requires(self) -> List[str]:
        """List of required plugins.

        Returns:
            List of plugin names that this plugin requires
        """
        return []


class PluginManager:
    """Manages FAMP plugins."""

    def __init__(self, plugin_dirs: Optional[List[Path]] = None):
        """Initialize plugin manager.

        Args:
            plugin_dirs: List of directories to search for plugins
        """
        self.plugins: Dict[str, Type[Plugin]] = {}
        self.plugin_instances: Dict[str, Plugin] = {}
        self.plugin_dirs = plugin_dirs or [Path(__file__).parent / "plugins"]
        self._load_plugins()

    def _load_plugins(self) -> None:
        """Discover and load plugins from plugin_dirs."""
        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.exists():
                logger.warning(f"Plugin directory {plugin_dir} does not exist")
                continue

            # Add plugin dir to path temporarily
            sys.path.insert(0, str(plugin_dir.parent))

            try:
                for _, name, is_pkg in pkgutil.iter_modules([str(plugin_dir)]):
                    if not is_pkg:
                        continue

                    try:
                        # Import the plugin package
                        plugin_package = importlib.import_module(f"{plugin_dir.name}.{name}")

                        # Look for the main module
                        if hasattr(plugin_package, "plugin"):
                            plugin_inst = plugin_package.plugin
                            if isinstance(plugin_inst, Plugin):
                                self.plugin_instances[name] = plugin_inst
                                self.plugins[name] = plugin_inst.__class__
                                logger.info(f"Loaded plugin: {name} ({plugin_inst.description})")
                        else:
                            # Try to import main module
                            try:
                                main_module = importlib.import_module(f"{plugin_dir.name}.{name}.main")
                                # Find plugin class in the module
                                for attr_name in dir(main_module):
                                    attr = getattr(main_module, attr_name)
                                    if (inspect.isclass(attr) and
                                            issubclass(attr, Plugin) and
                                            attr is not Plugin):
                                        plugin_cls = attr
                                        plugin_inst = plugin_cls()
                                        self.plugin_instances[name] = plugin_inst
                                        self.plugins[name] = plugin_cls
                                        logger.info(f"Loaded plugin: {name} ({plugin_inst.description})")
                                        break
                            except (ImportError, AttributeError) as e:
                                logger.warning(f"Failed to load plugin {name}: {e}")
                    except Exception as e:
                        logger.error(f"Error loading plugin {name}: {e}")
            finally:
                # Remove from path
                if str(plugin_dir.parent) in sys.path:
                    sys.path.remove(str(plugin_dir.parent))

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a plugin instance by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance or None if not found
        """
        return self.plugin_instances.get(name)

    def list_plugins(self) -> List[Dict[str, str]]:
        """List all available plugins.

        Returns:
            List of plugin information dictionaries
        """
        return [
            {
                "name": plugin.name,
                "description": plugin.description,
                "version": plugin.version
            }
            for plugin in self.plugin_instances.values()
        ]

    async def run_plugin(
        self,
        name: str,
        tab: Tab,
        account: FacebookAccount,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run a plugin.

        Args:
            name: Plugin name
            tab: nodriver Tab object
            account: Facebook account to use
            config: Optional plugin configuration

        Returns:
            Plugin execution results

        Raises:
            ValueError: If plugin not found
        """
        plugin = self.get_plugin(name)
        if not plugin:
            raise ValueError(f"Plugin {name} not found")

        # Configure plugin if config provided
        if config:
            plugin.configure(config)

        # Check and run required plugins first
        results = {}
        for req_plugin in plugin.requires:
            if req_plugin not in self.plugin_instances:
                raise ValueError(f"Required plugin {req_plugin} for {name} not found")
            req_results = await self.run_plugin(req_plugin, tab, account)
            results[f"{req_plugin}_results"] = req_results

        # Run the plugin
        try:
            logger.info(f"Running plugin: {name}")
            plugin_results = await plugin.run(tab, account)
            results.update(plugin_results)
            logger.info(f"Plugin {name} completed successfully")
            return results
        except Exception as e:
            error_msg = f"Error running plugin {name}: {e}"
            logger.error(error_msg)
            return {"error": error_msg, "success": False}
