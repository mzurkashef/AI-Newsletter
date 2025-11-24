"""Test suite for newsletter delivery module."""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime

from src.delivery.newsletter_delivery import (
    NewsletterDelivery,
    DeliveryError,
)
from src.delivery.telegram_bot_client import (
    TelegramConnectionError,
    TelegramAuthenticationError,
)
from src.database.storage import DatabaseStorage


class TestNewsletterDeliveryInitialization:
    """Test NewsletterDelivery initialization."""

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_init_with_valid_token(
        self, mock_validator_class, mock_bot_class
    ):
        """Test initialization with valid token."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("valid_token")

        assert delivery.bot_client == mock_bot
        assert delivery.message_validator == mock_validator
        assert delivery.storage is None

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    def test_init_with_auth_error(self, mock_bot_class):
        """Test initialization with authentication error."""
        mock_bot_class.side_effect = TelegramAuthenticationError(
            "Invalid token"
        )

        with pytest.raises(DeliveryError):
            NewsletterDelivery("invalid_token")

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    def test_init_with_connection_error(self, mock_bot_class):
        """Test initialization with connection error."""
        mock_bot_class.side_effect = TelegramConnectionError(
            "Connection failed"
        )

        with pytest.raises(DeliveryError):
            NewsletterDelivery("token")

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_init_with_storage(
        self, mock_validator_class, mock_bot_class
    ):
        """Test initialization with database storage."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator_class.return_value = mock_validator

        mock_storage = MagicMock(spec=DatabaseStorage)

        delivery = NewsletterDelivery("token", storage=mock_storage)

        assert delivery.storage == mock_storage


class TestDeliveryStatus:
    """Test getting delivery status."""

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_get_delivery_status_authenticated(
        self, mock_validator_class, mock_bot_class
    ):
        """Test getting status when authenticated."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot.get_connection_status.return_value = {
            "is_authenticated": True,
            "bot_id": 123456789,
            "bot_username": "test_bot",
        }
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")
        status = delivery.get_delivery_status()

        assert status["bot_authenticated"] is True
        assert status["bot_id"] == 123456789
        assert status["bot_username"] == "test_bot"
        assert status["ready"] is True

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_get_delivery_status_not_authenticated(
        self, mock_validator_class, mock_bot_class
    ):
        """Test getting status when not authenticated."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot.get_connection_status.return_value = {
            "is_authenticated": False,
            "bot_id": None,
            "bot_username": None,
        }
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")
        status = delivery.get_delivery_status()

        assert status["bot_authenticated"] is False
        assert status["ready"] is False


