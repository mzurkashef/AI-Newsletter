"""
Error handling and retry utilities for AI Newsletter system.

Provides decorators and utilities for handling errors with exponential backoff,
error classification, and comprehensive logging for resilience.
"""

import functools
import logging
from typing import Callable, Type, Tuple, Any, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)

logger = logging.getLogger(__name__)


# Error Classifications

class RetryableError(Exception):
    """Base class for retryable errors (transient failures)."""

    pass


class NetworkError(RetryableError):
    """Network-related errors (connection, timeout, etc.)."""

    pass


class RateLimitError(RetryableError):
    """Rate limiting errors from external services."""

    pass


class TimeoutError(RetryableError):
    """Timeout errors during operations."""

    pass


class PermanentError(Exception):
    """Base class for permanent errors (should not retry)."""

    pass


class AuthenticationError(PermanentError):
    """Authentication/authorization errors."""

    pass


class ValidationError(PermanentError):
    """Validation errors (invalid input, etc.)."""

    pass


class ConfigurationError(PermanentError):
    """Configuration errors."""

    pass


# Error Classification Functions


def is_retryable_error(exception: Exception) -> bool:
    """
    Classify an exception as retryable (transient) or permanent.

    Retryable errors:
    - Network errors (connection, timeout)
    - Rate limiting
    - Temporary service failures

    Non-retryable errors:
    - Authentication failures
    - Validation errors
    - Configuration errors
    - Client errors (4xx)

    Args:
        exception: The exception to classify

    Returns:
        bool: True if the error is retryable, False otherwise

    Example:
        >>> try:
        ...     result = some_operation()
        ... except Exception as e:
        ...     if is_retryable_error(e):
        ...         # Retry logic
        ...     else:
        ...         # Log and fail
    """
    # Check for explicitly retryable error types
    if isinstance(exception, RetryableError):
        return True

    # Check for permanent error types
    if isinstance(exception, PermanentError):
        return False

    # Check for specific exception types from libraries
    exception_name = type(exception).__name__

    # Network-related errors
    if exception_name in [
        "ConnectionError",
        "TimeoutError",
        "socket.timeout",
        "urllib3.exceptions.ConnectTimeoutError",
        "urllib3.exceptions.ReadTimeoutError",
        "requests.exceptions.ConnectionError",
        "requests.exceptions.Timeout",
        "requests.exceptions.ConnectTimeout",
        "requests.exceptions.ReadTimeout",
    ]:
        return True

    # Rate limiting
    if exception_name in [
        "requests.exceptions.HTTPError",  # Some HTTP errors are retryable
        "HTTPError",
    ]:
        # Check status code if available
        if hasattr(exception, "response"):
            status_code = getattr(exception.response, "status_code", None)
            if status_code in [429, 503, 504]:  # Rate limit, Service Unavailable, Gateway Timeout
                return True
        return False

    # Default: treat unknown errors as non-retryable (safe default)
    return False


def get_error_message(exception: Exception) -> str:
    """
    Extract a human-readable error message from an exception.

    Args:
        exception: The exception to extract message from

    Returns:
        str: Human-readable error message

    Example:
        >>> try:
        ...     risky_operation()
        ... except Exception as e:
        ...     message = get_error_message(e)
        ...     logger.error(f"Operation failed: {message}")
    """
    # Try standard message
    if str(exception):
        return str(exception)

    # Fallback to exception type
    return type(exception).__name__


# Retry Decorators

def with_retries(
    max_attempts: int = 3,
    backoff_multiplier: float = 1.0,
    backoff_min: float = 1.0,
    backoff_max: float = 4.0,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
) -> Callable:
    """
    Decorator to add retry logic with exponential backoff.

    Retries on specified exception types with exponential backoff timing.
    Logs each retry attempt and final results.

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        backoff_multiplier: Exponential backoff multiplier (default: 1.0)
        backoff_min: Minimum backoff delay in seconds (default: 1.0)
        backoff_max: Maximum backoff delay in seconds (default: 4.0)
        retryable_exceptions: Tuple of exception types to retry on (default: retryable errors)

    Returns:
        Callable: Decorated function with retry logic

    Raises:
        RetryError: If max attempts exceeded

    Example:
        >>> @with_retries(max_attempts=3, backoff_min=0.5, backoff_max=2.0)
        ... def fetch_data(url):
        ...     return requests.get(url).json()
        ...
        >>> try:
        ...     data = fetch_data("https://api.example.com/data")
        ... except RetryError:
        ...     logger.error("Failed after 3 retries")
    """
    # Default to retryable exceptions
    if retryable_exceptions is None:
        retryable_exceptions = (RetryableError, NetworkError, TimeoutError, RateLimitError)

    def decorator(func: Callable) -> Callable:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(
                multiplier=backoff_multiplier,
                min=backoff_min,
                max=backoff_max,
            ),
            retry=retry_if_exception_type(retryable_exceptions),
            reraise=True,
        )
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return func(*args, **kwargs)

        return wrapper

    return decorator


