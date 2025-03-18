"""
Account management commands.
"""

import click

from famp.cli.utils import pass_context, handle_error, display_table
from famp.core.account import FacebookAccount

@click.group(name="account")
@click.pass_context
def account_group(ctx):
    """Manage Facebook accounts."""
    pass

@account_group.command("list")
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
    display_table(table_data, headers)

@account_group.command("reset")
@click.confirmation_option(prompt="Are you sure you want to reset all accounts? This cannot be undone!")
@pass_context
@handle_error
def reset_accounts(ctx):
    """Reset accounts file (use if it becomes corrupted)."""
    import os

    accounts_file = ctx.account_manager.accounts_file
    if accounts_file.exists():
        backup_file = accounts_file.with_suffix('.json.bak')
        try:
            # Create backup of current file
            if accounts_file.exists():
                with open(accounts_file, 'rb') as src, open(backup_file, 'wb') as dst:
                    dst.write(src.read())
                click.echo(f"Backup created at {backup_file}")

            # Remove the corrupted file
            os.remove(accounts_file)
            click.echo("Accounts file removed")

            # Reset the accounts manager
            ctx.account_manager.accounts = {}
            ctx.account_manager._save_accounts()
            click.echo("Accounts reset successfully. A new empty accounts file has been created.")
        except Exception as e:
            click.echo(f"Error resetting accounts: {e}", err=True)
    else:
        click.echo("No accounts file found. Creating new one.")
        ctx.account_manager._save_accounts()

@account_group.command("add")
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

@account_group.command("remove")
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

@account_group.command("update")
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
