"""
Shared utilities for FAMP CLI.
"""

import asyncio
import logging
import sys
from functools import wraps
from typing import Any, Dict, List, Optional

import click
from tabulate import tabulate

from famp.core.context import Context

logger = logging.getLogger(__name__)

# Shared context decorator
pass_context = click.make_pass_decorator(Context, ensure=True)

def handle_error(func):
    """Decorator for handling command errors."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Command error: {e}", exc_info=True)
            click.echo(f"Error: {str(e)}", err=True)
            sys.exit(1)
    return wrapper

def format_table(data: List[List[Any]], headers: List[str]) -> str:
    """Format data as a table using tabulate.
    
    Args:
        data: List of rows (each row is a list of values)
        headers: List of column headers
        
    Returns:
        Formatted table string
    """
    return tabulate(data, headers=headers, tablefmt="grid")

def display_table(data: List[List[Any]], headers: List[str]) -> None:
    """Display a formatted table.
    
    Args:
        data: List of rows (each row is a list of values)
        headers: List of column headers
    """
    click.echo(format_table(data, headers))

def format_dict(d: Dict[str, Any], indent: int = 0) -> List[str]:
    """Format dictionary for display.
    
    Args:
        d: Dictionary to format
        indent: Indentation level
        
    Returns:
        List of formatted string lines
    """
    lines = []
    for key, value in d.items():
        if isinstance(value, dict):
            lines.append("  " * indent + f"{key}:")
            lines.extend(format_dict(value, indent + 1))
        else:
            lines.append("  " * indent + f"{key}: {value}")
    return lines

def load_json_config(config_path: str) -> Optional[Dict[str, Any]]:
    """Load JSON configuration file.
    
    Args:
        config_path: Path to JSON configuration file
        
    Returns:
        Loaded configuration or None if loading fails
    """
    import json
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        return None

def async_command(f):
    """Decorator to run a Click command as an async function."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper
