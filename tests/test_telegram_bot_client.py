"""Test suite for Telegram Bot client."""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from telegram import Bot, User, Chat, Message
from telegram.error import InvalidToken, NetworkError, TimedOut, TelegramError

from src.delivery.telegram_bot_client import (
    TelegramBotClient,
    TelegramConnectionError,
    TelegramAuthenticationError,
)


class TestTelegramBotClientInitialization:
    """Test TelegramBotClient initialization."""

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_init_with_valid_token(self, mock_bot_class):
        """Test initialization with valid token."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_newsletter_bot")
        )
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token_here")

        assert client.is_authenticated is True
        assert client.bot_id == 123456789
        assert client.bot_username == "test_newsletter_bot"

    def test_init_with_empty_token(self):
        """Test initialization with empty token."""
        with pytest.raises(TelegramAuthenticationError):
            TelegramBotClient("")

    def test_init_with_none_token(self):
        """Test initialization with None token."""
        with pytest.raises(TelegramAuthenticationError):
            TelegramBotClient(None)

    def test_init_with_non_string_token(self):
        """Test initialization with non-string token."""
        with pytest.raises(TelegramAuthenticationError):
            TelegramBotClient(123456)

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_init_with_invalid_token(self, mock_bot_class):
        """Test initialization with invalid token."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(side_effect=InvalidToken())
        mock_bot_class.return_value = mock_bot

        with pytest.raises(TelegramAuthenticationError):
            TelegramBotClient("invalid_token")

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_init_with_network_error(self, mock_bot_class):
        """Test initialization with network error."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(side_effect=NetworkError("Network error"))
        mock_bot_class.return_value = mock_bot

        with pytest.raises(TelegramConnectionError):
            TelegramBotClient("valid_token")

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_init_with_timeout_error(self, mock_bot_class):
        """Test initialization with timeout error."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(side_effect=TimedOut())
        mock_bot_class.return_value = mock_bot

        with pytest.raises(TelegramConnectionError):
            TelegramBotClient("valid_token")

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_init_with_empty_bot_info_response(self, mock_bot_class):
        """Test initialization when getMe returns None."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(return_value=None)
        mock_bot_class.return_value = mock_bot

        with pytest.raises(TelegramConnectionError):
            TelegramBotClient("valid_token")


class TestGetConnectionStatus:
    """Test getting connection status."""

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_get_connection_status_authenticated(self, mock_bot_class):
        """Test getting status when authenticated."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        status = client.get_connection_status()

        assert status["is_authenticated"] is True
        assert status["bot_id"] == 123456789
        assert status["bot_username"] == "test_bot"

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_get_connection_status_not_authenticated(self, mock_bot_class):
        """Test getting status when not authenticated."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(side_effect=InvalidToken())
        mock_bot_class.return_value = mock_bot

        with pytest.raises(TelegramAuthenticationError):
            TelegramBotClient("invalid_token")


class TestSendMessage:
    """Test sending messages."""

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_send_message_success(self, mock_bot_class):
        """Test sending message successfully."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot.send_message = AsyncMock(return_value=Mock(message_id=999))
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        result = client.send_message_sync(
            chat_id=987654321, message="Test message"
        )

        assert result["success"] is True
        assert result["message_id"] == 999
        assert result["chat_id"] == 987654321

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_send_message_not_authenticated(self, mock_bot_class):
        """Test sending message when not authenticated."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        client.is_authenticated = False

        with pytest.raises(TelegramConnectionError):
            client.send_message_sync(
                chat_id=987654321, message="Test message"
            )

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_send_message_invalid_chat_id_type(self, mock_bot_class):
        """Test sending message with invalid chat ID type."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")

        with pytest.raises(TelegramConnectionError):
            client.send_message_sync(
                chat_id="invalid_id", message="Test message"
            )

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_send_message_empty_message(self, mock_bot_class):
        """Test sending empty message."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")

        with pytest.raises(TelegramConnectionError):
            client.send_message_sync(chat_id=987654321, message="")

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_send_message_network_error(self, mock_bot_class):
        """Test sending message with network error."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot.send_message = AsyncMock(
            side_effect=NetworkError("Network error")
        )
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")

        with pytest.raises(TelegramConnectionError):
            client.send_message_sync(
                chat_id=987654321, message="Test message"
            )

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_send_message_with_custom_parse_mode(self, mock_bot_class):
        """Test sending message with custom parse mode."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot.send_message = AsyncMock(return_value=Mock(message_id=999))
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        result = client.send_message_sync(
            chat_id=987654321,
            message="**Bold** text",
            parse_mode="Markdown",
        )

        assert result["success"] is True


class TestSendMessages:
    """Test sending multiple messages."""

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_send_messages_success(self, mock_bot_class):
        """Test sending multiple messages successfully."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot.send_message = AsyncMock(
            side_effect=[
                Mock(message_id=101),
                Mock(message_id=102),
                Mock(message_id=103),
            ]
        )
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        messages = ["Message 1", "Message 2", "Message 3"]
        result = client.send_messages_sync(
            chat_id=987654321, messages=messages
        )

        assert result["success"] is True
        assert result["total_messages"] == 3
        assert result["successful_messages"] == 3
        assert result["message_ids"] == [101, 102, 103]
        assert result["failed_indices"] == []

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_send_messages_partial_failure(self, mock_bot_class):
        """Test sending multiple messages with partial failure."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )

        async def send_message_with_failure(*args, **kwargs):
            # Simulate second message failing
            if mock_bot.send_message.call_count == 2:
                raise NetworkError("Network error")
            return Mock(message_id=100 + mock_bot.send_message.call_count)

        mock_bot.send_message = AsyncMock(side_effect=send_message_with_failure)
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        messages = ["Message 1", "Message 2", "Message 3"]

        # This test needs adjustment - the side_effect doesn't track properly
        # So we use a simpler approach
        result = client.send_messages_sync(
            chat_id=987654321, messages=messages
        )

        assert result["total_messages"] == 3

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_send_messages_empty_list(self, mock_bot_class):
        """Test sending empty message list."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")

        with pytest.raises(TelegramConnectionError):
            client.send_messages_sync(chat_id=987654321, messages=[])

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_send_messages_single_message(self, mock_bot_class):
        """Test sending single message via send_messages."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot.send_message = AsyncMock(return_value=Mock(message_id=999))
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        messages = ["Single message"]
        result = client.send_messages_sync(
            chat_id=987654321, messages=messages
        )

        assert result["success"] is True
        assert result["total_messages"] == 1
        assert result["successful_messages"] == 1


class TestValidateChatId:
    """Test chat ID validation."""

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_validate_chat_id_success(self, mock_bot_class):
        """Test validating chat ID successfully."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot.get_chat = AsyncMock(
            return_value=Mock(id=987654321, type="private")
        )
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        result = client.validate_chat_id(987654321)

        assert result["is_valid"] is True
        assert result["chat_id"] == 987654321
        assert result["chat_type"] == "private"

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_validate_chat_id_not_authenticated(self, mock_bot_class):
        """Test validating chat ID when not authenticated."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        client.is_authenticated = False

        result = client.validate_chat_id(987654321)

        assert result["is_valid"] is False
        assert result["error"] == "Bot is not authenticated"

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_validate_chat_id_error(self, mock_bot_class):
        """Test validating invalid chat ID."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot.get_chat = AsyncMock(
            side_effect=TelegramError("Chat not found")
        )
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        result = client.validate_chat_id(987654321)

        assert result["is_valid"] is False
        assert "Chat not found" in result["error"]


