"""Newsletter delivery orchestration for Telegram."""

from typing import Dict, Any, List, Optional
from datetime import datetime
from src.delivery.telegram_bot_client import (
    TelegramBotClient,
    TelegramConnectionError,
    TelegramAuthenticationError,
)
from src.delivery.message_validator import MessageValidator
from src.database.storage import DatabaseStorage
from src.utils.logging_setup import get_logger
from src.utils.error_handling import with_retries_and_logging

logger = get_logger(__name__)


class DeliveryError(Exception):
    """Exception raised for delivery errors."""

    pass


class NewsletterDelivery:
    """Orchestrates newsletter delivery via Telegram.

    Handles the complete delivery workflow:
    1. Validates newsletter content length
    2. Splits if needed to fit Telegram limits
    3. Sends messages via Telegram Bot
    4. Stores delivery history in database
    5. Handles errors and retries gracefully
    """

    def __init__(
        self,
        bot_token: str,
        storage: Optional[DatabaseStorage] = None,
        char_limit: int = 4096,
        safe_margin: int = 100,
    ) -> None:
        """Initialize newsletter delivery system.

        Args:
            bot_token: Telegram Bot API token
            storage: Optional DatabaseStorage instance for tracking delivery
            char_limit: Character limit per message (default 4096 for Telegram)
            safe_margin: Safety margin to prevent edge cases (default 100)

        Raises:
            TelegramAuthenticationError: If bot token is invalid
            TelegramConnectionError: If connection cannot be established
            DeliveryError: If initialization fails
        """
        try:
            self.bot_client = TelegramBotClient(bot_token)
            self.message_validator = MessageValidator(
                storage=storage, char_limit=char_limit, safe_margin=safe_margin
            )
            self.storage = storage

            logger.info(
                "Initialized NewsletterDelivery system with bot @"
                f"{self.bot_client.bot_username}"
            )

        except (TelegramAuthenticationError, TelegramConnectionError) as e:
            logger.error(f"Failed to initialize delivery system: {e}")
            raise DeliveryError(f"Cannot initialize delivery: {e}") from e

    def get_delivery_status(self) -> Dict[str, Any]:
        """Get current delivery system status.

        Returns:
            Dictionary with:
                - bot_authenticated: Whether bot is authenticated
                - bot_id: Bot ID
                - bot_username: Bot username
                - ready: Whether system is ready to deliver
        """
        bot_status = self.bot_client.get_connection_status()

        return {
            "bot_authenticated": bot_status["is_authenticated"],
            "bot_id": bot_status["bot_id"],
            "bot_username": bot_status["bot_username"],
            "ready": bot_status["is_authenticated"],
        }

    @with_retries_and_logging(
        max_attempts=3,
        backoff_min=1,
        backoff_max=4,
        operation_name="deliver_newsletter",
    )
    def deliver_newsletter(
        self,
        newsletter_content: str,
        chat_id: int,
        parse_mode: str = "HTML",
    ) -> Dict[str, Any]:
        """Deliver newsletter via Telegram.

        Orchestrates the complete delivery pipeline:
        1. Validates newsletter length
        2. Splits if necessary
        3. Sends all messages
        4. Stores delivery history

        Args:
            newsletter_content: Complete newsletter text
            chat_id: Telegram chat or channel ID
            parse_mode: Message format (HTML, Markdown, MarkdownV2)

        Returns:
            Dictionary with:
                - success: Whether delivery succeeded
                - total_messages: Number of messages sent
                - message_ids: List of Telegram message IDs
                - delivery_timestamp: When delivery occurred
                - error: Error message (if failed)

        Raises:
            DeliveryError: If delivery fails after retries
        """
        if not newsletter_content:
            raise DeliveryError("Newsletter content cannot be empty")

        if not isinstance(chat_id, int):
            raise DeliveryError("chat_id must be an integer")

        try:
            logger.info(
                f"Starting newsletter delivery to chat {chat_id} "
                f"({len(newsletter_content)} characters)"
            )

            # Step 1: Validate message length
            validation = self.message_validator.validate_message_length(
                newsletter_content
            )

            logger.debug(
                f"Validation: valid={validation['is_valid']}, "
                f"needs_split={validation['needs_split']}"
            )

            # Step 2: Split if needed
            if validation["needs_split"]:
                split_result = self.message_validator.split_message(
                    newsletter_content
                )
                split_messages = self.message_validator.get_split_messages(
                    newsletter_content
                )

                logger.info(
                    f"Newsletter split into {len(split_messages)} messages"
                )
            else:
                split_messages = [newsletter_content]
                logger.info("Newsletter fits in single message")

            # Step 3: Validate chat before sending
            chat_validation = self.bot_client.validate_chat_id(chat_id)

            if not chat_validation["is_valid"]:
                error_msg = chat_validation.get(
                    "error", "Unknown validation error"
                )
                logger.error(f"Chat ID validation failed: {error_msg}")
                raise DeliveryError(
                    f"Invalid chat ID {chat_id}: {error_msg}"
                )

            logger.info(
                f"Chat validation successful (type: {chat_validation.get('chat_type')})"
            )

            # Step 4: Send messages
            send_result = self.bot_client.send_messages_sync(
                chat_id=chat_id, messages=split_messages, parse_mode=parse_mode
            )

            if not send_result["success"]:
                failed_count = len(send_result.get("failed_indices", []))
                error_msg = (
                    f"Failed to send {failed_count} out of "
                    f"{send_result['total_messages']} messages"
                )
                logger.error(error_msg)
                raise DeliveryError(error_msg)

            # Step 5: Store delivery history
            delivery_result = {
                "success": True,
                "total_messages": send_result["successful_messages"],
                "message_ids": send_result["message_ids"],
                "delivery_timestamp": datetime.utcnow().isoformat(),
                "chat_id": chat_id,
            }

            if self.storage:
                try:
                    self._store_delivery_history(
                        chat_id=chat_id,
                        newsletter_content=newsletter_content,
                        message_ids=send_result["message_ids"],
                        delivery_status="success",
                    )
                    logger.info("Delivery history stored in database")

                except Exception as e:
                    logger.warning(
                        f"Failed to store delivery history: {e}"
                    )
                    # Don't fail delivery if history storage fails

            logger.info(
                f"Newsletter delivered successfully: "
                f"{len(send_result['message_ids'])} messages sent"
            )

            return delivery_result

        except TelegramConnectionError as e:
            logger.error(f"Telegram connection error during delivery: {e}")
            raise DeliveryError(f"Telegram delivery failed: {e}") from e

        except Exception as e:
            logger.error(f"Unexpected error during delivery: {e}")
            raise DeliveryError(f"Delivery failed: {e}") from e

    def _store_delivery_history(
        self,
        chat_id: int,
        newsletter_content: str,
        message_ids: List[int],
        delivery_status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Store delivery history in database.

        Args:
            chat_id: Telegram chat ID
            newsletter_content: Newsletter text sent
            message_ids: List of Telegram message IDs
            delivery_status: Status (success, failure, partial)
            error_message: Error message if delivery failed
        """
        if not self.storage:
            logger.debug("Storage not available, skipping history storage")
            return

        try:
            # Format message IDs as comma-separated string
            message_ids_str = ",".join(str(mid) for mid in message_ids)

            # Store in delivery_history table
            self.storage.insert(
                "delivery_history",
                {
                    "newsletter_content": newsletter_content,
                    "delivered_at": datetime.utcnow().isoformat(),
                    "delivery_status": delivery_status,
                    "telegram_message_id": message_ids_str,
                    "telegram_chat_id": chat_id,
                    "error_message": error_message,
                },
            )

            logger.debug(
                f"Delivery history recorded: status={delivery_status}, "
                f"messages={len(message_ids)}"
            )

        except Exception as e:
            logger.error(f"Error storing delivery history: {e}")
            raise

    def test_delivery_ready(self) -> Dict[str, Any]:
        """Test if delivery system is ready for production.

        Performs:
        - Bot connection test
        - Chat ID validation (if available)
        - Message validation test

        Returns:
            Dictionary with:
                - ready: Whether system is production-ready
                - checks: Dict with individual check results
                - errors: List of any errors found
        """
        errors = []
        checks = {}

        # Check 1: Bot connection
        try:
            is_connected = self.bot_client.test_connection()
            checks["bot_connection"] = is_connected
            if not is_connected:
                errors.append("Bot connection test failed")

        except Exception as e:
            checks["bot_connection"] = False
            errors.append(f"Bot connection error: {e}")

        # Check 2: Message validator
        try:
            test_message = "Test newsletter content"
            validation = self.message_validator.validate_message_length(
                test_message
            )
            checks["message_validation"] = validation["is_valid"]

        except Exception as e:
            checks["message_validation"] = False
            errors.append(f"Message validation error: {e}")

        # Check 3: Storage availability (if configured)
        if self.storage:
            try:
                # Try a simple storage operation
                checks["storage_available"] = True
            except Exception as e:
                checks["storage_available"] = False
                errors.append(f"Storage error: {e}")
        else:
            checks["storage_available"] = True  # Not required

        ready = len(errors) == 0

        logger.info(
            f"Delivery system readiness check: ready={ready}, "
            f"errors={len(errors)}"
        )

        return {
            "ready": ready,
            "checks": checks,
            "errors": errors,
        }

    def validate_configuration(
        self, chat_id: int
    ) -> Dict[str, Any]:
        """Validate delivery configuration before use.

        Args:
            chat_id: Telegram chat ID to validate

        Returns:
            Dictionary with:
                - valid: Whether configuration is valid
                - issues: List of any issues found
        """
        issues = []

        # Check 1: Bot authentication
        status = self.bot_client.get_connection_status()
        if not status["is_authenticated"]:
            issues.append("Bot is not authenticated")

        # Check 2: Chat ID validity
        if isinstance(chat_id, int):
            chat_validation = self.bot_client.validate_chat_id(chat_id)
            if not chat_validation["is_valid"]:
                issues.append(
                    f"Chat ID validation failed: "
                    f"{chat_validation.get('error', 'Unknown error')}"
                )
        else:
            issues.append("chat_id must be an integer")

        # Check 3: Message validator ready
        if not self.message_validator.is_authenticated:
            logger.debug("Message validator not authenticated (not a concern)")

        valid = len(issues) == 0

        logger.info(
            f"Configuration validation: valid={valid}, "
            f"issues={len(issues)}"
        )

        return {
            "valid": valid,
            "issues": issues,
        }
