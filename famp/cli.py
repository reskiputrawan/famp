"""
Command-line interface for FAMP using Click.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
from tabulate import tabulate

from famp.core.account import AccountManager, FacebookAccount
from famp.core.browser import BrowserManager
from famp.core.config import Settings
from famp.plugin import PluginManager

logger = logging.getLogger(__name__)

class Context:
    """Click context object for storing FAMP components."""

    def __init__(self):
        self.settings = None
        self.account_manager = None
        self.browser_manager = None
        self.plugin_manager = None

pass_context = click.make_pass_decorator(Context, ensure=True)

@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.version_option()
@click.option(
    '--debug/--no-debug',
    default=False,
    help='Enable debug mode with verbose logging.',
)
@click.option(
    '--headless/--no-headless',
    default=True,
    help='Run browser in headless mode.',
)
@click.option(
    '--config', '-c',
    type=click.Path(exists=False),
    help='Path to configuration file.',
)
@click.pass_context
def cli(ctx, debug, headless, config):
    """FAMP - Facebook Account Management Platform.

    A tool for automating Facebook account management tasks.

    Available commands:
    - login: Automate Facebook login process
    - scroll: Scroll through Facebook feed and collect posts
    - publish: Publish posts to Facebook
    """
    # Create context object
    context = Context()

    # Load settings
    context.settings = Settings(config_file=config if config else None)

    # Set debug mode if requested
    if debug:
        context.settings.log_level = "DEBUG"
        os.environ["FAMP_LOG_LEVEL"] = "DEBUG"

    # Store context
    ctx.obj = context

@cli.group()
@click.pass_context
def account(ctx):
    """Manage Facebook accounts."""
    pass

@account.command("list")
@pass_context
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
        click.echo(f"Failed to add account {account_id}. It may already exist.")

@account.command("remove")
@click.argument("account_id")
@click.confirmation_option(prompt="Are you sure you want to delete this account?")
@pass_context
def remove_account(ctx, account_id):
    """Remove a Facebook account."""
    success = ctx.account_manager.delete_account(account_id)

    if success:
        click.echo(f"Account {account_id} removed successfully.")
    else:
        click.echo(f"Failed to remove account {account_id}. It may not exist.")

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
def update_account(ctx, account_id, **kwargs):
    """Update an existing Facebook account."""
    # Get existing account
    account = ctx.account_manager.get_account(account_id)

    if not account:
        click.echo(f"Account {account_id} not found.")
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
        click.echo(f"Failed to update account {account_id}.")

@cli.group()
@click.pass_context
def plugin(ctx):
    """Manage and run plugins."""
    pass

@plugin.command("list")
@pass_context
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
@click.option("--headless/--no-headless", default=False, help="Run in headless mode")
@click.option("--config", "-c", type=click.Path(exists=True), help="Plugin configuration file")
@pass_context
async def run_plugin(ctx, plugin_name, account_id, headless, config):
    """Run a plugin for a specific account."""
    # Check if account exists
    account = ctx.account_manager.get_account(account_id)
    if not account:
        click.echo(f"Account {account_id} not found.")
        return

    # Load plugin configuration if provided
    plugin_config = None
    if config:
        try:
            with open(config, "r") as f:
                import json
                plugin_config = json.load(f)
        except Exception as e:
            click.echo(f"Error loading plugin configuration: {e}")
            return

    # Get browser tab for account
    try:
        tab = await ctx.browser_manager.get_tab(
            account_id,
            headless=headless,
            proxy=account.proxy
        )

        # Run plugin
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
            for key, value in results.items():
                if key not in ["success", "status"]:
                    click.echo(f"{key}: {value}")
        else:
            click.echo(f"Plugin {plugin_name} failed: {results.get('message', 'Unknown error')}")

        # Save cookies
        await ctx.browser_manager.save_cookies(account_id)

    except Exception as e:
        click.echo(f"Error running plugin: {e}")
    finally:
        # Close browser
        await ctx.browser_manager.close_browser(account_id)

@cli.command()
@click.pass_context
def login(ctx):
    """Automate Facebook login process."""
    pass

@cli.command()
@click.pass_context
def scroll(ctx):
    """Scroll through Facebook feed and collect posts."""
    pass

@cli.command()
@click.pass_context
def publish(ctx):
    """Publish posts to Facebook."""
    pass

async def main(context: Context):
    """Async entry point for CLI.

    Args:
        context: Context object with initialized components
    """
    # Create click context
    ctx = click.Context(cli)
    ctx.obj = context

    # Get the command line arguments
    import sys
    args = sys.argv[1:]
    
    if not args:
        # If no arguments provided, show help
        args = ['--help']
    
    # Run CLI with command line arguments
    await cli(args, prog_name="famp", standalone_mode=False, obj=ctx.obj)

if __name__ == "__main__":
    # This is only used when running cli.py directly
    cli(auto_envvar_prefix='FAMP')
