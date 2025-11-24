"""
Tests for error handling and retry utilities.
"""

import pytest
import time
import logging
from src.utils.error_handling import (
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


class TestErrorClassification:
    """Test error classification."""

    def test_retryable_error_hierarchy(self):
        """Test retryable error class hierarchy."""
        assert issubclass(NetworkError, RetryableError)
        assert issubclass(RateLimitError, RetryableError)
        assert issubclass(TimeoutError, RetryableError)

    def test_permanent_error_hierarchy(self):
        """Test permanent error class hierarchy."""
        assert issubclass(AuthenticationError, PermanentError)
        assert issubclass(ValidationError, PermanentError)
        assert issubclass(ConfigurationError, PermanentError)

    def test_retryable_error_instances(self):
        """Test that retryable errors are classified correctly."""
        assert is_retryable_error(NetworkError("Connection failed"))
        assert is_retryable_error(RateLimitError("Rate limited"))
        assert is_retryable_error(TimeoutError("Timeout"))
        assert is_retryable_error(RetryableError("Generic retryable"))

    def test_permanent_error_instances(self):
        """Test that permanent errors are not retryable."""
        assert not is_retryable_error(AuthenticationError("Auth failed"))
        assert not is_retryable_error(ValidationError("Invalid input"))
        assert not is_retryable_error(ConfigurationError("Bad config"))
        assert not is_retryable_error(PermanentError("Generic permanent"))

    def test_builtin_errors_not_retryable(self):
        """Test that generic errors are not retryable by default."""
        assert not is_retryable_error(ValueError("Bad value"))
        assert not is_retryable_error(RuntimeError("Runtime error"))
        assert not is_retryable_error(Exception("Generic error"))

    def test_connection_error_retryable(self):
        """Test that ConnectionError is retryable."""
        error = ConnectionError("Connection refused")
        assert is_retryable_error(error)

    def test_timeout_error_retryable(self):
        """Test that built-in TimeoutError is retryable."""
        import builtins
        error = builtins.TimeoutError("Timeout")
        assert is_retryable_error(error)


class TestErrorMessages:
    """Test error message extraction."""

    def test_get_error_message_with_message(self):
        """Test extracting message from exception with message."""
        error = ValueError("This is an error")
        message = get_error_message(error)

        assert message == "This is an error"

    def test_get_error_message_empty(self):
        """Test extracting message from exception without message."""
        error = ValueError()
        message = get_error_message(error)

        assert message is not None
        assert len(message) > 0

    def test_get_error_message_custom_exception(self):
        """Test extracting message from custom exception."""
        error = NetworkError("Network timeout")
        message = get_error_message(error)

        assert message == "Network timeout"

    def test_get_error_message_complex_error(self):
        """Test extracting message from complex exception."""
        try:
            raise ValueError("Complex error message")
        except ValueError as e:
            message = get_error_message(e)
            assert "Complex error message" in message


class TestWithRetriesDecorator:
    """Test with_retries decorator."""

    def test_succeeds_on_first_attempt(self):
        """Test function succeeds on first attempt."""
        @with_retries(max_attempts=3)
        def success_func():
            return "success"

        result = success_func()
        assert result == "success"

    def test_succeeds_after_retries(self):
        """Test function succeeds after retries."""
        call_count = 0

        @with_retries(max_attempts=3, backoff_min=0.01, backoff_max=0.01)
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("Network timeout")
            return "success"

        result = flaky_func()
        assert result == "success"
        assert call_count == 3

    def test_fails_after_max_attempts(self):
        """Test function fails after max attempts."""
        call_count = 0

        @with_retries(max_attempts=2, backoff_min=0.01, backoff_max=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise NetworkError("Network timeout")

        with pytest.raises(NetworkError):
            always_fails()

        assert call_count == 2

    def test_fails_on_non_retryable_error(self):
        """Test that non-retryable errors aren't retried."""
        call_count = 0

        @with_retries(max_attempts=3)
        def permanent_error_func():
            nonlocal call_count
            call_count += 1
            raise ValidationError("Invalid input")

        with pytest.raises(ValidationError):
            permanent_error_func()

        # Should fail immediately, not retry
        assert call_count == 1

    def test_custom_retryable_exceptions(self):
        """Test with custom retryable exception types."""
        call_count = 0

        @with_retries(
            max_attempts=3,
            retryable_exceptions=(ValueError,),
            backoff_min=0.01,
            backoff_max=0.01,
        )
        def custom_retry_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Custom error")
            return "success"

        result = custom_retry_func()
        assert result == "success"
        assert call_count == 3

    def test_exponential_backoff_timing(self):
        """Test that exponential backoff timing is reasonable."""
        call_count = 0

        @with_retries(
            max_attempts=3,
            backoff_min=0.05,
            backoff_max=0.2,
            backoff_multiplier=2.0,
        )
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("Network timeout")
            return "success"

        start = time.time()
        result = flaky_func()
        elapsed = time.time() - start

        assert result == "success"
        # Should take at least 0.05 + 0.1 seconds (first + second backoff)
        assert elapsed > 0.1


class TestWithRetriesAndLoggingDecorator:
    """Test with_retries_and_logging decorator."""

    def test_logs_success(self, caplog):
        """Test that success is logged."""
        @with_retries_and_logging(max_attempts=3, operation_name="test operation")
        def success_func():
            return "success"

        with caplog.at_level(logging.INFO):
            result = success_func()

        assert result == "success"
        assert "succeeded" in caplog.text.lower()

    def test_logs_retries(self, caplog):
        """Test that retries are logged."""
        call_count = 0

        @with_retries_and_logging(
            max_attempts=3,
            backoff_min=0.01,
            backoff_max=0.01,
            operation_name="flaky operation",
        )
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("Network timeout")
            return "success"

        with caplog.at_level(logging.WARNING):
            result = flaky_func()

        assert result == "success"
        assert "retrying" in caplog.text.lower()

    def test_logs_failure(self, caplog):
        """Test that failure is logged."""
        @with_retries_and_logging(
            max_attempts=2, backoff_min=0.01, backoff_max=0.01, operation_name="failing op"
        )
        def failing_func():
            raise NetworkError("Network timeout")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(NetworkError):
                failing_func()

        assert "failed after" in caplog.text.lower()

    def test_logs_non_retryable_error(self, caplog):
        """Test that non-retryable errors are logged differently."""
        @with_retries_and_logging(max_attempts=3, operation_name="auth op")
        def auth_error_func():
            raise AuthenticationError("Auth failed")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(AuthenticationError):
                auth_error_func()

        assert "non-retryable" in caplog.text.lower()

    def test_operation_name_in_logs(self, caplog):
        """Test that operation name appears in logs."""
        @with_retries_and_logging(max_attempts=1, operation_name="custom operation")
        def test_func():
            return "success"

        with caplog.at_level(logging.INFO):
            test_func()

        assert "custom operation" in caplog.text


class TestErrorContext:
    """Test ErrorContext context manager."""

    def test_success_no_exception(self):
        """Test context manager with successful operation."""
        with ErrorContext("test operation") as ctx:
            pass

        assert ctx.exception is None

    def test_exception_not_suppressed(self):
        """Test that exceptions propagate by default."""
        with pytest.raises(ValueError):
            with ErrorContext("test operation"):
                raise ValueError("Test error")

    def test_exception_suppressed(self):
        """Test exception suppression."""
        with ErrorContext("test operation", suppress_errors=True):
            raise ValueError("Test error")

        # Should not raise

    def test_default_return_when_suppressed(self):
        """Test default return value when error suppressed."""
        with ErrorContext("test operation", suppress_errors=True, default_return="default"):
            raise ValueError("Test error")

        # Should not raise

    def test_logs_success(self, caplog):
        """Test that success is logged."""
        with caplog.at_level(logging.INFO):
            with ErrorContext("test operation"):
                pass

        assert "completed successfully" in caplog.text.lower()

    def test_logs_retryable_error(self, caplog):
        """Test that retryable errors are logged as warnings."""
        with caplog.at_level(logging.WARNING):
            try:
                with ErrorContext("test operation"):
                    raise NetworkError("Network error")
            except NetworkError:
                pass

        assert "retryable" in caplog.text.lower()

    def test_logs_permanent_error(self, caplog):
        """Test that permanent errors are logged as errors."""
        with caplog.at_level(logging.ERROR):
            try:
                with ErrorContext("test operation"):
                    raise AuthenticationError("Auth error")
            except AuthenticationError:
                pass

        assert "permanent" in caplog.text.lower()


class TestRetryWithExponentialBackoff:
    """Test retry_with_exponential_backoff function."""

    def test_succeeds_on_first_attempt(self):
        """Test function succeeds on first attempt."""

        def success_func(value):
            return value * 2

        result = retry_with_exponential_backoff(success_func, args=(5,))
        assert result == 10

    def test_succeeds_after_retries(self):
        """Test function succeeds after retries."""
        call_count = [0]

        def flaky_func(value):
            call_count[0] += 1
            if call_count[0] < 3:
                raise NetworkError("Network timeout")
            return value * 2

        result = retry_with_exponential_backoff(
            flaky_func,
            args=(5,),
            max_attempts=3,
            backoff_min=0.01,
            backoff_max=0.01,
        )
        assert result == 10
        assert call_count[0] == 3

    def test_fails_after_max_attempts(self):
        """Test function fails after max attempts."""
        call_count = [0]

        def always_fails():
            call_count[0] += 1
            raise NetworkError("Network timeout")

        with pytest.raises(NetworkError):
            retry_with_exponential_backoff(
                always_fails,
                max_attempts=2,
                backoff_min=0.01,
                backoff_max=0.01,
            )

        assert call_count[0] == 2

    def test_fails_on_non_retryable_error(self):
        """Test that non-retryable errors aren't retried."""
        call_count = [0]

        def permanent_error():
            call_count[0] += 1
            raise ValidationError("Invalid input")

        with pytest.raises(ValidationError):
            retry_with_exponential_backoff(permanent_error, max_attempts=3)

        # Should fail immediately, not retry
        assert call_count[0] == 1

    def test_with_kwargs(self):
        """Test function with keyword arguments."""

        def func_with_kwargs(a, b=10):
            return a + b

        result = retry_with_exponential_backoff(
            func_with_kwargs, args=(5,), kwargs={"b": 20}
        )
        assert result == 25


class TestErrorIntegration:
    """Integration tests for error handling."""

    def test_decorated_function_with_logging(self, caplog):
        """Test decorated function with logging."""
        call_count = [0]

        @with_retries_and_logging(
            max_attempts=3,
            backoff_min=0.01,
            backoff_max=0.01,
            operation_name="integration test",
        )
        def test_func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise NetworkError("Network error")
            return "success"

        with caplog.at_level(logging.INFO):
            result = test_func()

        assert result == "success"
        assert "integration test" in caplog.text
        assert "retrying" in caplog.text.lower() or "retry" in caplog.text.lower()

    def test_error_context_with_retries(self):
        """Test error context with retry logic."""
        call_count = [0]

        @with_retries(max_attempts=3, backoff_min=0.01, backoff_max=0.01)
        def retryable_func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise NetworkError("Network error")
            return "success"

        with ErrorContext("retryable operation"):
            result = retryable_func()

        assert result == "success"
        assert call_count[0] == 2

    def test_custom_exception_chain(self):
        """Test error classification with exception chaining."""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise NetworkError("Network wrapper") from e
        except NetworkError as e:
            assert is_retryable_error(e)
            assert e.__cause__ is not None
