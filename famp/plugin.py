"""Plugin system for FAMP."""

import asyncio
import datetime
import enum
import importlib
import inspect
import logging
import pkgutil
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union

from nodriver import Tab
from pydantic import BaseModel

from famp.core.account import FacebookAccount

logger = logging.getLogger(__name__)

class ErrorCode(enum.Enum):
    """Error codes for plugin system."""
    CONFIG_ERROR = "CONFIG_ERROR"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    INITIALIZATION_ERROR = "INITIALIZATION_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    PERMISSION_ERROR = "PERMISSION_ERROR"
    RESOURCE_ERROR = "RESOURCE_ERROR"

class RetryConfig(BaseModel):
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 30.0  # seconds
    exponential_base: float = 2.0
    retry_codes: Set[ErrorCode] = {
        ErrorCode.NETWORK_ERROR,
        ErrorCode.TIMEOUT_ERROR,
        ErrorCode.RESOURCE_ERROR
    }

class PluginError(Exception):
    """Base class for plugin errors."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        plugin_name: str,
        context: Optional[Dict[str, Any]] = None,
        *args: object
    ) -> None:
        """Initialize plugin error.

        Args:
            code: Error code
            message: Error message
            plugin_name: Name of the plugin that raised the error
            context: Additional context information
        """
        super().__init__(message, *args)
        self.code = code
        self.message = message
        self.plugin_name = plugin_name
        self.context = context or {}
        self.timestamp = datetime.datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary format.

        Returns:
            Dictionary representation of the error
        """
        return {
            "code": self.code.value,
            "message": self.message,
            "plugin_name": self.plugin_name,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context
        }

class PluginConfigError(PluginError):
    """Error raised when plugin configuration is invalid."""
    def __init__(self, message: str, plugin_name: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.CONFIG_ERROR, message, plugin_name, context)

class PluginExecutionError(PluginError):
    """Error raised during plugin execution."""
    def __init__(self, message: str, plugin_name: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.EXECUTION_ERROR, message, plugin_name, context)

class PluginDependencyError(PluginError):
    """Error raised when plugin dependencies cannot be satisfied."""
    def __init__(self, message: str, plugin_name: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.DEPENDENCY_ERROR, message, plugin_name, context)

@dataclass
class PluginDependency:
    """Represents a plugin dependency with version constraints."""
    name: str
    version_constraint: Optional[str] = None
    optional: bool = False

class PluginMetadata(BaseModel):
    """Metadata for a plugin."""
    name: str
    description: str
    version: str
    categories: List[str] = []
    tags: List[str] = []
    config_schema: Optional[Dict[str, Any]] = None
    documentation: Optional[str] = None
    health_status: Optional[str] = None
    author: Optional[str] = None
    homepage: Optional[str] = None
    license: Optional[str] = None

