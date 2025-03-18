"""
Plugin management commands.
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

import click
from tabulate import tabulate

from famp.cli.utils import pass_context, handle_error, display_table, load_json_config

@click.group(name="plugin")
@click.pass_context
def plugin_group(ctx):
    """Manage and run plugins."""
    pass

@plugin_group.command("init")
@click.argument("plugin_name")
@click.option("--description", default="A FAMP plugin", help="Plugin description")
@click.option("--version", default="0.1.0", help="Plugin version")
@pass_context
@handle_error
def init_plugin(ctx, plugin_name, description, version):
    """Initialize a new plugin with required structure."""
    # Create plugin directory
    plugin_dir = Path(ctx.settings.plugins.plugin_dirs[0]) / plugin_name

    if plugin_dir.exists():
        click.echo(f"Plugin directory {plugin_dir} already exists.", err=True)
        return

    try:
        # Create plugin directory
        plugin_dir.mkdir(parents=True, exist_ok=True)

        # Create __init__.py
        init_content = f"""\"\"\"FAMP plugin: {plugin_name}.\"\"\"

from famp.plugin import Plugin
from nodriver import Tab
from famp.core.account import FacebookAccount
from typing import Dict, Any

class {plugin_name.title().replace('_', '')}Plugin(Plugin):
    \"\"\"Plugin for {description}.\"\"\"

    name = "{plugin_name}"
    version = "{version}"
    description = "{description}"

    @property
    def requires(self):
        \"\"\"No dependencies required.\"\"\"
        return []

    async def run(self, tab: Tab, account: FacebookAccount) -> Dict[str, Any]:
        \"\"\"Run the plugin.

        Args:
            tab: Browser tab
            account: Facebook account

        Returns:
            Results dictionary
        \"\"\"
        # Import the run function from main.py
        from .main import run as run_main

        # Create a context object with required attributes
        context = type('Context', (), {{
            'browser_manager': None,  # We don't need this anymore
            'account': account
        }})()

        # Since we have direct access to the Tab, we can modify main.py's run function to use it
        context.tab = tab
        return await run_main(context)

# Instantiate the plugin for auto-discovery
plugin = {plugin_name.title().replace('_', '')}Plugin()
"""

        # Create main.py
        main_content = f"""\"\"\"Implementation for {plugin_name} plugin.\"\"\"

import asyncio
import logging

logger = logging.getLogger(__name__)

async def run(context):
    \"\"\"Run the plugin logic.\"\"\"
    logger.info("Starting {plugin_name} plugin")

    try:
        # Use the tab that was passed in
        tab = context.tab
        logger.info("Browser tab ready")

        # Navigate to a simple test page
        logger.info("Navigating to example.com")
        if hasattr(tab, 'goto'):
            await tab.goto("https://example.com")
        else:
            # Try alternate method name
            await tab.get("https://example.com")
        logger.info("Navigation complete")

        # Verify page loaded
        title = await tab.evaluate("document.title")
        logger.info(f"Page loaded with title: {{title}}")

        # Your plugin implementation here
        # ...

        # Wait a moment to see the page
        logger.info("Waiting 3 seconds for visual inspection")
        await asyncio.sleep(3)

        # Take screenshot (if available)
        try:
            screenshot_data = await tab.screenshot()
            logger.info(f"Captured screenshot with {{len(screenshot_data)}} bytes")
        except (AttributeError, NotImplementedError):
            logger.info("Screenshot functionality not available")

        logger.info("Plugin execution complete")

        return {{
            "success": True,
            "title": title,
            "message": "{plugin_name} executed successfully"
        }}
    except Exception as e:
        logger.error(f"Plugin execution failed: {{e}}")
        return {{
            "success": False,
            "error": str(e),
            "message": "Plugin execution failed"
        }}
"""

        # Write files
        with open(plugin_dir / "__init__.py", "w") as f:
            f.write(init_content)

        with open(plugin_dir / "main.py", "w") as f:
            f.write(main_content)

        click.echo(f"Plugin '{plugin_name}' initialized successfully at {plugin_dir}")
        click.echo("To use this plugin, restart FAMP or reload plugins.")
    except Exception as e:
        click.echo(f"Error creating plugin: {e}", err=True)

@plugin_group.command("list")
@pass_context
@handle_error
def list_plugins(ctx):
    """List all available plugins."""
    plugins = ctx.plugin_manager.list_plugins()

    if not plugins:
        click.echo("No plugins found.")
        return

    # Format plugins for display
    table_data = []
    for plugin in plugins:
        table_data.append([
            plugin["name"],
            plugin["description"],
            plugin["version"]
        ])

    headers = ["Name", "Description", "Version"]
    display_table(table_data, headers)

@plugin_group.command("run")
@click.argument("plugin_name", metavar="PLUGIN_NAME")
@click.argument("account_id", metavar="ACCOUNT_ID")
@click.option("--headless/--no-headless", default=None,
              help="Run in headless mode (overrides settings)")
@click.option("--config", "-c", type=click.Path(exists=True),
              help="Plugin configuration file")
@pass_context
@handle_error
async def run_plugin(ctx, plugin_name, account_id, headless, config):
    """Run a plugin for a specific account.

    Arguments:
        PLUGIN_NAME: Name of the plugin to run (required)
        ACCOUNT_ID: ID of the Facebook account to use (required)
                   Use 'account list' command to see available accounts

    Example:
        uv run main.py plugin run manual_login my_account_id
    """
    # Check if account exists
    account = ctx.account_manager.get_account(account_id)
    if not account:
        click.echo(f"Account {account_id} not found.", err=True)
        return

    # Load plugin configuration if provided
    plugin_config = None
    if config:
        plugin_config = load_json_config(config)
        if plugin_config is None:
            return

    try:
        # Use settings default if headless not specified
        use_headless = headless if headless is not None else ctx.settings.browser.default_headless

        # Get browser tab for account
        tab = await ctx.browser_manager.get_tab(
            account_id,
            headless=use_headless,
            proxy=account.proxy,
            user_agent=account.user_agent or ctx.settings.browser.default_user_agent
        )

        # Run plugin with timeout from settings
        async with asyncio.timeout(ctx.settings.browser.default_timeout):
            results = await ctx.plugin_manager.run_plugin(
                plugin_name,
                tab,
                account,
                config=plugin_config
            )

        # Display results
        if results.get("success", False):
            click.echo(f"Plugin {plugin_name} executed successfully.")

            # Format results
            result_table = []
            for key, value in results.items():
                if key not in ["success", "status"]:
                    result_table.append([key, str(value)])

            if result_table:
                display_table(result_table, headers=["Key", "Value"])
        else:
            click.echo(
                f"Plugin {plugin_name} failed: {results.get('message', 'Unknown error')}",
                err=True
            )

    except asyncio.TimeoutError:
        click.echo(f"Plugin {plugin_name} timed out after {ctx.settings.browser.default_timeout}s", err=True)
    except Exception as e:
        click.echo(f"Error running plugin: {e}", err=True)
        ctx.logger.exception("Plugin execution error")
    finally:
        # Save cookies and close browser
        try:
            await ctx.browser_manager.save_cookies(account_id)
            await ctx.browser_manager.close_browser(account_id)
        except Exception as e:
            ctx.logger.error(f"Error during cleanup: {e}")
