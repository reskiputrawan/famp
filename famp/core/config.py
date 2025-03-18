"""
Configuration management for FAMP using Pydantic.
"""

import json
import logging
import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

logger = logging.getLogger(__name__)


class LogLevel(str, Enum):
    """Log levels for FAMP."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class CookieSettings(BaseModel):
    """Cookie-specific settings."""

    domain_filter: List[str] = Field(
        default=["facebook.com", "fb.com", "fbcdn.net"],
        description="Domains to keep cookies for"
    )
    expiration_days: int = Field(
        default=30,
        description="Number of days before cookies expire"
    )
    encryption_enabled: bool = Field(
        default=False,
        description="Whether to encrypt cookies"
    )
    encryption_key: Optional[SecretStr] = Field(
        default=None,
        description="Key for cookie encryption"
    )
    auto_refresh: bool = Field(
        default=True,
        description="Automatically refresh cookies before expiration"
    )
    backup_enabled: bool = Field(
        default=True,
        description="Enable cookie backups"
    )
    backup_count: int = Field(
        default=3,
        description="Number of cookie backups to keep"
    )


class BrowserSettings(BaseModel):
    """Browser-specific settings."""

    default_headless: bool = Field(
        default=False,
        description="Run browsers in headless mode by default"
    )
    default_user_agent: Optional[str] = Field(
        default=None,
        description="Default user agent string"
    )
    default_timeout: int = Field(
        default=30,
        description="Default timeout in seconds"
    )
    cookies: CookieSettings = Field(
        default_factory=CookieSettings,
        description="Cookie settings"
    )
    extra_args: List[str] = Field(
        default=[],
        description="Extra arguments to pass to the browser"
    )


class PluginSettings(BaseModel):
    """Plugin-specific settings."""

    auto_load: bool = Field(
        default=True,
        description="Automatically load plugins on startup"
    )
    plugin_dirs: List[Path] = Field(
        default_factory=lambda: [Path.home() / ".famp" / "plugins"],
        description="Directories to search for plugins"
    )
    disabled_plugins: List[str] = Field(
        default=[],
        description="List of plugins to disable"
    )


class Settings(BaseModel):
    """Main settings for FAMP."""

    # General settings
    data_dir: Path = Field(
        default_factory=lambda: Path.home() / ".famp",
        description="Directory to store FAMP data"
    )
    config_file: Optional[Path] = Field(
        default=None,
        description="Path to configuration file"
    )
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Log level"
    )
    log_file: Optional[Path] = Field(
        default=None,
        description="Path to log file"
    )
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format"
    )

    # Component settings
    browser: BrowserSettings = Field(
        default_factory=BrowserSettings,
        description="Browser settings"
    )
    plugins: PluginSettings = Field(
        default_factory=PluginSettings,
        description="Plugin settings"
    )

    def __init__(self, config_file: Optional[Union[str, Path]] = None, **data: Any):
        """Initialize settings.

        Args:
            config_file: Path to configuration file
            **data: Additional settings
        """
        # Convert string path to Path
        if isinstance(config_file, str):
            config_file = Path(config_file)

        # Load settings from environment variables
        env_settings = self._load_from_env()

        # Load settings from config file
        file_settings = {}
        if config_file:
            file_settings = self._load_from_file(config_file)

        # Merge settings (priority: data > env > file > defaults)
        merged_settings = {}
        merged_settings.update(file_settings)
        merged_settings.update(env_settings)
        merged_settings.update(data)

        # Initialize with merged settings
        super().__init__(**merged_settings)

        # Store config file path
        self.config_file = config_file

        # Create data directory
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _load_from_env(self) -> Dict[str, Any]:
        """Load settings from environment variables.

        Returns:
            Dictionary of settings from environment variables
        """
        settings = {}

        # General settings
        if os.environ.get("FAMP_DATA_DIR"):
            settings["data_dir"] = Path(os.environ["FAMP_DATA_DIR"])

        if os.environ.get("FAMP_LOG_LEVEL"):
            settings["log_level"] = os.environ["FAMP_LOG_LEVEL"]

        if os.environ.get("FAMP_LOG_FILE"):
            settings["log_file"] = Path(os.environ["FAMP_LOG_FILE"])

        # More environment variables can be added here

        return settings

    def _load_from_file(self, config_file: Path) -> Dict[str, Any]:
        """Load settings from configuration file.

        Args:
            config_file: Path to configuration file

        Returns:
            Dictionary of settings from file
        """
        if not config_file.exists():
            logger.warning(f"Configuration file {config_file} not found")
            return {}

        try:
            with open(config_file, "r") as f:
                # Determine file type from extension
                if config_file.suffix.lower() in [".yaml", ".yml"]:
                    return yaml.safe_load(f) or {}
                elif config_file.suffix.lower() == ".json":
                    return json.load(f)
                else:
                    logger.warning(f"Unsupported configuration file format: {config_file.suffix}")
                    return {}
        except Exception as e:
            logger.error(f"Error loading configuration file: {e}")
            return {}

    def save(self, config_file: Optional[Path] = None) -> bool:
        """Save settings to configuration file.

        Args:
            config_file: Path to configuration file (defaults to self.config_file)

        Returns:
            True if settings were saved, False otherwise
        """
        config_file = config_file or self.config_file

        if not config_file:
            logger.warning("No configuration file specified")
            return False

        try:
            # Create parent directories if they don't exist
            config_file.parent.mkdir(parents=True, exist_ok=True)

            # Convert to dictionary
            settings_dict = self.model_dump(exclude={"config_file"})

            # Convert Path objects to strings
            settings_dict = self._convert_paths_to_str(settings_dict)

            # Save to file
            with open(config_file, "w") as f:
                if config_file.suffix.lower() in [".yaml", ".yml"]:
                    yaml.dump(settings_dict, f, default_flow_style=False)
                elif config_file.suffix.lower() == ".json":
                    json.dump(settings_dict, f, indent=2)
                else:
                    logger.warning(f"Unsupported configuration file format: {config_file.suffix}")
                    return False

            logger.info(f"Settings saved to {config_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration file: {e}")
            return False

    def _convert_paths_to_str(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Path objects to strings in a dictionary.

        Args:
            data: Dictionary to convert

        Returns:
            Dictionary with Path objects converted to strings
        """
        result = {}

        for key, value in data.items():
            if isinstance(value, Path):
                result[key] = str(value)
            elif isinstance(value, dict):
                result[key] = self._convert_paths_to_str(value)
            elif isinstance(value, list):
                result[key] = [
                    str(item) if isinstance(item, Path) else item
                    for item in value
                ]
            else:
                result[key] = value

        return result

    def reload(self) -> bool:
        """Reload settings from configuration file.

        Returns:
            True if settings were reloaded, False otherwise
        """
        if not self.config_file or not self.config_file.exists():
            logger.warning("No configuration file to reload")
            return False

        try:
            # Load settings from file
            file_settings = self._load_from_file(self.config_file)

            # Update settings
            for key, value in file_settings.items():
                if hasattr(self, key):
                    setattr(self, key, value)

            logger.info(f"Settings reloaded from {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Error reloading settings: {e}")
            return False

    @model_validator(mode="after")
    def validate_cookie_encryption(self) -> "Settings":
        """Validate cookie encryption settings.

        Returns:
            Validated settings
        """
        if self.browser.cookies.encryption_enabled and not self.browser.cookies.encryption_key:
            logger.warning("Cookie encryption enabled but no encryption key provided")

        return self

    @field_validator("data_dir", "log_file", mode="before")
    @classmethod
    def validate_path(cls, value: Any) -> Path:
        """Validate and convert path to Path object.

        Args:
            value: Path value

        Returns:
            Path object
        """
        if value is None:
            return None

        if isinstance(value, str):
            return Path(value).expanduser().absolute()

        if isinstance(value, Path):
            return value.expanduser().absolute()

        raise ValueError(f"Invalid path: {value}")
