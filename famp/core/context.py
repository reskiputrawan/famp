"""Component context management for FAMP."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from famp.core.account import AccountManager
from famp.core.browser import BrowserManager
from famp.core.config import Settings
from famp.core.logging import setup_logging
from famp.plugin import PluginManager

logger = logging.getLogger(__name__)

class Context(BaseModel):
    """Manages core FAMP components and their lifecycle."""

    settings: Optional[Settings] = None
    account_manager: Optional[AccountManager] = None
    browser_manager: Optional[BrowserManager] = None
    plugin_manager: Optional[PluginManager] = None
    _initialized: bool = False

    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True

    async def initialize(self, config_file: Optional[Path] = None) -> None:
        """Initialize all components in the correct order.

        Args:
            config_file: Optional path to configuration file
        """
        if self._initialized:
            logger.warning("Context already initialized")
            return

        try:
            # 1. Load settings first
            self.settings = Settings(config_file=config_file)

            # 2. Setup logging
            setup_logging(
                settings=self.settings,
                context={"component": "context"}
            )

            logger.info("Initializing FAMP context")

            # 3. Initialize account manager
            self.account_manager = AccountManager(
                data_dir=self.settings.data_dir / "accounts"
            )
            logger.debug("Account manager initialized")

            # 4. Initialize browser manager
            self.browser_manager = BrowserManager(
                data_dir=self.settings.data_dir / "browsers"
            )
            # Configure browser settings
            self.browser_manager.cookie_settings.update(
                self.settings.browser.cookies.model_dump()
            )
            logger.debug("Browser manager initialized")

            # 5. Initialize plugin manager
            self.plugin_manager = PluginManager(
                plugin_dirs=self.settings.plugins.plugin_dirs
            )
            logger.debug("Plugin manager initialized")

            self._initialized = True
            logger.info("FAMP context initialization complete")

        except Exception as e:
            logger.exception("Failed to initialize context")
            await self.cleanup()
            raise RuntimeError(f"Context initialization failed: {e}")

    async def cleanup(self) -> None:
        """Cleanup and release resources."""
        logger.info("Cleaning up FAMP context")

        # Close all browser instances
        if self.browser_manager:
            try:
                await self.browser_manager.close_all()
                logger.debug("Closed all browser instances")
            except Exception as e:
                logger.error(f"Error closing browsers: {e}")

        # Clear plugin instances
        if self.plugin_manager:
            self.plugin_manager.plugin_instances.clear()
            logger.debug("Cleared plugin instances")

        self._initialized = False
        logger.info("FAMP context cleanup complete")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        asyncio.run(self.cleanup())

    @property
    def is_initialized(self) -> bool:
        """Check if context is initialized."""
        return self._initialized
