"""
Plugin management commands.
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

import click
from tabulate import tabulate

from famp.cli.utils import (
    pass_context, handle_error, display_table, load_json_config,
    load_config_file, async_command
)

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

@plugin_group.command("configure")
@click.argument("plugin_name")
@click.argument("config_file", type=click.Path(exists=True))
@click.option("--merge/--replace", default=True, help="Merge with or replace existing config")
@pass_context
@handle_error
def configure_plugin(ctx, plugin_name, config_file, merge):
    """Configure a plugin from a JSON or YAML file."""
    plugin = ctx.plugin_manager.get_plugin(plugin_name)
    if not plugin:
        click.echo(f"Plugin {plugin_name} not found.", err=True)
        return

    # Load configuration
    config = load_config_file(Path(config_file))
    if not config:
        return

    # Get current config if merging
    current_config = plugin.config.copy() if merge else {}

    # Merge or replace config
    if merge:
        current_config.update(config)
    else:
        current_config = config

    # Configure plugin
    try:
        plugin.configure(current_config)
        click.echo(f"Plugin {plugin_name} configured successfully.")
    except Exception as e:
        click.echo(f"Error configuring plugin: {e}", err=True)

@plugin_group.command("configure-interactive")
@click.argument("plugin_name")
@pass_context
@handle_error
def configure_plugin_interactive(ctx, plugin_name):
    """Configure a plugin interactively."""
    import json

    plugin = ctx.plugin_manager.get_plugin(plugin_name)
    if not plugin:
        click.echo(f"Plugin {plugin_name} not found.", err=True)
        return

    # Get schema
    schema = getattr(plugin, "config_schema", {})
    if not schema or not schema.get("properties"):
        click.echo("Plugin does not have a configuration schema.")
        # Fall back to current config
        schema = {"properties": {k: {"description": k} for k in plugin.config}}
        if not schema["properties"]:
            click.echo("No configuration options available.")
            return

    # Build config interactively
    config = {}
    for prop_name, prop_schema in schema.get("properties", {}).items():
        prompt = prop_schema.get("description", prop_name)
        default = plugin.config.get(prop_name, prop_schema.get("default"))

        # Convert default to string for prompt
        if default is not None:
            if isinstance(default, bool):
                pass  # Click handles bool defaults
            else:
                default = str(default)

        # Get type
        prop_type = prop_schema.get("type", "string")

        if prop_type == "boolean":
            config[prop_name] = click.confirm(prompt, default=default)
        elif prop_type == "integer":
            config[prop_name] = click.prompt(prompt, default=default, type=int)
        elif prop_type == "number":
            config[prop_name] = click.prompt(prompt, default=default, type=float)
        elif prop_type == "array":
            if default and isinstance(default, list):
                default_str = ",".join(str(x) for x in default)
            else:
                default_str = ""
            value = click.prompt(f"{prompt} (comma-separated)", default=default_str)
            config[prop_name] = [x.strip() for x in value.split(",")] if value else []
        else:
            config[prop_name] = click.prompt(prompt, default=default)

    # Configure plugin
    try:
        plugin.configure(config)
        click.echo(f"Plugin {plugin_name} configured successfully.")

        # Show new configuration
        click.echo("\nNew configuration:")
        click.echo(json.dumps(plugin.config, indent=2))
    except Exception as e:
        click.echo(f"Error configuring plugin: {e}", err=True)

@plugin_group.command("info")
@click.argument("plugin_name")
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
@pass_context
@handle_error
def plugin_info(ctx, plugin_name, output_json):
    """Show detailed information about a plugin."""
    import json

    plugin = ctx.plugin_manager.get_plugin(plugin_name)
    if not plugin:
        click.echo(f"Plugin {plugin_name} not found.", err=True)
        return

    # Get plugin metadata and other info
    try:
        metadata = plugin.metadata.model_dump()
    except AttributeError:
        # Fallback for plugins without metadata
        metadata = {
            "name": plugin.name,
            "description": plugin.description,
            "version": plugin.version
        }

    # Add dependencies
    deps = []
    for dep in getattr(plugin, "requires", []):
        deps.append({
            "name": dep.name,
            "version_constraint": dep.version_constraint,
            "optional": dep.optional
        })

    # Add configuration
    info = {
        **metadata,
        "dependencies": deps,
        "config": plugin.config,
        "config_schema": getattr(plugin, "config_schema", {})
    }

    # Output in JSON format if requested
    if output_json:
        click.echo(json.dumps(info, indent=2))
        return

    # Format for human-readable output
    click.echo("\nPlugin Information:")
    click.echo("-" * 50)

    # Basic info
    for key in ["name", "version", "description", "author", "license", "homepage"]:
        if key in metadata and metadata[key]:
            click.echo(f"{key.capitalize():15}: {metadata[key]}")

    # Dependencies
    if deps:
        click.echo("\nDependencies:")
        for dep in deps:
            optional = " (optional)" if dep.get("optional") else ""
            version = f" {dep.get('version_constraint')}" if dep.get("version_constraint") else ""
            click.echo(f"- {dep['name']}{version}{optional}")

    # Current configuration
    if plugin.config:
        click.echo("\nCurrent Configuration:")
        click.echo(json.dumps(plugin.config, indent=2))

    # Configuration schema
    if "config_schema" in info and info["config_schema"]:
        click.echo("\nConfiguration Schema:")
        click.echo(json.dumps(info["config_schema"], indent=2))

@plugin_group.command("test")
@click.argument("plugin_name")
@click.option("--account-id", help="Account ID to use (creates temporary account if not specified)")
@click.option("--headless/--no-headless", default=True, help="Run in headless mode")
@pass_context
@handle_error
@async_command
async def test_plugin(ctx, plugin_name, account_id, headless):
    """Test a plugin with minimal configuration."""
    import json
    import time
    from pydantic import SecretStr

    plugin = ctx.plugin_manager.get_plugin(plugin_name)
    if not plugin:
        click.echo(f"Plugin {plugin_name} not found.", err=True)
        return

    # Use provided account or create temporary one
    temp_account = False
    if not account_id:
        # Create temporary test account
        account_id = f"test_{plugin_name}_{int(time.time())}"
        from famp.core.account import FacebookAccount

        test_account = FacebookAccount(
            account_id=account_id,
            email="test@example.com",
            password=SecretStr("test_password")
        )
        ctx.account_manager.add_account(test_account)
        click.echo(f"Created temporary test account: {account_id}")
        temp_account = True
    else:
        # Check if account exists
        account = ctx.account_manager.get_account(account_id)
        if not account:
            click.echo(f"Account {account_id} not found.", err=True)
            return

    try:
        # Get browser tab
        tab = await ctx.browser_manager.get_tab(
            account_id,
            headless=headless,
            user_agent=ctx.settings.browser.default_user_agent
        )

        try:
            # Run plugin
            click.echo(f"Testing plugin {plugin_name}...")
            async with asyncio.timeout(ctx.settings.browser.default_timeout):
                results = await ctx.plugin_manager.run_plugin(
                    plugin_name,
                    tab,
                    ctx.account_manager.get_account(account_id)
                )

            # Display results
            click.echo("\nTest Results:")
            click.echo("-" * 50)
            click.echo(json.dumps(results, indent=2))

        except asyncio.TimeoutError:
            click.echo(f"Plugin {plugin_name} timed out after {ctx.settings.browser.default_timeout}s", err=True)
        except Exception as e:
            click.echo(f"Test failed: {str(e)}", err=True)
            ctx.logger.exception("Plugin execution error")

    except Exception as e:
        click.echo(f"Error setting up test environment: {str(e)}", err=True)
        ctx.logger.exception("Test setup error")

    finally:
        # Cleanup
        if account_id:
            # Save cookies and close browser
            try:
                await ctx.browser_manager.save_cookies(account_id)
                await ctx.browser_manager.close_browser(account_id)
            except Exception as e:
                ctx.logger.error(f"Error during cleanup: {str(e)}")

            # Remove temporary account if needed
            if temp_account:
                ctx.account_manager.remove_account(account_id)
                click.echo(f"Removed temporary test account: {account_id}")
