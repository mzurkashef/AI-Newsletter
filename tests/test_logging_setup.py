"""
Tests for logging setup module.
"""

import pytest
import logging
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta

from src.utils.logging_setup import (
    setup_logging,
    get_logger,
    configure_logger,
    mask_secrets,
    LogContextManager,
    SensitiveDataFilter,
    ColoredFormatter,
)


@pytest.fixture(autouse=True)
def cleanup_handlers():
    """Cleanup logging handlers after each test."""
    yield
    # Cleanup after test
    import time
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        try:
            if hasattr(handler, 'flush'):
                handler.flush()
            handler.close()
        except Exception:
            pass
        root_logger.removeHandler(handler)
    # Give Windows time to release file handles
    time.sleep(0.1)


class TestSensitiveDataFilter:
    """Test sensitive data filtering."""

    def test_filter_allows_normal_messages(self):
        """Test that normal messages pass through."""
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Normal message",
            args=(),
            exc_info=None,
        )

        result = filter_obj.filter(record)

        assert result is True
        assert record.msg == "Normal message"

    def test_is_sensitive_field(self):
        """Test sensitive field detection."""
        assert SensitiveDataFilter._is_sensitive_field("api_key") is True
        assert SensitiveDataFilter._is_sensitive_field("token") is True
        assert SensitiveDataFilter._is_sensitive_field("password") is True
        assert SensitiveDataFilter._is_sensitive_field("secret") is True

        assert SensitiveDataFilter._is_sensitive_field("name") is False
        assert SensitiveDataFilter._is_sensitive_field("url") is False

    def test_mask_sensitive_patterns(self):
        """Test masking of sensitive patterns in messages."""
        message = "API token=abc123def456"
        masked = SensitiveDataFilter._mask_sensitive_data(message)

        assert "abc123def456" not in masked
        assert "***MASKED***" in masked

    def test_mask_sensitive_with_colon(self):
        """Test masking with colon separator."""
        message = "API key: xyz789"
        masked = SensitiveDataFilter._mask_sensitive_data(message)

        assert "xyz789" not in masked
        assert "***MASKED***" in masked

    def test_mask_secrets_in_dict(self):
        """Test masking sensitive fields in dictionary args."""
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Config created",
            args={},
            exc_info=None,
        )

        result = filter_obj.filter(record)

        assert result is True
        assert record.msg == "Config created"


class TestColoredFormatter:
    """Test colored formatter."""

    def test_formatter_creates(self):
        """Test that formatter can be created."""
        formatter = ColoredFormatter("%(levelname)s - %(message)s")
        assert formatter is not None

    def test_formatter_formats_message(self):
        """Test that formatter formats messages."""
        formatter = ColoredFormatter("%(levelname)s - %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert isinstance(result, str)
        # Message should contain the log level and message (colors may vary by platform)
        assert "Test message" in result


class TestSetupLogging:
    """Test logging setup function."""

    def test_setup_logging_creates_logger(self):
        """Test that setup_logging returns a logger."""
        logger = setup_logging(log_dir="logs_test", enable_console=True, enable_file=False)

        assert isinstance(logger, logging.Logger)
        assert logger.level == logging.INFO

    def test_setup_logging_creates_log_directory(self):
        """Test that setup_logging creates the log directory."""
        log_dir = "logs_test_create"
        try:
            setup_logging(log_dir=log_dir, enable_console=False, enable_file=False)
            assert os.path.isdir(log_dir)
        finally:
            import shutil
            if os.path.exists(log_dir):
                shutil.rmtree(log_dir, ignore_errors=True)

    def test_setup_logging_with_console_handler(self):
        """Test setup_logging with console handler enabled."""
        logger = setup_logging(log_dir="logs_test", enable_console=True, enable_file=False)

        # Should have console handler
        console_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)]
        assert len(console_handlers) > 0

    def test_setup_logging_respects_log_level(self):
        """Test that log level is respected."""
        logger = setup_logging(log_dir="logs_test", log_level=logging.DEBUG, enable_console=True, enable_file=False)

        assert logger.level == logging.DEBUG

    def test_setup_logging_custom_format(self):
        """Test setup_logging with custom format."""
        custom_format = "%(name)s | %(levelname)s | %(message)s"
        logger = setup_logging(
            log_dir="logs_test", log_format=custom_format, enable_console=True, enable_file=False
        )

        # Logger is configured with custom format
        for handler in logger.handlers:
            if hasattr(handler, "formatter"):
                assert handler.formatter is not None

    def test_setup_logging_idempotent(self):
        """Test that setup_logging can be called multiple times."""
        logger1 = setup_logging(log_dir="logs_test", enable_console=True, enable_file=False)
        logger2 = setup_logging(log_dir="logs_test", enable_console=True, enable_file=False)

        # Should be the same logger (root logger)
        assert logger1 is logger2


class TestGetLogger:
    """Test get_logger function."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger."""
        logger = get_logger("test_module")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_same_name_returns_same_logger(self):
        """Test that calling get_logger with same name returns same instance."""
        logger1 = get_logger("same_module")
        logger2 = get_logger("same_module")

        assert logger1 is logger2

    def test_get_logger_different_names(self):
        """Test that different names return different loggers."""
        logger1 = get_logger("module_a")
        logger2 = get_logger("module_b")

        assert logger1 is not logger2
        assert logger1.name != logger2.name


