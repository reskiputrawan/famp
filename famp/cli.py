"""
Command-line interface for FAMP using Click.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
from tabulate import tabulate

from famp.core.account import AccountManager, FacebookAccount
from famp.core.browser import BrowserManager
from famp.core.config import Environment, Settings
from famp.core.context import Context
from famp.plugin import PluginManager

logger = logging.getLogger(__name__)

pass_context = click.make_pass_decorator(Context, ensure=True)

def handle_error(func):
    """Decorator for handling command errors."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Command error: {e}", exc_info=True)
            click.echo(f"Error: {str(e)}", err=True)
            sys.exit(1)
    return wrapper

@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.version_option()
@click.option(
    '--debug/--no-debug',
    default=False,
    help='Enable debug mode with verbose logging.',
)
@click.option(
    '--env', '-e',
    type=click.Choice(['dev', 'test', 'prod'], case_sensitive=False),
    default='dev',
    help='Environment to run in.',
)
@click.option(
    '--config', '-c',
    type=click.Path(exists=False),
    help='Path to configuration file.',
)
@click.pass_context
def cli(ctx, debug, env, config):
    """FAMP - Facebook Account Management Platform.

    A tool for automating Facebook account management tasks.
    """
    if not ctx.obj or not ctx.obj.is_initialized:
        # Create context if not provided or not initialized
        context = Context()

        # Initialize settings with environment override
        settings_env = Environment(env.upper())
        try:
            asyncio.run(context.initialize(
                config_file=Path(config) if config else None,
                env=settings_env
            ))
        except Exception as e:
            logger.error(f"Failed to initialize context: {e}")
            click.echo(f"Initialization error: {str(e)}", err=True)
            sys.exit(1)

        # Override debug mode if requested
        if debug:
            context.settings.logging.level = "DEBUG"

        # Store context
        ctx.obj = context

@cli.group()
@click.pass_context
def account(ctx):
    """Manage Facebook accounts."""
    pass

@account.command("list")
@pass_context
@handle_error
def list_accounts(ctx):
    """List all Facebook accounts."""
    accounts = ctx.account_manager.list_accounts()

    if not accounts:
        click.echo("No accounts found.")
        return

    # Format accounts for display
    table_data = []
    for acc in accounts:
        status = "Active" if acc.active else "Inactive"
        proxy = acc.proxy or "None"
        notes = acc.notes or ""
        if len(notes) > 30:
            notes = notes[:27] + "..."

        table_data.append([
            acc.account_id,
            acc.email,
            status,
            proxy,
            notes
        ])

    headers = ["ID", "Email", "Status", "Proxy", "Notes"]
    click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))

@account.command("add")
@click.option("--id", "account_id", required=True, help="Unique account identifier")
@click.option("--email", required=True, help="Facebook email")
@click.option("--password", required=True, help="Facebook password")
@click.option("--user-agent", help="Custom user agent")
@click.option("--proxy", help="Proxy server (e.g., socks5://127.0.0.1:9050)")
@click.option("--two-factor", help="Two-factor authentication secret")
@click.option("--notes", help="Notes about this account")
@click.option("--active/--inactive", default=True, help="Account status")
@pass_context
@handle_error
def add_account(ctx, account_id, email, password, user_agent, proxy, two_factor, notes, active):
    """Add a new Facebook account."""
    # Create account object
    account = FacebookAccount(
        account_id=account_id,
        email=email,
        password=password,
        user_agent=user_agent,
        proxy=proxy,
        two_factor_secret=two_factor if two_factor else None,
        notes=notes,
        active=active
    )

    # Add account
    success = ctx.account_manager.add_account(account)

    if success:
        click.echo(f"Account {account_id} added successfully.")
    else:
        click.echo(f"Failed to add account {account_id}. It may already exist.", err=True)

@account.command("remove")
@click.argument("account_id")
@click.confirmation_option(prompt="Are you sure you want to delete this account?")
@pass_context
@handle_error
def remove_account(ctx, account_id):
    """Remove a Facebook account."""
    success = ctx.account_manager.delete_account(account_id)

    if success:
        click.echo(f"Account {account_id} removed successfully.")
    else:
        click.echo(f"Failed to remove account {account_id}. It may not exist.", err=True)

@account.command("update")
@click.argument("account_id")
@click.option("--email", help="Facebook email")
@click.option("--password", help="Facebook password")
@click.option("--user-agent", help="Custom user agent")
@click.option("--proxy", help="Proxy server (e.g., socks5://127.0.0.1:9050)")
@click.option("--two-factor", help="Two-factor authentication secret")
@click.option("--notes", help="Notes about this account")
@click.option("--active/--inactive", help="Account status")
@pass_context
@handle_error
def update_account(ctx, account_id, **kwargs):
    """Update an existing Facebook account."""
    # Get existing account
    account = ctx.account_manager.get_account(account_id)

    if not account:
        click.echo(f"Account {account_id} not found.", err=True)
        return

    # Update fields
    for key, value in kwargs.items():
        if value is not None:
            setattr(account, key, value)

    # Save changes
    success = ctx.account_manager.update_account(account)

    if success:
        click.echo(f"Account {account_id} updated successfully.")
    else:
        click.echo(f"Failed to update account {account_id}.", err=True)

@cli.group()
@click.pass_context
def plugin(ctx):
    """Manage and run plugins."""
    pass

@plugin.command("list")
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
    click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))

@plugin.command("run")
@click.argument("plugin_name")
@click.argument("account_id")
@click.option("--headless/--no-headless", default=None,
              help="Run in headless mode (overrides settings)")
@click.option("--config", "-c", type=click.Path(exists=True),
              help="Plugin configuration file")
@pass_context
@handle_error
async def run_plugin(ctx, plugin_name, account_id, headless, config):
    """Run a plugin for a specific account."""
    # Check if account exists
    account = ctx.account_manager.get_account(account_id)
    if not account:
        click.echo(f"Account {account_id} not found.", err=True)
        return

    # Load plugin configuration if provided
    plugin_config = None
    if config:
        try:
            with open(config, "r") as f:
                plugin_config = json.load(f)
        except Exception as e:
            click.echo(f"Error loading plugin configuration: {e}", err=True)
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
                click.echo(tabulate(result_table, headers=["Key", "Value"], tablefmt="grid"))
        else:
            click.echo(
                f"Plugin {plugin_name} failed: {results.get('message', 'Unknown error')}",
                err=True
            )

    except asyncio.TimeoutError:
        click.echo(f"Plugin {plugin_name} timed out after {ctx.settings.browser.default_timeout}s", err=True)
    except Exception as e:
        click.echo(f"Error running plugin: {e}", err=True)
        logger.exception("Plugin execution error")
    finally:
        # Save cookies and close browser
        try:
            await ctx.browser_manager.save_cookies(account_id)
            await ctx.browser_manager.close_browser(account_id)
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

@cli.command()
@pass_context
@handle_error
def config(ctx):
    """Show current configuration."""
    # Convert settings to dictionary excluding sensitive data
    settings_dict = ctx.settings.model_dump(exclude={"security"})

    # Format and display settings
    click.echo("\nCurrent Configuration:")
    click.echo("-" * 50)

    def format_dict(d, indent=0):
        lines = []
        for key, value in d.items():
            if isinstance(value, dict):
                lines.append("  " * indent + f"{key}:")
                lines.extend(format_dict(value, indent + 1))
            else:
                lines.append("  " * indent + f"{key}: {value}")
        return lines

    for line in format_dict(settings_dict):
        click.echo(line)

if __name__ == "__main__":
    cli(prog_name="famp")
