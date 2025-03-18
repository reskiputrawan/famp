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
    log_level: str = "INFO",
    log_file: Optional[Union[str, Path]] = None,
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    console: bool = True,
    file_rotation: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    context: Optional[Dict[str, str]] = None
) -> logging.Logger:
    """Set up logging for FAMP.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        log_format: Log message format
        console: Whether to log to console
        file_rotation: Whether to use rotating file handler
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup log files to keep
        context: Dictionary with context information to add to log records

    Returns:
        Root logger
    """
    # Convert string path to Path
    if isinstance(log_file, str):
        log_file = Path(log_file)

    # Get the root logger
    root_logger = logging.getLogger()

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Set log level
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(level)

    # Create formatters
    file_formatter = logging.Formatter(log_format)
    console_formatter = ColoredFormatter(log_format) if COLORAMA_AVAILABLE else file_formatter

    # Add context filter if provided
    if context:
        context_filter = ContextFilter(context)
        root_logger.addFilter(context_filter)

    # Add console handler if requested
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # Add file handler if log file is specified
    if log_file:
        # Create directory if it doesn't exist
        log_file.parent.mkdir(parents=True, exist_ok=True)

        if file_rotation:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count
            )
        else:
            file_handler = logging.FileHandler(log_file)

        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Create FAMP logger
    famp_logger = logging.getLogger("famp")
    famp_logger.info(f"Logging initialized at level {log_level}")

    return root_logger


def get_logger(name: str, context: Optional[Dict[str, str]] = None) -> logging.Logger:
    """Get a logger with optional context.

    Args:
        name: Logger name
        context: Dictionary with context information to add to log records

    Returns:
        Logger with context
    """
    logger = logging.getLogger(name)

    if context:
        # Add context filter
        context_filter = ContextFilter(context)
        logger.addFilter(context_filter)

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
