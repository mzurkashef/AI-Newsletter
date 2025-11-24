"""Utilities module for AI Newsletter system."""

from .logging_setup import (
    setup_logging,
    get_logger,
    configure_logger,
    mask_secrets,
    LogContextManager,
    SensitiveDataFilter,
    ColoredFormatter,
)
from .error_handling import (
    RetryableError,
    NetworkError,
    RateLimitError,
    TimeoutError,
    PermanentError,
    AuthenticationError,
    ValidationError,
    ConfigurationError,
    is_retryable_error,
    get_error_message,
    with_retries,
    with_retries_and_logging,
    ErrorContext,
    retry_with_exponential_backoff,
)

__all__ = [
    # Logging
    "setup_logging",
    "get_logger",
    "configure_logger",
    "mask_secrets",
    "LogContextManager",
    "SensitiveDataFilter",
    "ColoredFormatter",
    # Error Handling
    "RetryableError",
    "NetworkError",
    "RateLimitError",
    "TimeoutError",
    "PermanentError",
    "AuthenticationError",
    "ValidationError",
    "ConfigurationError",
    "is_retryable_error",
    "get_error_message",
    "with_retries",
    "with_retries_and_logging",
    "ErrorContext",
    "retry_with_exponential_backoff",
]
