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

from famp.cli import cli, main
from famp.core.account import AccountManager
from famp.core.browser import BrowserManager
from famp.core.config import Settings
from famp.core.logging import setup_logging
from famp.plugin import PluginManager
from famp.core.context import Context

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

    except click.exceptions.MissingParameter as e:
        # Handle missing parameter error with user-friendly message
        param_name = getattr(e, 'param', None)
        param_name = param_name.name if param_name else 'parameter'

        if logger:
            logger.error(f"Missing required parameter: {param_name}")

        # Show helpful command usage
        command_path = " ".join([p for p in e.ctx.command_path.split() if p != "famp"])
        print(f"\nError: Missing required parameter: {param_name}")
        print(f"\nUsage: uv run main.py {command_path} [OPTIONS] {param_name.upper()}")

        # For plugin run command specifically
        if 'plugin run' in command_path:
            print("\nExample:")
            print("  uv run main.py plugin run manual_login my_account_id")
            print("\nTo see all accounts:")
            print("  uv run main.py account list")

        return 1

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

if __name__ == "__main__":
    # Use the appropriate event loop handling for nodriver
    try:
        from nodriver import start, loop
        result = loop().run_until_complete(async_main())
        sys.exit(result)
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)
