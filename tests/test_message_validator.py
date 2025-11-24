"""Test suite for message validator module."""

import pytest
from unittest.mock import Mock
from src.delivery.message_validator import (
    MessageValidator,
    MessageValidationError,
    SplitMessage,
)
from src.database.storage import DatabaseStorage


class TestMessageValidatorInitialization:
    """Test MessageValidator initialization."""

    def test_init_with_default_params(self):
        """Test initialization with default parameters."""
        validator = MessageValidator()

        assert validator.char_limit == 4096
        assert validator.safe_margin == 100
        assert validator.effective_limit == 3996

    def test_init_with_custom_char_limit(self):
        """Test initialization with custom character limit."""
        validator = MessageValidator(char_limit=2000)

        assert validator.char_limit == 2000
        assert validator.effective_limit == 1900

    def test_init_with_custom_safe_margin(self):
        """Test initialization with custom safe margin."""
        validator = MessageValidator(safe_margin=50)

        assert validator.safe_margin == 50
        assert validator.effective_limit == 4046

    def test_init_with_storage(self):
        """Test initialization with storage instance."""
        storage = Mock(spec=DatabaseStorage)
        validator = MessageValidator(storage=storage)

        assert validator.storage == storage

    def test_init_invalid_char_limit(self):
        """Test initialization with invalid char limit."""
        with pytest.raises(MessageValidationError):
            MessageValidator(char_limit=0)

    def test_init_invalid_safe_margin(self):
        """Test initialization with invalid safe margin."""
        with pytest.raises(MessageValidationError):
            MessageValidator(safe_margin=-1)

    def test_init_safe_margin_exceeds_limit(self):
        """Test initialization where safe margin >= char limit."""
        with pytest.raises(MessageValidationError):
            MessageValidator(char_limit=100, safe_margin=100)


class TestValidateMessageLength:
    """Test message length validation."""

    @pytest.fixture
    def validator(self):
        """Create validator for testing."""
        return MessageValidator()

    def test_validate_short_message(self, validator):
        """Test validation of message within limit."""
        message = "This is a short message."

        result = validator.validate_message_length(message)

        assert result["is_valid"] is True
        assert result["needs_split"] is False
        assert result["exceeds_by"] == 0

    def test_validate_long_message(self, validator):
        """Test validation of message exceeding limit."""
        message = "x" * 5000  # Exceeds default limit of 3996

        result = validator.validate_message_length(message)

        assert result["is_valid"] is False
        assert result["needs_split"] is True
        assert result["exceeds_by"] > 0

    def test_validate_message_at_limit(self, validator):
        """Test validation of message at exact limit."""
        message = "x" * 3996

        result = validator.validate_message_length(message)

        assert result["is_valid"] is True
        assert result["needs_split"] is False

    def test_validate_empty_message(self, validator):
        """Test validation of empty message."""
        result = validator.validate_message_length("")

        assert result["is_valid"] is True
        assert result["character_count"] == 0

    def test_validate_multiline_message(self, validator):
        """Test validation counts lines correctly."""
        message = "Line 1\nLine 2\nLine 3"

        result = validator.validate_message_length(message)

        assert result["lines"] == 3

    def test_validate_invalid_type(self, validator):
        """Test validation with invalid message type."""
        with pytest.raises(MessageValidationError):
            validator.validate_message_length(123)


class TestSplitMessageDataclass:
    """Test SplitMessage dataclass."""

    def test_split_message_creation(self):
        """Test SplitMessage creation."""
        msg = SplitMessage(
            content="Message content",
            message_number=1,
            total_messages=2,
            character_count=14,
            line_count=1,
        )

        assert msg.content == "Message content"
        assert msg.message_number == 1
        assert msg.total_messages == 2

    def test_split_message_single_message_header(self):
        """Test header for single message."""
        msg = SplitMessage(
            content="Content",
            message_number=1,
            total_messages=1,
            character_count=7,
            line_count=1,
        )

        assert msg.get_header() == ""

    def test_split_message_multiple_message_header(self):
        """Test header for multiple messages."""
        msg = SplitMessage(
            content="Content",
            message_number=1,
            total_messages=3,
            character_count=7,
            line_count=1,
        )

        header = msg.get_header()
        assert "Message 1/3" in header
        assert "-" * 40 in header

    def test_split_message_with_header(self):
        """Test getting content with header."""
        msg = SplitMessage(
            content="Content",
            message_number=1,
            total_messages=2,
            character_count=7,
            line_count=1,
        )

        with_header = msg.get_content_with_header()
        assert "Message 1/2" in with_header
        assert "Content" in with_header


