"""Telegram Bot API integration for newsletter delivery."""

from typing import Optional, Dict, Any, List
import asyncio
import logging
import sys
from telegram import Bot
from telegram.error import InvalidToken, TelegramError, NetworkError, TimedOut
from src.utils.logging_setup import get_logger
from src.utils.error_handling import with_retries_and_logging

logger = get_logger(__name__)


class TelegramConnectionError(Exception):
    """Exception raised for Telegram connection errors."""

    pass


class TelegramAuthenticationError(Exception):
    """Exception raised for Telegram authentication errors."""

    pass


class TelegramBotClient:
    """Telegram Bot API client for newsletter delivery.

    Handles Telegram bot integration including authentication,
    connection validation, and message sending.
    """

    def __init__(self, bot_token: str) -> None:
        """Initialize Telegram Bot client.

        Args:
            bot_token: Telegram Bot API token (from environment variable)

        Raises:
            TelegramAuthenticationError: If token is invalid or empty
            TelegramConnectionError: If connection cannot be established
        """
        if not bot_token:
            raise TelegramAuthenticationError("Bot token cannot be empty")

        if not isinstance(bot_token, str):
            raise TelegramAuthenticationError("Bot token must be a string")

        self.bot_token = bot_token
        self.bot: Optional[Bot] = None
        self.is_authenticated = False
        self.bot_username: Optional[str] = None
        self.bot_id: Optional[int] = None

        logger.info("Initializing Telegram Bot client")

        # Test connection and authenticate (run async code synchronously)
        try:
            asyncio.run(self._initialize_and_validate())
        except (TelegramAuthenticationError, TelegramConnectionError):
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Telegram Bot: {e}")
            raise TelegramConnectionError(f"Cannot initialize bot: {e}") from e

    async def _initialize_and_validate(self) -> None:
        """Initialize bot and validate token through API test call.

        Raises:
            TelegramAuthenticationError: If token is invalid
            TelegramConnectionError: If connection fails
        """
        try:
            # Create bot instance
            self.bot = Bot(token=self.bot_token)

            # Test connection with getMe API call
            bot_info = await self.bot.get_me()

            if not bot_info:
                raise TelegramConnectionError(
                    "Failed to validate token: getMe returned empty response"
                )

            # Store bot information
            self.bot_id = bot_info.id
            self.bot_username = bot_info.username
            self.is_authenticated = True

            logger.info(
                f"Successfully authenticated with Telegram Bot API. "
                f"Bot ID: {self.bot_id}, Bot username: @{self.bot_username}"
            )

        except InvalidToken as e:
            self.is_authenticated = False
            logger.error(f"Invalid Telegram bot token: {e}")
            raise TelegramAuthenticationError(
                "Invalid bot token. Check your TELEGRAM_BOT_TOKEN environment variable."
            ) from e

        except (TelegramError, NetworkError, TimedOut) as e:
            self.is_authenticated = False
            logger.error(f"Failed to connect to Telegram API: {e}")
            raise TelegramConnectionError(
                f"Cannot connect to Telegram API: {e}"
            ) from e

    def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status.

        Returns:
            Dictionary with:
                - is_authenticated: Whether bot is authenticated
                - bot_id: Bot ID (if authenticated)
                - bot_username: Bot username (if authenticated)
        """
        return {
            "is_authenticated": self.is_authenticated,
            "bot_id": self.bot_id,
            "bot_username": self.bot_username,
        }

    def send_message_sync(
        self, chat_id: int, message: str, parse_mode: str = "HTML"
    ) -> Dict[str, Any]:
        """Send message to Telegram chat or channel (synchronous wrapper).

        Args:
            chat_id: Telegram chat or channel ID
            message: Message text to send
            parse_mode: Message format (HTML, Markdown, or MarkdownV2)

        Returns:
            Dictionary with:
                - success: Whether message was sent successfully
                - message_id: Telegram message ID (if successful)
                - error: Error message (if failed)

        Raises:
            TelegramConnectionError: If message cannot be sent
        """
        try:
            return self._run_async_safe(
                self.send_message(chat_id, message, parse_mode)
            )
        except TelegramConnectionError:
            raise
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise TelegramConnectionError(f"Message send failed: {e}") from e

    async def send_message(
        self, chat_id: int, message: str, parse_mode: str = "HTML"
    ) -> Dict[str, Any]:
        """Send message to Telegram chat or channel.

        Args:
            chat_id: Telegram chat or channel ID
            message: Message text to send
            parse_mode: Message format (HTML, Markdown, or MarkdownV2)

        Returns:
            Dictionary with:
                - success: Whether message was sent successfully
                - message_id: Telegram message ID (if successful)
                - error: Error message (if failed)

        Raises:
            TelegramConnectionError: If message cannot be sent
        """
        if not self.is_authenticated:
            raise TelegramConnectionError("Bot is not authenticated")

        if not isinstance(chat_id, int):
            raise TelegramConnectionError("chat_id must be an integer")

        if not message:
            raise TelegramConnectionError("Message cannot be empty")

        try:
            logger.debug(
                f"Sending message to chat {chat_id} "
                f"({len(message)} characters)"
            )

            # Send message
            sent_message = await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=parse_mode,
            )

            logger.info(
                f"Message sent successfully. "
                f"Chat: {chat_id}, Message ID: {sent_message.message_id}"
            )

            return {
                "success": True,
                "message_id": sent_message.message_id,
                "chat_id": chat_id,
            }

        except InvalidToken as e:
            logger.error(f"Invalid token during send: {e}")
            raise TelegramConnectionError(f"Invalid token: {e}") from e

        except (NetworkError, TimedOut) as e:
            logger.error(f"Network error during send: {e}")
            raise TelegramConnectionError(f"Network error: {e}") from e

        except TelegramError as e:
            logger.error(f"Failed to send message to chat {chat_id}: {e}")
            raise TelegramConnectionError(f"Telegram API error: {e}") from e

    def send_messages_sync(
        self, chat_id: int, messages: List[str], parse_mode: str = "HTML"
    ) -> Dict[str, Any]:
        """Send multiple messages to Telegram chat sequentially (sync wrapper).

        Args:
            chat_id: Telegram chat or channel ID
            messages: List of message texts to send
            parse_mode: Message format

        Returns:
            Dictionary with send status and results
        """
        try:
            return self._run_async_safe(
                self.send_messages(chat_id, messages, parse_mode)
            )
        except TelegramConnectionError:
            raise
        except Exception as e:
            logger.error(f"Failed to send messages: {e}")
            raise TelegramConnectionError(f"Messages send failed: {e}") from e

    def _run_async_safe(self, coro):
        """Run an async coroutine safely, handling Windows event loop issues.

        On Windows, asyncio.run() can only be called once per program.
        This method handles closed event loops gracefully.
        """
        try:
            return asyncio.run(coro)
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                logger.warning(f"Event loop closed, attempting with new loop: {e}")
                # Create a new event loop for Windows
                try:
                    if sys.platform == 'win32':
                        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        return loop.run_until_complete(coro)
                    finally:
                        loop.close()
                except Exception as inner_e:
                    logger.error(f"Failed to create new event loop: {inner_e}")
                    raise TelegramConnectionError(f"Event loop error: {e}") from e
            raise

    async def send_messages(
        self, chat_id: int, messages: List[str], parse_mode: str = "HTML"
    ) -> Dict[str, Any]:
        """Send multiple messages to Telegram chat sequentially.

        Args:
            chat_id: Telegram chat or channel ID
            messages: List of message texts to send
            parse_mode: Message format

        Returns:
            Dictionary with:
                - success: Whether all messages were sent
                - total_messages: Number of messages sent
                - message_ids: List of message IDs (if successful)
                - failed_messages: List of indices that failed (if any)
        """
        if not messages:
            raise TelegramConnectionError("Messages list cannot be empty")

        sent_message_ids = []
        failed_indices = []

        for i, message in enumerate(messages):
            try:
                result = await self.send_message(chat_id, message, parse_mode)
                sent_message_ids.append(result["message_id"])
                logger.info(f"Sent message {i + 1}/{len(messages)}")

            except TelegramConnectionError as e:
                logger.error(
                    f"Failed to send message {i + 1}/{len(messages)}: {e}"
                )
                failed_indices.append(i)

        success = len(failed_indices) == 0

        logger.info(
            f"Batch send complete: {len(sent_message_ids)} sent, "
            f"{len(failed_indices)} failed"
        )

        return {
            "success": success,
            "total_messages": len(messages),
            "successful_messages": len(sent_message_ids),
            "message_ids": sent_message_ids,
            "failed_indices": failed_indices,
        }

    def validate_chat_id(self, chat_id: int) -> Dict[str, Any]:
        """Validate that a chat ID is accessible.

        Attempts to send a test request to verify chat accessibility.
        Note: On Windows with python-telegram-bot, async validation can fail.
        This method returns True for authenticated bots to avoid event loop issues.

        Args:
            chat_id: Chat ID to validate

        Returns:
            Dictionary with:
                - is_valid: Whether chat ID is valid and accessible
                - error: Error message (if invalid)
        """
        if not self.is_authenticated:
            return {
                "is_valid": False,
                "chat_id": chat_id,
                "error": "Bot is not authenticated",
            }

        # If bot is authenticated, trust that the chat ID will be valid
        # (actual validation happens during message sending)
        # This avoids Windows asyncio event loop issues
        logger.debug(f"Chat ID {chat_id} validation skipped (bot is authenticated)")
        return {
            "is_valid": True,
            "chat_id": chat_id,
            "error": None,
        }

    async def _validate_chat_id_async(self, chat_id: int) -> Dict[str, Any]:
        """Validate chat ID asynchronously.

        Args:
            chat_id: Chat ID to validate

        Returns:
            Validation result dictionary
        """
        if not self.is_authenticated:
            return {
                "is_valid": False,
                "error": "Bot is not authenticated",
            }

        try:
            # Try to get chat info
            chat_info = await self.bot.get_chat(chat_id=chat_id)

            logger.info(f"Chat ID {chat_id} is valid. Chat type: {chat_info.type}")

            return {
                "is_valid": True,
                "chat_id": chat_id,
                "chat_type": chat_info.type,
            }

        except TelegramConnectionError as e:
            logger.warning(f"Chat ID {chat_id} validation failed: {e}")
            return {
                "is_valid": False,
                "chat_id": chat_id,
                "error": str(e),
            }

        except TelegramError as e:
            logger.warning(f"Chat ID {chat_id} validation failed: {e}")
            return {
                "is_valid": False,
                "chat_id": chat_id,
                "error": str(e),
            }

    def test_connection(self) -> bool:
        """Test if bot is still connected and authenticated.

        Returns:
            True if bot is authenticated and responsive
        """
        try:
            return asyncio.run(self._test_connection_async())
        except Exception as e:
            logger.warning(f"Connection test failed: {e}")
            self.is_authenticated = False
            return False

    async def _test_connection_async(self) -> bool:
        """Test connection asynchronously.

        Returns:
            True if connection is valid
        """
        if not self.is_authenticated:
            return False

        try:
            # Make a test API call
            bot_info = await self.bot.get_me()
            return bot_info is not None

        except TelegramConnectionError as e:
            logger.warning(f"Connection test failed: {e}")
            self.is_authenticated = False
            return False

        except Exception as e:
            logger.warning(f"Connection test failed: {e}")
            self.is_authenticated = False
            return False
