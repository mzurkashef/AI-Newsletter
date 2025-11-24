"""Message length validation and splitting for Telegram delivery."""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from src.database.storage import DatabaseStorage
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)


class MessageValidationError(Exception):
    """Exception raised for message validation errors."""

    pass


@dataclass
class SplitMessage:
    """Represents a split message with metadata."""

    content: str
    message_number: int
    total_messages: int
    character_count: int
    line_count: int
    starts_with_topic: bool = False
    ends_with_topic: bool = False

    def get_header(self) -> str:
        """Get message header with numbering."""
        if self.total_messages == 1:
            return ""
        return f"Message {self.message_number}/{self.total_messages}\n" + "-" * 40 + "\n"

    def get_content_with_header(self) -> str:
        """Get complete message with header."""
        if self.total_messages == 1:
            return self.content
        return self.get_header() + self.content


class MessageValidator:
    """Validate and split messages for Telegram delivery.

    Ensures messages fit within Telegram's 4096 character limit by
    splitting long content intelligently while maintaining topic boundaries
    and proper formatting.
    """

    # Telegram Bot API limit
    TELEGRAM_CHAR_LIMIT = 4096
    # Safety margin to avoid edge cases
    SAFE_LIMIT = TELEGRAM_CHAR_LIMIT - 100

    def __init__(
        self,
        storage: Optional[DatabaseStorage] = None,
        char_limit: int = TELEGRAM_CHAR_LIMIT,
        safe_margin: int = 100,
    ) -> None:
        """Initialize message validator.

        Args:
            storage: Optional DatabaseStorage instance
            char_limit: Character limit per message (default 4096)
            safe_margin: Safety margin to prevent edge cases (default 100)

        Raises:
            MessageValidationError: If parameters are invalid
        """
        if char_limit <= 0:
            raise MessageValidationError("char_limit must be > 0")

        if safe_margin < 0:
            raise MessageValidationError("safe_margin must be >= 0")

        if safe_margin >= char_limit:
            raise MessageValidationError("safe_margin must be < char_limit")

        self.storage = storage
        self.char_limit = char_limit
        self.safe_margin = safe_margin
        self.effective_limit = char_limit - safe_margin

        logger.info(
            f"Initialized MessageValidator with char_limit={char_limit}, "
            f"safe_margin={safe_margin}, effective_limit={self.effective_limit}"
        )

    def validate_message_length(self, message: str) -> Dict[str, Any]:
        """Validate a single message against character limit.

        Args:
            message: Message text to validate

        Returns:
            Dictionary with:
                - is_valid: Whether message fits within limit
                - character_count: Number of characters
                - exceeds_by: Number of characters over limit (0 if valid)
                - lines: Number of lines
                - needs_split: Whether message needs splitting

        Raises:
            MessageValidationError: If message is invalid
        """
        if not isinstance(message, str):
            raise MessageValidationError("Message must be a string")

        char_count = len(message)
        line_count = message.count("\n") + 1

        is_valid = char_count <= self.effective_limit
        exceeds_by = max(0, char_count - self.effective_limit)
        needs_split = char_count > self.effective_limit

        logger.info(
            f"Message validation: chars={char_count}, valid={is_valid}, "
            f"needs_split={needs_split}"
        )

        return {
            "is_valid": is_valid,
            "character_count": char_count,
            "exceeds_by": exceeds_by,
            "lines": line_count,
            "needs_split": needs_split,
        }

    def split_message(self, message: str) -> Dict[str, Any]:
        """Split a message into multiple parts fitting within character limit.

        Attempts to split on topic boundaries (🔹) first, then falls back
        to splitting on section headers or paragraph breaks.

        Args:
            message: Message text to split

        Returns:
            Dictionary with:
                - messages: List of SplitMessage objects
                - total_messages: Number of split messages
                - original_length: Original character count
                - total_length: Total length of split messages
                - split_strategy: How the split was done

        Raises:
            MessageValidationError: If message cannot be split
        """
        if not isinstance(message, str):
            raise MessageValidationError("Message must be a string")

        if not message:
            raise MessageValidationError("Message cannot be empty")

        # Check if splitting is needed
        if len(message) <= self.effective_limit:
            logger.info("Message fits within limit, no split needed")
            return {
                "messages": [
                    SplitMessage(
                        content=message,
                        message_number=1,
                        total_messages=1,
                        character_count=len(message),
                        line_count=message.count("\n") + 1,
                    )
                ],
                "total_messages": 1,
                "original_length": len(message),
                "total_length": len(message),
                "split_strategy": "none",
            }

        # Try splitting by topic boundaries first
        split_messages = self._split_by_topics(message)

        if not split_messages or all(len(m) > self.effective_limit for m in split_messages):
            # Fall back to splitting by sections or paragraph breaks
            split_messages = self._split_by_sections(message)

        if not split_messages or all(len(m) > self.effective_limit for m in split_messages):
            # Fall back to aggressive paragraph splitting
            split_messages = self._split_by_paragraphs(message)

        if not split_messages or all(len(m) > self.effective_limit for m in split_messages):
            # Last resort: split by lines
            split_messages = self._split_by_lines(message)

        # Create SplitMessage objects
        result_messages = []
        strategy = "lines"

        for i, msg in enumerate(split_messages, 1):
            split_msg = SplitMessage(
                content=msg,
                message_number=i,
                total_messages=len(split_messages),
                character_count=len(msg),
                line_count=msg.count("\n") + 1,
                starts_with_topic="🔹" in msg[:20],
                ends_with_topic="🔹" in msg[-20:],
            )
            result_messages.append(split_msg)

        total_length = sum(len(m.content) for m in result_messages)

        logger.info(
            f"Message split: {len(result_messages)} parts, "
            f"strategy={strategy}, original={len(message)}, total={total_length}"
        )

        return {
            "messages": result_messages,
            "total_messages": len(result_messages),
            "original_length": len(message),
            "total_length": total_length,
            "split_strategy": strategy,
        }

    def _split_by_topics(self, message: str) -> List[str]:
        """Split message by topic boundaries (🔹 markers).

        Args:
            message: Message to split

        Returns:
            List of message parts, or empty if no valid split
        """
        if "🔹" not in message:
            return []

        # Split by topic marker
        parts = message.split("🔹")

        # Reconstruct with marker and check sizes
        messages = []
        current_msg = ""

        for i, part in enumerate(parts):
            # Skip empty first part from leading split
            if i == 0 and not part.strip():
                continue

            # Add marker back (except for first part)
            part_with_marker = ("🔹" + part) if i > 0 else part

            # Check if adding this part would exceed limit
            if current_msg and len(current_msg) + len(part_with_marker) > self.effective_limit:
                messages.append(current_msg)
                current_msg = part_with_marker
            else:
                current_msg += part_with_marker

        if current_msg:
            messages.append(current_msg)

        # Validate all messages fit
        if all(len(m) <= self.effective_limit for m in messages):
            return messages

        return []

    def _split_by_sections(self, message: str) -> List[str]:
        """Split by section headers (lines starting with dashes or numbers).

        Args:
            message: Message to split

        Returns:
            List of message parts
        """
        lines = message.split("\n")
        messages = []
        current_msg = ""

        for line in lines:
            # Check if line is a section header
            is_header = (
                line.startswith("-") or line.startswith("=") or
                (len(line) > 0 and line[0].isdigit() and "." in line[:3])
            )

            # Add line to current message or start new one
            test_msg = current_msg + "\n" + line if current_msg else line

            if len(test_msg) > self.effective_limit and current_msg:
                messages.append(current_msg)
                current_msg = line
            else:
                current_msg = test_msg

        if current_msg:
            messages.append(current_msg)

        return messages

    def _split_by_paragraphs(self, message: str) -> List[str]:
        """Split by paragraph boundaries (double newlines).

        Args:
            message: Message to split

        Returns:
            List of message parts
        """
        paragraphs = message.split("\n\n")
        messages = []
        current_msg = ""

        for para in paragraphs:
            separator = "\n\n" if current_msg else ""
            test_msg = current_msg + separator + para

            if len(test_msg) > self.effective_limit and current_msg:
                messages.append(current_msg)
                current_msg = para
            else:
                current_msg = test_msg

        if current_msg:
            messages.append(current_msg)

        return messages

    def _split_by_lines(self, message: str) -> List[str]:
        """Split by individual lines (last resort).

        Args:
            message: Message to split

        Returns:
            List of message parts
        """
        lines = message.split("\n")
        messages = []
        current_msg = ""

        for line in lines:
            separator = "\n" if current_msg else ""
            test_msg = current_msg + separator + line

            if len(test_msg) > self.effective_limit and current_msg:
                messages.append(current_msg)
                current_msg = line
            else:
                current_msg = test_msg

        if current_msg:
            messages.append(current_msg)

        return messages

    def get_split_messages(self, message: str) -> List[str]:
        """Get final split messages ready for sending.

        Includes message numbering headers if multiple messages.

        Args:
            message: Message to split

        Returns:
            List of formatted messages ready for delivery
        """
        result = self.split_message(message)
        split_messages = result["messages"]

        if result["total_messages"] == 1:
            return [message]

        # Add headers with numbering
        final_messages = []
        for split_msg in split_messages:
            final_messages.append(split_msg.get_content_with_header())

        return final_messages

    def validate_split_messages(
        self, split_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate that all split messages fit within limits.

        Args:
            split_result: Result from split_message()

        Returns:
            Dictionary with validation results

        Raises:
            MessageValidationError: If split is invalid
        """
        if "messages" not in split_result:
            raise MessageValidationError("Invalid split result structure")

        messages = split_result["messages"]
        all_valid = True
        issues = []

        for msg in messages:
            if len(msg.content) > self.effective_limit:
                all_valid = False
                issues.append(
                    f"Message {msg.message_number}: "
                    f"{len(msg.content)} chars (limit {self.effective_limit})"
                )

        logger.info(
            f"Split validation: all_valid={all_valid}, issues={len(issues)}"
        )

        return {
            "is_valid": all_valid,
            "total_messages": len(messages),
            "issues": issues,
            "max_message_size": max(len(m.content) for m in messages),
        }

    def estimate_split_count(self, message_length: int) -> int:
        """Estimate number of messages needed for given length.

        Args:
            message_length: Length of message in characters

        Returns:
            Estimated number of split messages needed
        """
        if message_length <= self.effective_limit:
            return 1

        # Rough estimate (actual may vary based on split points)
        # Account for header overhead (Message X/Y format ~20 chars per message)
        header_overhead = 40
        effective_with_overhead = self.effective_limit - header_overhead

        estimated = (message_length + effective_with_overhead - 1) // effective_with_overhead

        return max(1, estimated)

    def get_validation_statistics(
        self, messages: List[str]
    ) -> Dict[str, Any]:
        """Calculate statistics about message set.

        Args:
            messages: List of message strings

        Returns:
            Dictionary with statistics
        """
        if not messages:
            return {
                "total_messages": 0,
                "total_characters": 0,
                "average_length": 0.0,
                "max_length": 0,
                "min_length": 0,
                "all_valid": True,
            }

        char_counts = [len(m) for m in messages]

        return {
            "total_messages": len(messages),
            "total_characters": sum(char_counts),
            "average_length": sum(char_counts) / len(char_counts),
            "max_length": max(char_counts),
            "min_length": min(char_counts),
            "all_valid": all(c <= self.effective_limit for c in char_counts),
        }