class TestDeliverNewsletter:
    """Test newsletter delivery."""

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_deliver_single_message(
        self, mock_validator_class, mock_bot_class
    ):
        """Test delivering newsletter in single message."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot.validate_chat_id.return_value = {"is_valid": True, "chat_type": "private"}
        mock_bot.send_messages_sync.return_value = {
            "success": True,
            "total_messages": 1,
            "successful_messages": 1,
            "message_ids": [999],
            "failed_indices": [],
        }
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator.validate_message_length.return_value = {
            "is_valid": True,
            "needs_split": False,
        }
        mock_validator.get_split_messages.return_value = [
            "Newsletter content"
        ]
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")
        result = delivery.deliver_newsletter("Newsletter content", 987654321)

        assert result["success"] is True
        assert result["total_messages"] == 1
        assert result["message_ids"] == [999]
        assert "delivery_timestamp" in result

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_deliver_split_message(
        self, mock_validator_class, mock_bot_class
    ):
        """Test delivering newsletter split into multiple messages."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot.validate_chat_id.return_value = {"is_valid": True, "chat_type": "channel"}
        mock_bot.send_messages_sync.return_value = {
            "success": True,
            "total_messages": 2,
            "successful_messages": 2,
            "message_ids": [101, 102],
            "failed_indices": [],
        }
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator.validate_message_length.return_value = {
            "is_valid": False,
            "needs_split": True,
        }
        mock_validator.split_message.return_value = {
            "total_messages": 2,
            "messages": [Mock(), Mock()],
        }
        mock_validator.get_split_messages.return_value = [
            "Message 1/2\nPart 1",
            "Message 2/2\nPart 2",
        ]
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")
        result = delivery.deliver_newsletter(
            "x" * 5000, 987654321
        )

        assert result["success"] is True
        assert result["total_messages"] == 2
        assert result["message_ids"] == [101, 102]

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_deliver_empty_content(
        self, mock_validator_class, mock_bot_class
    ):
        """Test delivery with empty content."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")

        with pytest.raises(DeliveryError):
            delivery.deliver_newsletter("", 987654321)

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_deliver_invalid_chat_id_type(
        self, mock_validator_class, mock_bot_class
    ):
        """Test delivery with invalid chat ID type."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")

        with pytest.raises(DeliveryError):
            delivery.deliver_newsletter("Newsletter", "invalid_id")

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_deliver_chat_validation_fails(
        self, mock_validator_class, mock_bot_class
    ):
        """Test delivery when chat ID validation fails."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot.validate_chat_id.return_value = {
            "is_valid": False,
            "error": "Chat not found",
        }
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator.validate_message_length.return_value = {
            "is_valid": True,
            "needs_split": False,
        }
        mock_validator.get_split_messages.return_value = ["Newsletter"]
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")

        with pytest.raises(DeliveryError):
            delivery.deliver_newsletter("Newsletter", 987654321)

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_deliver_send_fails(
        self, mock_validator_class, mock_bot_class
    ):
        """Test delivery when message send fails."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot.validate_chat_id.return_value = {"is_valid": True, "chat_type": "private"}
        mock_bot.send_messages_sync.side_effect = TelegramConnectionError(
            "Network error"
        )
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator.validate_message_length.return_value = {
            "is_valid": True,
            "needs_split": False,
        }
        mock_validator.get_split_messages.return_value = ["Newsletter"]
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")

        with pytest.raises(DeliveryError):
            delivery.deliver_newsletter("Newsletter", 987654321)

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_deliver_with_storage(
        self, mock_validator_class, mock_bot_class
    ):
        """Test delivery with storage."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot.validate_chat_id.return_value = {"is_valid": True, "chat_type": "private"}
        mock_bot.send_messages_sync.return_value = {
            "success": True,
            "total_messages": 1,
            "successful_messages": 1,
            "message_ids": [999],
            "failed_indices": [],
        }
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator.validate_message_length.return_value = {
            "is_valid": True,
            "needs_split": False,
        }
        mock_validator.get_split_messages.return_value = ["Newsletter"]
        mock_validator_class.return_value = mock_validator

        mock_storage = MagicMock(spec=DatabaseStorage)
        mock_storage.insert = MagicMock()

        delivery = NewsletterDelivery("token", storage=mock_storage)
        result = delivery.deliver_newsletter("Newsletter", 987654321)

        assert result["success"] is True
        mock_storage.insert.assert_called_once()


class TestTestDeliveryReady:
    """Test delivery readiness checks."""

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_delivery_ready_success(
        self, mock_validator_class, mock_bot_class
    ):
        """Test delivery ready when all checks pass."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot.test_connection.return_value = True
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator.validate_message_length.return_value = {
            "is_valid": True
        }
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")
        result = delivery.test_delivery_ready()

        assert result["ready"] is True
        assert len(result["errors"]) == 0
        assert result["checks"]["bot_connection"] is True
        assert result["checks"]["message_validation"] is True

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_delivery_ready_bot_connection_fails(
        self, mock_validator_class, mock_bot_class
    ):
        """Test delivery ready when bot connection fails."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot.test_connection.return_value = False
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator.validate_message_length.return_value = {
            "is_valid": True
        }
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")
        result = delivery.test_delivery_ready()

        assert result["ready"] is False
        assert len(result["errors"]) > 0
        assert result["checks"]["bot_connection"] is False


class TestValidateConfiguration:
    """Test configuration validation."""

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_validate_configuration_valid(
        self, mock_validator_class, mock_bot_class
    ):
        """Test validating valid configuration."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot.get_connection_status.return_value = {
            "is_authenticated": True
        }
        mock_bot.validate_chat_id.return_value = {"is_valid": True}
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")
        result = delivery.validate_configuration(987654321)

        assert result["valid"] is True
        assert len(result["issues"]) == 0

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_validate_configuration_not_authenticated(
        self, mock_validator_class, mock_bot_class
    ):
        """Test validating configuration when not authenticated."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot.get_connection_status.return_value = {
            "is_authenticated": False
        }
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")
        result = delivery.validate_configuration(987654321)

        assert result["valid"] is False
        assert len(result["issues"]) > 0

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_validate_configuration_invalid_chat(
        self, mock_validator_class, mock_bot_class
    ):
        """Test validating configuration with invalid chat ID."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot.get_connection_status.return_value = {
            "is_authenticated": True
        }
        mock_bot.validate_chat_id.return_value = {
            "is_valid": False,
            "error": "Chat not found",
        }
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")
        result = delivery.validate_configuration(987654321)

        assert result["valid"] is False
        assert len(result["issues"]) > 0

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_validate_configuration_invalid_type(
        self, mock_validator_class, mock_bot_class
    ):
        """Test validating configuration with invalid chat ID type."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot.get_connection_status.return_value = {
            "is_authenticated": True
        }
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")
        result = delivery.validate_configuration("invalid_id")

        assert result["valid"] is False
        assert len(result["issues"]) > 0


class TestNewsletterDeliveryIntegration:
    """Integration tests for newsletter delivery."""

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_complete_delivery_workflow(
        self, mock_validator_class, mock_bot_class
    ):
        """Test complete delivery workflow."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "ai_newsletter_bot"
        mock_bot.get_connection_status.return_value = {
            "is_authenticated": True,
            "bot_id": 123456789,
            "bot_username": "ai_newsletter_bot",
        }
        mock_bot.validate_chat_id.return_value = {"is_valid": True, "chat_type": "channel"}
        mock_bot.send_messages_sync.return_value = {
            "success": True,
            "total_messages": 2,
            "successful_messages": 2,
            "message_ids": [101, 102],
            "failed_indices": [],
        }
        mock_bot.test_connection.return_value = True
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator.validate_message_length.return_value = {
            "is_valid": False,
            "needs_split": True,
        }
        mock_validator.split_message.return_value = {
            "total_messages": 2,
            "messages": [Mock(), Mock()],
        }
        mock_validator.get_split_messages.return_value = [
            "Part 1/2\nContent",
            "Part 2/2\nContent",
        ]
        mock_validator_class.return_value = mock_validator

        # Test complete workflow
        delivery = NewsletterDelivery("token")

        # Check status
        status = delivery.get_delivery_status()
        assert status["ready"] is True

        # Validate configuration
        config = delivery.validate_configuration(987654321)
        assert config["valid"] is True

        # Test readiness
        ready = delivery.test_delivery_ready()
        assert ready["ready"] is True

        # Deliver newsletter
        result = delivery.deliver_newsletter(
            "x" * 5000, 987654321
        )

        assert result["success"] is True
        assert result["total_messages"] == 2
        assert len(result["message_ids"]) == 2