def with_retries_and_logging(
    max_attempts: int = 3,
    backoff_multiplier: float = 1.0,
    backoff_min: float = 1.0,
    backoff_max: float = 4.0,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    operation_name: Optional[str] = None,
) -> Callable:
    """
    Decorator to add retry logic with comprehensive logging.

    Logs:
    - Attempt number and total
    - Error message on each failure
    - Exponential backoff delay before retry
    - Final success or failure

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        backoff_multiplier: Exponential backoff multiplier (default: 1.0)
        backoff_min: Minimum backoff delay in seconds (default: 1.0)
        backoff_max: Maximum backoff delay in seconds (default: 4.0)
        retryable_exceptions: Tuple of exception types to retry on
        operation_name: Name of operation for logging (default: function name)

    Returns:
        Callable: Decorated function with retry logic and logging

    Example:
        >>> @with_retries_and_logging(
        ...     max_attempts=3,
        ...     operation_name="API call"
        ... )
        ... def call_api(endpoint):
        ...     return requests.get(endpoint).json()
    """
    # Default to retryable exceptions
    if retryable_exceptions is None:
        retryable_exceptions = (RetryableError, NetworkError, TimeoutError, RateLimitError)

    def decorator(func: Callable) -> Callable:
        operation = operation_name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    logger.debug(f"Attempting {operation} (attempt {attempt}/{max_attempts})")
                    result = func(*args, **kwargs)
                    logger.info(f"{operation} succeeded on attempt {attempt}")
                    return result

                except Exception as e:
                    last_exception = e
                    error_msg = get_error_message(e)

                    if not isinstance(e, retryable_exceptions):
                        # Non-retryable error - fail immediately
                        logger.error(f"{operation} failed with non-retryable error: {error_msg}")
                        raise

                    if attempt >= max_attempts:
                        # Last attempt failed
                        logger.error(
                            f"{operation} failed after {max_attempts} attempts. "
                            f"Last error: {error_msg}"
                        )
                        raise

                    # Calculate backoff delay
                    delay = min(
                        backoff_max,
                        backoff_min * (backoff_multiplier ** (attempt - 1)),
                    )
                    logger.warning(
                        f"{operation} failed on attempt {attempt}/{max_attempts}: {error_msg}. "
                        f"Retrying in {delay:.1f}s..."
                    )

            # Should not reach here
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


# Context Manager for Error Handling

class ErrorContext:
    """Context manager for handling errors with logging."""

    def __init__(
        self,
        operation_name: str,
        log_level: int = logging.INFO,
        suppress_errors: bool = False,
        default_return: Any = None,
    ):
        """
        Initialize error context manager.

        Args:
            operation_name: Name of the operation (for logging)
            log_level: Logging level for success (default: INFO)
            suppress_errors: Whether to suppress errors (default: False)
            default_return: Value to return if error suppressed (default: None)

        Example:
            >>> with ErrorContext("data processing"):
            ...     process_data()
        """
        self.operation_name = operation_name
        self.log_level = log_level
        self.suppress_errors = suppress_errors
        self.default_return = default_return
        self.exception = None

    def __enter__(self):
        """Enter context."""
        logger.debug(f"Starting {self.operation_name}...")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and handle any exception."""
        if exc_type is None:
            logger.log(self.log_level, f"{self.operation_name} completed successfully")
            return False

        self.exception = exc_val
        error_msg = get_error_message(exc_val)

        if is_retryable_error(exc_val):
            logger.warning(f"{self.operation_name} failed with retryable error: {error_msg}")
        else:
            logger.error(f"{self.operation_name} failed with permanent error: {error_msg}")

        if self.suppress_errors:
            logger.info(f"{self.operation_name} error suppressed, continuing...")
            return True

        return False


# Utility Functions

def retry_with_exponential_backoff(
    func: Callable,
    args: tuple = (),
    kwargs: Optional[dict] = None,
    max_attempts: int = 3,
    backoff_multiplier: float = 1.0,
    backoff_min: float = 1.0,
    backoff_max: float = 4.0,
) -> Any:
    """
    Execute a function with retry logic and exponential backoff.

    Manual retry execution without decorator.

    Args:
        func: Function to execute
        args: Positional arguments for function
        kwargs: Keyword arguments for function
        max_attempts: Maximum number of attempts
        backoff_multiplier: Exponential backoff multiplier
        backoff_min: Minimum backoff delay in seconds
        backoff_max: Maximum backoff delay in seconds

    Returns:
        Any: Function return value

    Raises:
        Exception: If all attempts fail

    Example:
        >>> result = retry_with_exponential_backoff(
        ...     risky_operation,
        ...     args=(url,),
        ...     max_attempts=3
        ... )
    """
    import time

    if kwargs is None:
        kwargs = {}

    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if not is_retryable_error(e):
                raise

            if attempt >= max_attempts:
                raise

            # Calculate backoff
            delay = min(
                backoff_max,
                backoff_min * (backoff_multiplier ** (attempt - 1)),
            )
            logger.warning(
                f"Attempt {attempt} failed: {get_error_message(e)}. "
                f"Retrying in {delay:.1f}s..."
            )
            time.sleep(delay)

    # Should not reach here
    if last_exception:
        raise last_exception