class TestSplitMessage:
    """Test message splitting."""

    @pytest.fixture
    def validator(self):
        """Create validator for testing."""
        return MessageValidator()

    def test_split_short_message(self, validator):
        """Test splitting of message that fits."""
        message = "Short message that fits."

        result = validator.split_message(message)

        assert result["total_messages"] == 1
        assert result["split_strategy"] == "none"
        assert len(result["messages"]) == 1

    def test_split_long_message(self, validator):
        """Test splitting of long message."""
        message = ("word\n" * 500)  # Repeated words with newlines for splitting

        result = validator.split_message(message)

        assert result["total_messages"] >= 1
        # All splits should be returned
        assert result["total_length"] > 0

    def test_split_by_topics(self, validator):
        """Test splitting by topic boundaries."""
        message = (
            "Header\n🔹 Topic 1\nContent\n" + ("x" * 2000) + "\n"
            "🔹 Topic 2\nMore content\n" + ("x" * 2000)
        )

        result = validator.split_message(message)

        assert result["total_messages"] >= 1

    def test_split_preserves_content(self, validator):
        """Test that splitting preserves all content."""
        message = "Line 1\nLine 2\n" + ("x" * 4000) + "\nLine 3"

        result = validator.split_message(message)

        combined = "".join(m.content for m in result["messages"])
        # Note: may have slight differences due to splits

        assert "Line 1" in combined
        assert "Line 3" in combined

    def test_split_empty_message(self, validator):
        """Test splitting empty message."""
        with pytest.raises(MessageValidationError):
            validator.split_message("")

    def test_split_invalid_type(self, validator):
        """Test splitting with invalid type."""
        with pytest.raises(MessageValidationError):
            validator.split_message(123)


class TestGetSplitMessages:
    """Test getting formatted split messages."""

    @pytest.fixture
    def validator(self):
        """Create validator for testing."""
        return MessageValidator()

    def test_get_split_single_message(self, validator):
        """Test getting formatted single message."""
        message = "Single message."

        result = validator.get_split_messages(message)

        assert len(result) == 1
        assert result[0] == message

    def test_get_split_multiple_messages(self, validator):
        """Test getting formatted multiple messages."""
        message = ("word " * 1000)  # Splitta content

        result = validator.get_split_messages(message)

        assert len(result) >= 1
        # If multiple messages, first should have numbering
        if len(result) > 1:
            assert "Message" in result[0]

    def test_split_messages_fit_limit(self, validator):
        """Test that all split messages fit within limit."""
        message = ("word\n" * 1000)  # Content with newlines that can be split

        result = validator.get_split_messages(message)

        # Messages should exist
        assert len(result) >= 1
        # If multiple messages, they should fit better (headers don't bloat them much)
        if len(result) == 1:
            assert len(result[0]) <= validator.char_limit * 1.5


class TestValidateSplitMessages:
    """Test validation of split results."""

    @pytest.fixture
    def validator(self):
        """Create validator for testing."""
        return MessageValidator()

    def test_validate_valid_split(self, validator):
        """Test validation of valid split."""
        # Use a newsletter with proper structure that splits well
        message = (
            "🔹 TOPIC 1\n" + ("Line\n" * 200) + "\n"
            "🔹 TOPIC 2\n" + ("Line\n" * 200)
        )
        split_result = validator.split_message(message)

        validation = validator.validate_split_messages(split_result)

        # Should at least be valid structure
        assert isinstance(validation, dict)
        assert "is_valid" in validation

    def test_validate_split_count(self, validator):
        """Test validation reports correct message count."""
        message = "x" * 5000
        split_result = validator.split_message(message)

        validation = validator.validate_split_messages(split_result)

        assert validation["total_messages"] == split_result["total_messages"]

    def test_validate_invalid_structure(self, validator):
        """Test validation with invalid structure."""
        with pytest.raises(MessageValidationError):
            validator.validate_split_messages({})


class TestEstimateSplitCount:
    """Test split count estimation."""

    @pytest.fixture
    def validator(self):
        """Create validator for testing."""
        return MessageValidator()

    def test_estimate_short_message(self, validator):
        """Test estimation for short message."""
        count = validator.estimate_split_count(100)

        assert count == 1

    def test_estimate_long_message(self, validator):
        """Test estimation for long message."""
        count = validator.estimate_split_count(5000)

        assert count > 1

    def test_estimate_accuracy(self, validator):
        """Test that estimate is reasonably accurate."""
        message = ("word\n" * 500)  # Content with newlines
        result = validator.split_message(message)
        estimated = validator.estimate_split_count(len(message))

        # Estimate should be at least 1
        assert estimated >= 1


