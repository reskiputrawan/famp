"""
Command-line interface for FAMP.
"""

import asyncio
import logging
import sys
from pathlib import Path

import click

from famp.core.config import Environment
from famp.core.context import Context
from famp.cli.utils import pass_context, handle_error
from famp.cli.account import account_group
from famp.cli.plugin import plugin_group
from famp.cli.workflow import workflow_group

logger = logging.getLogger(__name__)

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
        settings_env = Environment(env.lower())
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

# Register command groups
cli.add_command(account_group)
cli.add_command(plugin_group)
cli.add_command(workflow_group)

@cli.command()
@pass_context
@handle_error
def config(ctx):
    """Show current configuration."""
    from famp.cli.utils import format_dict

    # Convert settings to dictionary excluding sensitive data
    settings_dict = ctx.settings.model_dump(exclude={"security"})

    # Format and display settings
    click.echo("\nCurrent Configuration:")
    click.echo("-" * 50)

    for line in format_dict(settings_dict):
        click.echo(line)

def main():
    """Entry point for the CLI."""
    cli(prog_name="famp")

if __name__ == "__main__":
    main()
