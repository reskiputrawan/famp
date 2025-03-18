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
    logger = None
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
            if logger:
                logger.error(f"CLI error: Exit code {e.exit_code}")
            else:
                print(f"CLI error: Exit code {e.exit_code}")
            return e.exit_code
    except Exception as e:
        if logger:
            logger.exception(f"Fatal error in FAMP: {e}")
        else:
            print(f"Fatal error in FAMP: {e}")
        return 1
    finally:
        if "context" in locals() and context:
            await context.cleanup()

    return 0

async def handle_shutdown(context: Context) -> None:
    """Handle graceful shutdown.

    Args:
        context: Application context
    """
    try:
        logger = logging.getLogger("famp")
        logger.info("Initiating graceful shutdown...")
    except Exception:
        print("Initiating graceful shutdown...")

    await context.cleanup()

def main():
    """Main entry point for FAMP."""
    try:
        # Set up event loop based on platform
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(loop)
        else:
            loop = asyncio.get_event_loop()

        # Run main function using loop.run_until_complete
        exit_code = loop.run_until_complete(async_main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        # Handle KeyboardInterrupt outside of async code
        print("\nFAMP terminated by user")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error in FAMP main: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