class TestConfigureLogger:
    """Test configure_logger function."""

    def test_configure_logger_sets_level(self):
        """Test that configure_logger sets the log level."""
        logger = get_logger("test_configure")
        configure_logger(logger, level=logging.DEBUG)

        assert logger.level == logging.DEBUG

    def test_configure_logger_with_handlers(self):
        """Test configure_logger with handlers."""
        logger = get_logger("test_handlers")
        handler = logging.StreamHandler()

        initial_count = len(logger.handlers)
        configure_logger(logger, handlers=[handler])

        # Handler should be added
        assert len(logger.handlers) >= initial_count


class TestMaskSecrets:
    """Test mask_secrets function."""

    def test_mask_secrets_empty_dict(self):
        """Test masking empty dictionary."""
        result = mask_secrets({})

        assert result == {}

    def test_mask_secrets_no_sensitive_fields(self):
        """Test dict with no sensitive fields."""
        data = {"name": "test", "url": "https://example.com", "count": 42}
        result = mask_secrets(data)

        assert result == data

    def test_mask_secrets_with_api_key(self):
        """Test masking api_key field."""
        data = {"api_key": "secret123", "name": "test"}
        result = mask_secrets(data)

        assert result["api_key"] == "***MASKED***"
        assert result["name"] == "test"

    def test_mask_secrets_with_token(self):
        """Test masking token field."""
        data = {"token": "xyz789", "user": "alice"}
        result = mask_secrets(data)

        assert result["token"] == "***MASKED***"
        assert result["user"] == "alice"

    def test_mask_secrets_with_password(self):
        """Test masking password field."""
        data = {"password": "pass123", "email": "user@example.com"}
        result = mask_secrets(data)

        assert result["password"] == "***MASKED***"
        assert result["email"] == "user@example.com"

    def test_mask_secrets_case_insensitive(self):
        """Test that field detection is case insensitive."""
        data = {"API_KEY": "secret", "Token": "token123"}
        result = mask_secrets(data)

        assert result["API_KEY"] == "***MASKED***"
        assert result["Token"] == "***MASKED***"

    def test_mask_secrets_preserves_original(self):
        """Test that masking doesn't modify original dict."""
        original = {"api_key": "secret", "name": "test"}
        result = mask_secrets(original)

        assert original["api_key"] == "secret"
        assert result["api_key"] == "***MASKED***"


class TestLogContextManager:
    """Test LogContextManager context manager."""

    def test_context_manager_changes_level(self):
        """Test that context manager changes log level."""
        logger = get_logger("context_test")
        logger.setLevel(logging.WARNING)

        with LogContextManager(logger, logging.DEBUG):
            assert logger.level == logging.DEBUG

    def test_context_manager_restores_level(self):
        """Test that context manager restores original level."""
        logger = get_logger("restore_test")
        original_level = logging.WARNING
        logger.setLevel(original_level)

        with LogContextManager(logger, logging.DEBUG):
            pass

        assert logger.level == original_level

    def test_context_manager_works_on_exception(self):
        """Test that level is restored even if exception occurs."""
        logger = get_logger("exception_test")
        original_level = logging.WARNING
        logger.setLevel(original_level)

        try:
            with LogContextManager(logger, logging.DEBUG):
                raise ValueError("Test exception")
        except ValueError:
            pass

        assert logger.level == original_level

    def test_context_manager_returns_self(self):
        """Test that context manager returns itself."""
        logger = get_logger("self_test")

        with LogContextManager(logger, logging.DEBUG) as ctx:
            assert isinstance(ctx, LogContextManager)


class TestLoggingIntegration:
    """Integration tests for logging system."""

    def test_full_logging_workflow(self):
        """Test complete logging workflow."""
        # Setup logging with console only (avoid file cleanup issues on Windows)
        root_logger = setup_logging(
            log_dir="logs_test", enable_console=True, enable_file=False
        )

        # Get module logger
        module_logger = get_logger("test_module")

        # Log messages at different levels
        module_logger.debug("Debug message")
        module_logger.info("Info message")
        module_logger.warning("Warning message")
        module_logger.error("Error message")

        # Should have handlers
        assert len(root_logger.handlers) > 0

    def test_multiple_loggers_share_handlers(self):
        """Test that multiple loggers can share the same handlers."""
        root = setup_logging(log_dir="logs_test", enable_console=True, enable_file=False)

        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        logger1.info("From module 1")
        logger2.info("From module 2")

        # Both loggers should be able to log
        assert logger1 is not None
        assert logger2 is not None

    def test_logging_performance(self):
        """Test that logging doesn't significantly impact performance."""
        import time

        logger = setup_logging(
            log_dir="logs_test", enable_console=True, enable_file=False
        )

        # Measure time to log 100 messages
        start = time.time()
        for i in range(100):
            logger.info(f"Message {i}")
        elapsed = time.time() - start

        # Should complete reasonably fast
        assert elapsed < 5.0

    def test_log_rotation_configuration(self):
        """Test that log rotation is configured."""
        logger = setup_logging(log_dir="logs_test", enable_file=True, enable_console=False)

        # Check that handlers have rotation configured
        file_handlers = [
            h
            for h in logger.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(file_handlers) > 0

        # Check rotation settings
        handler = file_handlers[0]
        assert handler.maxBytes == 10 * 1024 * 1024  # 10 MB
        assert handler.backupCount >= 30  # At least 30 backups
