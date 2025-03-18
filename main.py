#!/usr/bin/env python3
"""
Facebook Account Management Platform (FAMP) main entry point.
"""

import asyncio
import logging
import signal
import sys
import click
from pathlib import Path

from famp.cli import cli, Context
from famp.core.account import AccountManager
from famp.core.browser import BrowserManager
from famp.core.config import Settings
from famp.core.logging import setup_logging
from famp.plugin import PluginManager

async def async_main():
    """Async main function to initialize and run FAMP components."""
    try:
        # Create and initialize context
        context = Context()
        await context.initialize()

        # Get logger after logging is set up
        logger = logging.getLogger("famp")
        logger.info(f"Starting FAMP in {context.settings.env.value} mode")

        # Register signal handlers for graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda s, f: asyncio.create_task(handle_shutdown(context)))

        # Run CLI with initialized context
        result = cli.main(args=sys.argv[1:], prog_name="famp", obj=context, standalone_mode=False)
        if asyncio.iscoroutine(result):
            await result

    except click.exceptions.Exit as e:
        if e.exit_code != 0:  # Normal exit with code 0 is fine
            logger.error(f"CLI error: Exit code {e.exit_code}")
            return e.exit_code
    except Exception as e:
        logger.exception(f"Fatal error in FAMP: {e}")
        return 1
    finally:
        if "context" in locals():
            await context.cleanup()

    return 0

async def handle_shutdown(context: Context) -> None:
    """Handle graceful shutdown.

    Args:
        context: Application context
    """
    logger = logging.getLogger("famp")
    logger.info("Initiating graceful shutdown...")

    await context.cleanup()

    # Stop the event loop
    loop = asyncio.get_event_loop()
    loop.stop()

def main():
    """Main entry point for FAMP."""
    try:
        if sys.platform == "win32":
            # Use ProactorEventLoop on Windows for better subprocess support
            loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(loop)

        exit_code = asyncio.run(async_main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        # Handle KeyboardInterrupt outside of async code
        logger = logging.getLogger("famp")
        logger.info("FAMP terminated by user")
        sys.exit(0)
    except Exception as e:
        logger = logging.getLogger("famp")
        logger.exception("Unexpected error in FAMP main")
        sys.exit(1)

if __name__ == "__main__":
    main()