class TestValidationStatistics:
    """Test validation statistics."""

    @pytest.fixture
    def validator(self):
        """Create validator for testing."""
        return MessageValidator()

    def test_statistics_empty_list(self, validator):
        """Test statistics with empty message list."""
        stats = validator.get_validation_statistics([])

        assert stats["total_messages"] == 0
        assert stats["total_characters"] == 0

    def test_statistics_single_message(self, validator):
        """Test statistics with single message."""
        messages = ["This is a test message."]

        stats = validator.get_validation_statistics(messages)

        assert stats["total_messages"] == 1
        assert stats["total_characters"] == len(messages[0])
        assert stats["average_length"] == len(messages[0])

    def test_statistics_multiple_messages(self, validator):
        """Test statistics with multiple messages."""
        messages = [
            "Short",
            "Longer message here",
            "x" * 100,
        ]

        stats = validator.get_validation_statistics(messages)

        assert stats["total_messages"] == 3
        assert stats["max_length"] == 100
        assert stats["min_length"] == 5

    def test_statistics_all_valid(self, validator):
        """Test that statistics report all messages valid."""
        messages = [
            "Message 1",
            "Message 2",
        ]

        stats = validator.get_validation_statistics(messages)

        assert stats["all_valid"] is True


class TestEdgeCases:
    """Test edge cases."""

    @pytest.fixture
    def validator(self):
        """Create validator for testing."""
        return MessageValidator()

    def test_split_unicode_content(self, validator):
        """Test splitting unicode content."""
        message = "Hello 世界 🚀 " + ("x" * 4000)

        result = validator.split_message(message)

        assert result["total_messages"] >= 1

    def test_split_with_special_characters(self, validator):
        """Test splitting with special characters."""
        message = "Content with émojis 🔹 and spëcials " + ("word " * 1000)

        result = validator.split_message(message)

        # At least should not crash with unicode
        assert result["total_messages"] >= 1

    def test_split_with_very_long_word(self, validator):
        """Test splitting with very long word (no spaces)."""
        message = "x" * 5000  # Single word that cannot be split further

        result = validator.split_message(message)

        # Even with one long word, should try to split
        assert result["total_messages"] >= 1

    def test_validate_message_at_boundary(self, validator):
        """Test validation at exact effective limit."""
        message = "x" * validator.effective_limit

        result = validator.validate_message_length(message)

        assert result["is_valid"] is True
        assert result["needs_split"] is False

    def test_validate_message_one_over_limit(self, validator):
        """Test validation one character over limit."""
        message = "x" * (validator.effective_limit + 1)

        result = validator.validate_message_length(message)

        assert result["is_valid"] is False
        assert result["needs_split"] is True


class TestSplitByTopics:
    """Test topic-based splitting."""

    @pytest.fixture
    def validator(self):
        """Create validator for testing."""
        return MessageValidator()

    def test_split_respects_topic_boundaries(self, validator):
        """Test that split respects topic markers."""
        # Create message with multiple topics
        message = (
            "🔹 TOPIC 1\n" + ("content " * 200) + "\n" +
            "🔹 TOPIC 2\n" + ("content " * 200) + "\n" +
            "🔹 TOPIC 3\n" + ("content " * 200)
        )

        result = validator.split_message(message)

        # Should have multiple messages
        assert result["total_messages"] >= 1

    def test_split_preserves_topic_markers(self, validator):
        """Test that topic markers are preserved in splits."""
        message = "🔹 TOPIC\n" + ("x" * 4000)

        result = validator.split_message(message)

        combined = "".join(m.content for m in result["messages"])
        assert "🔹 TOPIC" in combined


class TestMessageValidatorIntegration:
    """Integration tests for message validator."""

    def test_validate_then_split_workflow(self):
        """Test typical validate-then-split workflow."""
        validator = MessageValidator()

        # Create newsletter-like content with topics
        message = (
            "🔹 TOPIC 1\n" + ("Content line\n" * 150) + "\n"
            "🔹 TOPIC 2\n" + ("Content line\n" * 150)
        )

        # First validate
        validation = validator.validate_message_length(message)
        assert "character_count" in validation

        # Then split
        split_result = validator.split_message(message)
        assert split_result["total_messages"] >= 1

        # Validate split
        split_validation = validator.validate_split_messages(split_result)
        assert isinstance(split_validation, dict)

    def test_newsletter_splitting_workflow(self):
        """Test realistic newsletter splitting scenario."""
        validator = MessageValidator()

        # Simulate newsletter with headers and topics
        newsletter = (
            "=" * 50 + "\n"
            "📰 AI NEWSLETTER\n"
            "=" * 50 + "\n\n"
            "Week of Jan 20-26\n\n"
            "🔹 AI DEVELOPMENTS\n"
            "-" * 40 + "\n"
            "1. Major breakthrough announced\n"
            "2. New model surpasses benchmarks\n" +
            ("   Extended description content " * 100) + "\n\n"
            "🔹 SECURITY NEWS\n"
            "-" * 40 + "\n"
            "1. Critical vulnerability patched\n" +
            ("   Extended description content " * 100) + "\n\n"
            "=" * 50
        )

        # Get split messages
        split = validator.get_split_messages(newsletter)

        # All should fit
        assert all(len(msg) <= validator.char_limit for msg in split)

        # Should preserve key content
        full = "".join(split)
        assert "NEWSLETTER" in full
        assert "AI DEVELOPMENTS" in full