class Plugin(ABC):
    """Base class for FAMP plugins."""

    name: str = "base_plugin"
    description: str = "Base plugin class"
    version: str = "0.1.0"

    def __init__(self):
        """Initialize plugin."""
        self.config: Dict[str, Any] = {}
        self._metadata = PluginMetadata(
            name=self.name,
            description=self.description,
            version=self.version
        )

    @abstractmethod
    async def run(self, tab: Tab, account: FacebookAccount) -> Dict[str, Any]:
        """Run the plugin.

        Args:
            tab: nodriver Tab object
            account: Facebook account to use

        Returns:
            Dictionary with execution results

        Raises:
            PluginError: On plugin-specific errors
        """
        raise NotImplementedError("Plugin must implement run method")

    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the plugin.

        Args:
            config: Configuration dictionary

        Raises:
            PluginConfigError: If configuration is invalid
        """
        try:
            self._validate_config(config)
            self.config = config
        except Exception as e:
            raise PluginConfigError(
                f"Invalid configuration: {str(e)}",
                self.name,
                {"config": config}
            )

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate plugin configuration.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If configuration is invalid
        """
        if self._metadata.config_schema:
            # TODO: Implement config validation against schema
            pass

    @property
    def requires(self) -> List[PluginDependency]:
        """List of required plugins.

        Returns:
            List of plugin dependencies
        """
        return []

    @property
    def metadata(self) -> PluginMetadata:
        """Get plugin metadata.

        Returns:
            Plugin metadata
        """
        return self._metadata

    def update_metadata(self, **kwargs) -> None:
        """Update plugin metadata.

        Args:
            **kwargs: Metadata fields to update
        """
        self._metadata = self._metadata.model_copy(update=kwargs)

    def is_error_retryable(self, error: PluginError) -> bool:
        """Check if an error is retryable.

        Args:
            error: Error to check

        Returns:
            True if error is retryable, False otherwise
        """
        return error.code in RetryConfig().retry_codes

    async def get_health(self) -> Dict[str, Any]:
        """Get plugin health information.

        Returns:
            Dictionary with health status information
        """
        try:
            # Basic health check
            return {
                "status": "healthy",
                "timestamp": datetime.datetime.now().isoformat(),
                "version": self.version
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "timestamp": datetime.datetime.now().isoformat(),
                "error": str(e),
                "version": self.version
            }

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
        self._dependency_graph: Dict[str, Set[str]] = {}
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
                                self._register_plugin(name, plugin_inst)
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
                                        self._register_plugin(name, plugin_inst)
                                        break
                            except (ImportError, AttributeError) as e:
                                logger.warning(f"Failed to load plugin {name}: {e}")
                    except Exception as e:
                        logger.error(f"Error loading plugin {name}: {e}")
            finally:
                # Remove from path
                if str(plugin_dir.parent) in sys.path:
                    sys.path.remove(str(plugin_dir.parent))

    def _register_plugin(self, name: str, plugin: Plugin) -> None:
        """Register a plugin with the manager.

        Args:
            name: Plugin name
            plugin: Plugin instance
        """
        self.plugin_instances[name] = plugin
        self.plugins[name] = plugin.__class__

        # Update dependency graph
        deps = {dep.name for dep in plugin.requires if not dep.optional}
        self._dependency_graph[name] = deps

        logger.info(f"Loaded plugin: {name} ({plugin.description})")

    def _validate_dependencies(self, name: str) -> None:
        """Validate plugin dependencies.

        Args:
            name: Plugin name to validate

        Raises:
            PluginDependencyError: If dependencies are invalid
        """
        plugin = self.get_plugin(name)
        if not plugin:
            raise PluginDependencyError(f"Plugin {name} not found", name)

        for dep in plugin.requires:
            if dep.name not in self.plugin_instances and not dep.optional:
                raise PluginDependencyError(
                    f"Required plugin {dep.name} for {name} not found",
                    name,
                    {"missing_dependency": dep.name}
                )

    def _detect_circular_dependencies(self, name: str) -> None:
        """Detect circular dependencies for a plugin.

        Args:
            name: Plugin name to check

        Raises:
            PluginDependencyError: If circular dependencies are detected
        """
        visited = set()
        path = []

        def visit(node: str) -> None:
            if node in path:
                cycle = path[path.index(node):] + [node]
                raise PluginDependencyError(
                    f"Circular dependency detected: {' -> '.join(cycle)}",
                    name,
                    {"dependency_cycle": cycle}
                )
            if node not in visited:
                visited.add(node)
                path.append(node)
                for dep in self._dependency_graph.get(node, set()):
                    visit(dep)
                path.pop()

        visit(name)

    async def _retry_execution(
        self,
        plugin: Plugin,
        tab: Tab,
        account: FacebookAccount,
        error: PluginError,
        retry_config: Optional[RetryConfig] = None
    ) -> Dict[str, Any]:
        """Retry plugin execution with exponential backoff.

        Args:
            plugin: Plugin to retry
            tab: Browser tab
            account: Facebook account
            error: Original error that triggered retry
            retry_config: Retry configuration

        Returns:
            Plugin execution results

        Raises:
            PluginError: If all retries fail
        """
        config = retry_config or RetryConfig()
        attempt = 1
        last_error = error

        while attempt < config.max_attempts:
            delay = min(
                config.base_delay * (config.exponential_base ** (attempt - 1)),
                config.max_delay
            )

            logger.info(
                f"Retrying plugin {plugin.name} (attempt {attempt+1}/{config.max_attempts}) "
                f"after {delay}s delay"
            )

            await asyncio.sleep(delay)

            try:
                return await plugin.run(tab, account)
            except PluginError as e:
                if not plugin.is_error_retryable(e):
                    raise
                last_error = e

            attempt += 1

        raise PluginExecutionError(
            f"Plugin {plugin.name} failed after {config.max_attempts} attempts",
            plugin.name,
            {
                "attempts": config.max_attempts,
                "last_error": last_error.to_dict()
            }
        )

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a plugin instance by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance or None if not found
        """
        return self.plugin_instances.get(name)

    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all available plugins.

        Returns:
            List of plugin information dictionaries
        """
        return [
            plugin.metadata.model_dump()
            for plugin in self.plugin_instances.values()
        ]

    async def run_plugin(
        self,
        name: str,
        tab: Tab,
        account: FacebookAccount,
        config: Optional[Dict[str, Any]] = None,
        retry_config: Optional[RetryConfig] = None
    ) -> Dict[str, Any]:
        """Run a plugin.

        Args:
            name: Plugin name
            tab: nodriver Tab object
            account: Facebook account to use
            config: Optional plugin configuration
            retry_config: Optional retry configuration

        Returns:
            Plugin execution results

        Raises:
            PluginError: On plugin execution failure
        """
        plugin = self.get_plugin(name)
        if not plugin:
            raise PluginDependencyError(f"Plugin {name} not found", name)

        # Validate dependencies
        self._validate_dependencies(name)
        self._detect_circular_dependencies(name)

        # Configure plugin if config provided
        if config:
            plugin.configure(config)

        # Check and run required plugins first
        results = {}
        for dep in plugin.requires:
            if not dep.optional and dep.name not in self.plugin_instances:
                raise PluginDependencyError(
                    f"Required plugin {dep.name} for {name} not found",
                    name
                )
            try:
                req_results = await self.run_plugin(dep.name, tab, account)
                results[f"{dep.name}_results"] = req_results
            except PluginError as e:
                if not dep.optional:
                    raise

        # Run the plugin with retry support
        try:
            logger.info(f"Running plugin: {name}")
            start_time = datetime.datetime.now()

            try:
                plugin_results = await plugin.run(tab, account)
            except PluginError as e:
                if plugin.is_error_retryable(e) and retry_config:
                    plugin_results = await self._retry_execution(
                        plugin, tab, account, e, retry_config
                    )
                else:
                    raise

            execution_time = (datetime.datetime.now() - start_time).total_seconds()

            # Update results with metadata
            results.update(plugin_results)
            results["execution_time"] = execution_time
            results["success"] = True

            logger.info(f"Plugin {name} completed successfully in {execution_time:.2f}s")
            return results

        except Exception as e:
            if not isinstance(e, PluginError):
                e = PluginExecutionError(str(e), name)

            error_dict = e.to_dict() if isinstance(e, PluginError) else {
                "message": str(e),
                "type": e.__class__.__name__
            }

            logger.error(f"Plugin {name} failed: {e}")
            return {
                "success": False,
                "error": error_dict
            }

    def search_plugins(
        self,
        query: Optional[str] = None,
        categories: Optional[List[str]] = None,
        tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search for plugins based on criteria.

        Args:
            query: Optional search query
            categories: Optional list of categories to filter by
            tags: Optional list of tags to filter by

        Returns:
            List of matching plugin information dictionaries
        """
        results = []
        for plugin in self.plugin_instances.values():
            metadata = plugin.metadata

            # Check query match
            if query:
                query = query.lower()
                if not (
                    query in metadata.name.lower() or
                    query in metadata.description.lower() or
                    any(query in tag.lower() for tag in metadata.tags)
                ):
                    continue

            # Check category match
            if categories and not any(cat in metadata.categories for cat in categories):
                continue

            # Check tag match
            if tags and not any(tag in metadata.tags for tag in tags):
                continue

            results.append(metadata.model_dump())

        return results

    async def check_plugin_health(self, name: str) -> Dict[str, Any]:
        """Check health status of a plugin.

        Args:
            name: Plugin name

        Returns:
            Health status information

        Raises:
            PluginError: If plugin not found
        """
        plugin = self.get_plugin(name)
        if not plugin:
            raise PluginDependencyError(f"Plugin {name} not found", name)

        try:
            health_info = await plugin.get_health()
            plugin.update_metadata(health_status=health_info["status"])
            return health_info
        except Exception as e:
            health_info = {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.datetime.now().isoformat()
            }
            plugin.update_metadata(health_status="unhealthy")
            return health_info

    def reload_plugin(self, name: str) -> bool:
        """Reload a plugin from disk.

        Args:
            name: Plugin name

        Returns:
            True if plugin was reloaded, False otherwise
        """
        if name not in self.plugin_instances:
            return False

        try:
            # Get plugin module
            plugin = self.plugin_instances[name]
            module = inspect.getmodule(plugin.__class__)
            if not module:
                return False

            # Reload module
            importlib.reload(module)

            # Re-instantiate plugin
            plugin_cls = getattr(module, plugin.__class__.__name__)
            new_plugin = plugin_cls()

            # Update registrations
            self.plugin_instances[name] = new_plugin
            self.plugins[name] = plugin_cls

            logger.info(f"Reloaded plugin: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to reload plugin {name}: {e}")
            return False