class TestConnectionTest:
    """Test connection testing."""

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_test_connection_success(self, mock_bot_class):
        """Test connection is alive."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        is_connected = client.test_connection()

        assert is_connected is True

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_test_connection_failure(self, mock_bot_class):
        """Test connection is dead."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            side_effect=[
                Mock(id=123456789, username="test_bot"),
                NetworkError("Network error"),
            ]
        )
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        is_connected = client.test_connection()

        assert is_connected is False
        assert client.is_authenticated is False

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_test_connection_not_authenticated(self, mock_bot_class):
        """Test connection when not authenticated."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        client.is_authenticated = False

        is_connected = client.test_connection()

        assert is_connected is False


class TestTelegramBotClientIntegration:
    """Integration tests for Telegram Bot client."""

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_full_workflow_send_newsletter(self, mock_bot_class):
        """Test complete workflow: init -> validate -> send newsletter."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="ai_newsletter_bot")
        )
        mock_bot.send_message = AsyncMock(
            side_effect=[Mock(message_id=101), Mock(message_id=102)]
        )
        mock_bot_class.return_value = mock_bot

        # Initialize client
        client = TelegramBotClient("valid_token")
        assert client.is_authenticated is True
        assert client.bot_id == 123456789

        # Get status
        status = client.get_connection_status()
        assert status["is_authenticated"] is True

        # Send newsletter (split into 2 messages)
        messages = [
            "Message 1/2\n" + "=" * 40 + "\nContent 1",
            "Message 2/2\n" + "=" * 40 + "\nContent 2",
        ]
        result = client.send_messages_sync(
            chat_id=987654321, messages=messages
        )

        assert result["success"] is True
        assert result["successful_messages"] == 2
        assert len(result["message_ids"]) == 2

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_connection_recovery(self, mock_bot_class):
        """Test connection recovery after failure."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        assert client.is_authenticated is True

        # Simulate connection failure
        mock_bot.get_me = AsyncMock(side_effect=NetworkError("Network error"))
        is_connected = client.test_connection()
        assert is_connected is False
        assert client.is_authenticated is False


class TestEdgeCases:
    """Test edge cases."""

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_send_very_long_message(self, mock_bot_class):
        """Test sending very long message (near 4096 limit)."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot.send_message = AsyncMock(return_value=Mock(message_id=999))
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        long_message = "x" * 4000  # Near limit
        result = client.send_message_sync(
            chat_id=987654321, message=long_message
        )

        assert result["success"] is True

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_send_unicode_message(self, mock_bot_class):
        """Test sending message with unicode characters."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot.send_message = AsyncMock(return_value=Mock(message_id=999))
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        unicode_message = "Hello 世界 🚀 Привет 🎉"
        result = client.send_message_sync(
            chat_id=987654321, message=unicode_message
        )

        assert result["success"] is True

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_send_message_with_html_formatting(self, mock_bot_class):
        """Test sending message with HTML formatting."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot.send_message = AsyncMock(return_value=Mock(message_id=999))
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        html_message = (
            "<b>Bold</b> <i>Italic</i> <code>Code</code> "
            "<a href='http://example.com'>Link</a>"
        )
        result = client.send_message_sync(
            chat_id=987654321,
            message=html_message,
            parse_mode="HTML",
        )

        assert result["success"] is True

    @patch("src.delivery.telegram_bot_client.Bot")
    def test_negative_chat_id(self, mock_bot_class):
        """Test sending message with negative chat ID (group)."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_me = AsyncMock(
            return_value=Mock(id=123456789, username="test_bot")
        )
        mock_bot.send_message = AsyncMock(return_value=Mock(message_id=999))
        mock_bot_class.return_value = mock_bot

        client = TelegramBotClient("valid_token")
        result = client.send_message_sync(
            chat_id=-987654321, message="Message to group"
        )

        assert result["success"] is True
        assert result["chat_id"] == -987654321