class TestEdgeCases:
    """Test edge cases."""

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_deliver_very_long_newsletter(
        self, mock_validator_class, mock_bot_class
    ):
        """Test delivering very long newsletter."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot.validate_chat_id.return_value = {"is_valid": True, "chat_type": "private"}
        mock_bot.send_messages_sync.return_value = {
            "success": True,
            "total_messages": 5,
            "successful_messages": 5,
            "message_ids": [100, 101, 102, 103, 104],
            "failed_indices": [],
        }
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator.validate_message_length.return_value = {
            "is_valid": False,
            "needs_split": True,
        }
        mock_validator.get_split_messages.return_value = [
            f"Part {i+1}/5\nContent"
            for i in range(5)
        ]
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")
        result = delivery.deliver_newsletter("x" * 20000, 987654321)

        assert result["success"] is True
        assert result["total_messages"] == 5

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_deliver_unicode_content(
        self, mock_validator_class, mock_bot_class
    ):
        """Test delivering newsletter with unicode content."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot.validate_chat_id.return_value = {"is_valid": True, "chat_type": "private"}
        mock_bot.send_messages_sync.return_value = {
            "success": True,
            "total_messages": 1,
            "successful_messages": 1,
            "message_ids": [999],
            "failed_indices": [],
        }
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator.validate_message_length.return_value = {
            "is_valid": True,
            "needs_split": False,
        }
        mock_validator.get_split_messages.return_value = [
            "Newsletter 世界 🚀 Привет"
        ]
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")
        result = delivery.deliver_newsletter(
            "Newsletter 世界 🚀 Привет", 987654321
        )

        assert result["success"] is True

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_deliver_with_html_formatting(
        self, mock_validator_class, mock_bot_class
    ):
        """Test delivering newsletter with HTML formatting."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot.validate_chat_id.return_value = {"is_valid": True, "chat_type": "private"}
        mock_bot.send_messages_sync.return_value = {
            "success": True,
            "total_messages": 1,
            "successful_messages": 1,
            "message_ids": [999],
            "failed_indices": [],
        }
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator.validate_message_length.return_value = {
            "is_valid": True,
            "needs_split": False,
        }
        mock_validator.get_split_messages.return_value = [
            "<b>Bold</b> <i>Italic</i> Newsletter"
        ]
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")
        result = delivery.deliver_newsletter(
            "<b>Bold</b> <i>Italic</i> Newsletter",
            987654321,
            parse_mode="HTML",
        )

        assert result["success"] is True

    @patch("src.delivery.newsletter_delivery.TelegramBotClient")
    @patch("src.delivery.newsletter_delivery.MessageValidator")
    def test_deliver_to_negative_chat_id(
        self, mock_validator_class, mock_bot_class
    ):
        """Test delivering to negative chat ID (group/supergroup)."""
        mock_bot = MagicMock()
        mock_bot.bot_username = "test_bot"
        mock_bot.validate_chat_id.return_value = {"is_valid": True, "chat_type": "supergroup"}
        mock_bot.send_messages_sync.return_value = {
            "success": True,
            "total_messages": 1,
            "successful_messages": 1,
            "message_ids": [999],
            "failed_indices": [],
        }
        mock_bot_class.return_value = mock_bot

        mock_validator = MagicMock()
        mock_validator.validate_message_length.return_value = {
            "is_valid": True,
            "needs_split": False,
        }
        mock_validator.get_split_messages.return_value = ["Newsletter"]
        mock_validator_class.return_value = mock_validator

        delivery = NewsletterDelivery("token")
        result = delivery.deliver_newsletter("Newsletter", -987654321)

        assert result["success"] is True
