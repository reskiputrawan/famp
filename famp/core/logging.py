"""
Enhanced logging system for FAMP.
"""

import logging
import logging.handlers
import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Union

# Try to import colorama for colored console output
try:
    import colorama
    from colorama import Fore, Style
    colorama.init()
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False


class ColoredFormatter(logging.Formatter):
    """Custom formatter for colorized console output."""

    COLORS = {
        'DEBUG': 'CYAN',
        'INFO': 'GREEN',
        'WARNING': 'YELLOW',
        'ERROR': 'RED',
        'CRITICAL': 'RED',
    }

    def __init__(self, fmt=None, datefmt=None, style='%'):
        """Initialize the formatter with specified format strings.

        Args:
            fmt: Format string
            datefmt: Date format string
            style: Style of the format string
        """
        super().__init__(fmt, datefmt, style)
        self.use_colors = COLORAMA_AVAILABLE

    def format(self, record):
        """Format the log record with colors.

        Args:
            record: Log record to format

        Returns:
            Formatted log message
        """
        if not self.use_colors:
            return super().format(record)

        # Save original values
        orig_levelname = record.levelname
        orig_msg = record.msg

        # Add colors
        color_name = self.COLORS.get(record.levelname, 'WHITE')
        color = getattr(Fore, color_name, Fore.WHITE)
        record.levelname = f"{color}{record.levelname}{Style.RESET_ALL}"

        # Format the message
        result = super().format(record)

        # Restore original values
        record.levelname = orig_levelname
        record.msg = orig_msg

        return result


class ContextFilter(logging.Filter):
    """Filter that adds context information to log records."""

    def __init__(self, context=None):
        """Initialize the filter with context.

        Args:
            context: Dictionary with context information
        """
        super().__init__()
        self.context = context or {}

    def filter(self, record):
        """Add context information to the record.

        Args:
            record: Log record to filter

        Returns:
            True (always passes the filter)
        """
        for key, value in self.context.items():
            setattr(record, key, value)
        return True


class PerformanceTimer:
    """Timer for measuring performance metrics."""

    def __init__(self, logger, operation_name):
        """Initialize the timer.

        Args:
            logger: Logger to use for logging
            operation_name: Name of the operation being timed
        """
        self.logger = logger
        self.operation_name = operation_name
        self.start_time = None

    def __enter__(self):
        """Start the timer when entering the context.

        Returns:
            Self
        """
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Log the elapsed time when exiting the context.

        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised
        """
        elapsed = time.time() - self.start_time
        if exc_type:
            self.logger.warning(
                f"Operation '{self.operation_name}' failed after {elapsed:.3f}s: {exc_val}"
            )
        else:
            self.logger.debug(
                f"Operation '{self.operation_name}' completed in {elapsed:.3f}s"
            )


def setup_logging(
    settings: "Settings",
    context: Optional[Dict[str, str]] = None
) -> logging.Logger:
    """Set up logging for FAMP.

    Args:
        settings: Application settings containing logging configuration
        context: Optional dictionary with context information to add to log records

    Returns:
        Root logger
    """
    # Convert string path to Path if needed
    log_file = settings.logging.file
    if isinstance(log_file, str):
        log_file = Path(log_file)

    # Get the root logger
    root_logger = logging.getLogger()

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Set log level from settings
    level = getattr(logging, settings.logging.level.value, logging.INFO)
    root_logger.setLevel(level)

    # Create formatters
    base_format = settings.logging.format
    file_formatter = logging.Formatter(base_format)

    # Enhanced console formatter with colors and environment
    env_format = f"[%(levelname)s] [{settings.env}] {base_format}"
    console_formatter = ColoredFormatter(env_format) if COLORAMA_AVAILABLE else logging.Formatter(env_format)

    # Add context filter if provided
    if context:
        context_filter = ContextFilter(context)
        root_logger.addFilter(context_filter)

    # Always add console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Add file handler if log file is specified
    if log_file:
        # Create directory if it doesn't exist
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Use rotating file handler with settings from config
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=settings.logging.rotate_size,
            backupCount=settings.logging.backup_count
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Create and return FAMP logger
    famp_logger = logging.getLogger("famp")
    famp_logger.info(
        f"Logging initialized: level={settings.logging.level.value}, "
        f"environment={settings.env.value}"
    )

    return root_logger


def get_logger(
    name: str,
    context: Optional[Dict[str, str]] = None,
    level: Optional[str] = None
) -> logging.Logger:
    """Get a logger with optional context and level.

    Args:
        name: Logger name
        context: Optional dictionary with context information
        level: Optional log level override

    Returns:
        Logger with context and level
    """
    logger = logging.getLogger(name)

    if context:
        # Add context filter
        context_filter = ContextFilter(context)
        logger.addFilter(context_filter)

    if level:
        # Override log level if specified
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    return logger


def time_operation(logger, operation_name):
    """Create a context manager for timing operations.

    Args:
        logger: Logger to use for logging
        operation_name: Name of the operation being timed

    Returns:
        PerformanceTimer context manager
    """
    return PerformanceTimer(logger, operation_name)
