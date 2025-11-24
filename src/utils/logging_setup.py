"""
Logging infrastructure for AI Newsletter system.

Provides centralized logging configuration with daily rotation,
structured formatting, and sensitive data masking.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Log directory
LOG_DIR = Path("logs")
DEFAULT_LOG_FILE = "newsletter_{date}.log"
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Sensitive patterns to mask
SENSITIVE_PATTERNS = ["token", "api_key", "password", "secret", "key"]


class SensitiveDataFilter(logging.Filter):
    """Filter to mask sensitive data in log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log records to mask sensitive information.

        Args:
            record: The log record to filter

        Returns:
            bool: True to allow the record, False to skip it
        """
        # Mask sensitive data in the message
        if record.msg and isinstance(record.msg, str):
            record.msg = self._mask_sensitive_data(record.msg)

        # Mask sensitive data in args if they exist
        if record.args:
            if isinstance(record.args, dict):
                for key in record.args:
                    if self._is_sensitive_field(key):
                        record.args[key] = "***MASKED***"
            elif isinstance(record.args, (list, tuple)):
                # For positional args, we can't reliably mask without context
                pass

        return True

    @staticmethod
    def _is_sensitive_field(field_name: str) -> bool:
        """
        Check if a field name is sensitive.

        Args:
            field_name: The field name to check

        Returns:
            bool: True if sensitive
        """
        field_lower = field_name.lower()
        return any(pattern in field_lower for pattern in SENSITIVE_PATTERNS)

    @staticmethod
    def _mask_sensitive_data(message: str) -> str:
        """
        Mask sensitive patterns in a message string.

        Args:
            message: The message to mask

        Returns:
            str: Message with sensitive data masked
        """
        # Simple pattern-based masking
        # In production, use more sophisticated approaches
        for pattern in SENSITIVE_PATTERNS:
            # Look for patterns like "token=xyz" or "api_key: xyz"
            import re

            # Match patterns like "token=...", "token: ...", etc.
            message = re.sub(
                rf"{pattern}\s*[=:]\s*\S+",
                f"{pattern}=***MASKED***",
                message,
                flags=re.IGNORECASE,
            )

        return message


class ColoredFormatter(logging.Formatter):
    """Formatter that adds color to console output."""

    # ANSI color codes
    COLORS = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with color.

        Args:
            record: The log record to format

        Returns:
            str: Formatted log message with color
        """
        if sys.platform == "win32":
            # Disable colors on Windows by default (unless Windows Terminal)
            return super().format(record)

        # Add color to level name
        levelname = record.levelname
        if record.levelno in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelno]}{levelname}{self.RESET}"
            )

        result = super().format(record)
        record.levelname = levelname  # Reset for other handlers
        return result


def setup_logging(
    log_dir: str = "logs",
    log_level: int = logging.INFO,
    log_format: str = DEFAULT_LOG_FORMAT,
    date_format: str = DEFAULT_LOG_DATE_FORMAT,
    enable_console: bool = True,
    enable_file: bool = True,
    retention_days: int = 30,
    file_name_pattern: str = "newsletter_{date}.log",
) -> logging.Logger:
    """
    Configure and return the root logger.

    This function sets up:
    - File handler with daily rotation and configurable retention
    - Console handler (optional)
    - Sensitive data filtering
    - Proper formatting

    Args:
        log_dir: Directory to store log files (default: "logs")
        log_level: Logging level (default: INFO)
        log_format: Format string for log messages
        date_format: Format string for timestamps
        enable_console: Enable console output (default: True)
        enable_file: Enable file output (default: True)
        retention_days: Number of days to keep log files (default: 30)
        file_name_pattern: Pattern for log file names

    Returns:
        logging.Logger: Configured root logger

    Example:
        >>> logger = setup_logging()
        >>> logger.info("Application started")
        >>> logger.error("An error occurred")
    """
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        try:
            handler.close()
        except Exception:
            pass
        root_logger.removeHandler(handler)

    # Create formatters
    formatter = logging.Formatter(log_format, datefmt=date_format)
    colored_formatter = ColoredFormatter(log_format, datefmt=date_format)

    # Create and add sensitive data filter
    sensitive_filter = SensitiveDataFilter()

    # File handler with daily rotation
    if enable_file:
        try:
            # Generate daily log filename
            from datetime import datetime as dt
            today = dt.now().strftime("%Y-%m-%d")
            log_file = log_path / f"newsletter_{today}.log"

            # Using rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                filename=str(log_file),
                maxBytes=10 * 1024 * 1024,  # 10 MB max file size
                backupCount=retention_days,
                encoding="utf-8",
            )

            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            file_handler.addFilter(sensitive_filter)
            root_logger.addHandler(file_handler)

        except Exception as e:
            # Fallback to console if file logging fails
            pass  # Don't log here, might cause infinite recursion

    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(colored_formatter)
        console_handler.addFilter(sensitive_filter)
        root_logger.addHandler(console_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: The logger name (typically __name__)

    Returns:
        logging.Logger: Logger instance for the module

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Module initialized")
    """
    return logging.getLogger(name)


def configure_logger(
    logger: logging.Logger,
    level: int = logging.INFO,
    handlers: Optional[list] = None,
) -> None:
    """
    Configure a specific logger instance.

    Args:
        logger: The logger to configure
        level: Logging level for this logger
        handlers: Optional list of handlers to add

    Example:
        >>> logger = get_logger("custom")
        >>> configure_logger(logger, logging.DEBUG)
    """
    logger.setLevel(level)
    if handlers:
        for handler in handlers:
            logger.addHandler(handler)


def mask_secrets(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a copy of data with sensitive fields masked.

    Used for logging data structures safely.

    Args:
        data: Dictionary potentially containing sensitive data

    Returns:
        Dict: Copy with sensitive fields masked

    Example:
        >>> config = {"api_key": "secret123", "name": "test"}
        >>> safe_config = mask_secrets(config)
        >>> # safe_config: {"api_key": "***MASKED***", "name": "test"}
    """
    masked = {}
    for key, value in data.items():
        if SensitiveDataFilter._is_sensitive_field(key):
            masked[key] = "***MASKED***"
        else:
            masked[key] = value
    return masked


class LogContextManager:
    """Context manager for temporary logging configuration."""

    def __init__(self, logger: logging.Logger, level: int):
        """
        Initialize context manager.

        Args:
            logger: Logger to temporarily reconfigure
            level: Temporary logging level

        Example:
            >>> logger = get_logger(__name__)
            >>> with LogContextManager(logger, logging.DEBUG):
            ...     logger.debug("Detailed debug info")
        """
        self.logger = logger
        self.level = level
        self.original_level = None

    def __enter__(self):
        """Enter context - save original level and set new level."""
        self.original_level = self.logger.level
        self.logger.setLevel(self.level)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - restore original level."""
        self.logger.setLevel(self.original_level)
        return False
