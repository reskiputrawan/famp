#!/usr/bin/env python3
"""
Facebook Account Management Platform (FAMP) main entry point.
"""

import asyncio
import logging
import sys
from pathlib import Path

from famp.cli import main as cli_main, Context
from famp.core.account import AccountManager
from famp.core.browser import BrowserManager
from famp.core.config import Settings
from famp.core.logging import setup_logging
from famp.plugin import PluginManager

async def async_main():
    """Async main function to initialize and run FAMP components."""
    # Load configuration
    settings = Settings()

    # Setup logging
    setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_format=settings.log_format
    )

    logger = logging.getLogger("famp")
    logger.info("Starting FAMP")

    try:
        # Initialize core components
        account_manager = AccountManager(data_dir=Path(settings.data_dir) / "accounts")
        browser_manager = BrowserManager(data_dir=Path(settings.data_dir) / "browsers")
        plugin_manager = PluginManager()

        # Get click context and set components
        ctx_obj = Context()
        ctx_obj.settings = settings
        ctx_obj.account_manager = account_manager
        ctx_obj.browser_manager = browser_manager
        ctx_obj.plugin_manager = plugin_manager

        # Run CLI with component instances
        await cli_main(ctx_obj)

    except KeyboardInterrupt:
        logger.info("FAMP terminated by user")
    except Exception as e:
        logger.exception(f"Error in FAMP: {e}")
        return 1
    finally:
        # Ensure all browsers are closed
        if 'browser_manager' in locals():
            await browser_manager.close_all()

        logger.info("FAMP shutdown complete")

    return 0

def main():
    """Main entry point for FAMP."""
    try:
        exit_code = asyncio.run(async_main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nFAMP terminated by user")
        sys.exit(0)

if __name__ == "__main__":
    main()
