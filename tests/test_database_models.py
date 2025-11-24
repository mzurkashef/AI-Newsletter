"""
Unit tests for database models.
"""

import pytest
from datetime import datetime
from src.database.models import (
    RawContent,
    ProcessedContent,
    DeliveryHistory,
    SourceStatus,
    DatabaseSchema,
    SCHEMA_VERSION,
)


class TestRawContent:
    """Test RawContent model."""

    def test_raw_content_creation_minimal(self):
        """Test creating RawContent with minimal required fields."""
        now = datetime.utcnow().isoformat()
        content = RawContent(
            source_type="newsletter",
            source_url="https://example.com/newsletter",
            collected_at=now,
        )

        assert content.source_type == "newsletter"
        assert content.source_url == "https://example.com/newsletter"
        assert content.collected_at == now
        assert content.content_text is None
        assert content.title is None

    def test_raw_content_creation_full(self):
        """Test creating RawContent with all fields."""
        now = datetime.utcnow().isoformat()
        content = RawContent(
            source_type="youtube",
            source_url="https://youtube.com/watch?v=123",
            collected_at=now,
            content_text="Transcript text",
            content_url="https://youtube.com/watch?v=123",
            title="Video Title",
            published_at=now,
            metadata='{"duration": 600}',
        )

        assert content.source_type == "youtube"
        assert content.content_text == "Transcript text"
        assert content.title == "Video Title"
        assert content.metadata == '{"duration": 600}'

    def test_raw_content_to_dict(self):
        """Test converting RawContent to dictionary."""
        now = datetime.utcnow().isoformat()
        content = RawContent(
            source_type="newsletter",
            source_url="https://example.com",
            collected_at=now,
            title="Test Article",
        )

        result = content.to_dict()
        assert isinstance(result, dict)
        assert result["source_type"] == "newsletter"
        assert result["source_url"] == "https://example.com"
        assert result["collected_at"] == now
        assert result["title"] == "Test Article"


class TestProcessedContent:
    """Test ProcessedContent model."""

    def test_processed_content_creation_minimal(self):
        """Test creating ProcessedContent with minimal fields."""
        now = datetime.utcnow().isoformat()
        content = ProcessedContent(
            raw_content_id=1,
            processed_at=now,
        )

        assert content.raw_content_id == 1
        assert content.processed_at == now
        assert content.summary is None
        assert content.category is None
        assert content.importance_score is None

    def test_processed_content_creation_full(self):
        """Test creating ProcessedContent with all fields."""
        now = datetime.utcnow().isoformat()
        content = ProcessedContent(
            raw_content_id=1,
            processed_at=now,
            summary="AI announcement: New model released",
            category="AI Announcements",
            importance_score=0.95,
        )

        assert content.raw_content_id == 1
        assert content.summary == "AI announcement: New model released"
        assert content.category == "AI Announcements"
        assert content.importance_score == 0.95

    def test_processed_content_to_dict(self):
        """Test converting ProcessedContent to dictionary."""
        now = datetime.utcnow().isoformat()
        content = ProcessedContent(
            raw_content_id=42,
            processed_at=now,
            category="Research",
            importance_score=0.75,
        )

        result = content.to_dict()
        assert result["raw_content_id"] == 42
        assert result["category"] == "Research"
        assert result["importance_score"] == 0.75


class TestDeliveryHistory:
    """Test DeliveryHistory model."""

    def test_delivery_history_success(self):
        """Test creating successful delivery record."""
        now = datetime.utcnow().isoformat()
        delivery = DeliveryHistory(
            newsletter_content="Newsletter content here",
            delivery_status="success",
            delivered_at=now,
            telegram_message_id="123456",
        )

        assert delivery.newsletter_content == "Newsletter content here"
        assert delivery.delivery_status == "success"
        assert delivery.delivered_at == now
        assert delivery.telegram_message_id == "123456"
        assert delivery.error_message is None

    def test_delivery_history_failure(self):
        """Test creating failed delivery record."""
        now = datetime.utcnow().isoformat()
        delivery = DeliveryHistory(
            newsletter_content="Newsletter content",
            delivery_status="failure",
            error_message="Network timeout",
        )

        assert delivery.delivery_status == "failure"
        assert delivery.error_message == "Network timeout"
        assert delivery.delivered_at is None

    def test_delivery_history_to_dict(self):
        """Test converting DeliveryHistory to dictionary."""
        now = datetime.utcnow().isoformat()
        delivery = DeliveryHistory(
            newsletter_content="Content",
            delivery_status="partial",
            delivered_at=now,
            telegram_message_id="123",
            error_message="Some recipients failed",
        )

        result = delivery.to_dict()
        assert result["delivery_status"] == "partial"
        assert result["telegram_message_id"] == "123"
        assert result["error_message"] == "Some recipients failed"


class TestSourceStatus:
    """Test SourceStatus model."""

    def test_source_status_creation_minimal(self):
        """Test creating SourceStatus with minimal fields."""
        status = SourceStatus(
            source_id="https://example.com/newsletter",
            source_type="newsletter",
        )

        assert status.source_id == "https://example.com/newsletter"
        assert status.source_type == "newsletter"
        assert status.consecutive_failures == 0

    def test_source_status_creation_full(self):
        """Test creating SourceStatus with all fields."""
        now = datetime.utcnow().isoformat()
        status = SourceStatus(
            source_id="UCxyz123",
            source_type="youtube",
            last_collected_at=now,
            last_success=now,
            last_error=None,
            consecutive_failures=0,
        )

        assert status.source_id == "UCxyz123"
        assert status.source_type == "youtube"
        assert status.last_collected_at == now
        assert status.consecutive_failures == 0

    def test_source_status_with_errors(self):
        """Test source status tracking failures."""
        error_time = datetime.utcnow().isoformat()
        status = SourceStatus(
            source_id="https://example.com",
            source_type="newsletter",
            last_error="Connection refused",
            consecutive_failures=3,
        )

        assert status.consecutive_failures == 3
        assert status.last_error == "Connection refused"

    def test_source_status_to_dict(self):
        """Test converting SourceStatus to dictionary."""
        now = datetime.utcnow().isoformat()
        status = SourceStatus(
            source_id="test-source",
            source_type="newsletter",
            last_collected_at=now,
            consecutive_failures=1,
        )

        result = status.to_dict()
        assert result["source_id"] == "test-source"
        assert result["consecutive_failures"] == 1


class TestDatabaseSchema:
    """Test DatabaseSchema class."""

    def test_schema_version(self):
        """Test schema version constant."""
        assert SCHEMA_VERSION == 1

    def test_table_creation_statements(self):
        """Test that all table creation statements are available."""
        statements = DatabaseSchema.get_all_create_statements()

        assert len(statements) == 5
        assert any("raw_content" in s for s in statements)
        assert any("processed_content" in s for s in statements)
        assert any("delivery_history" in s for s in statements)
        assert any("source_status" in s for s in statements)
        assert any("schema_version" in s for s in statements)

    def test_index_creation_statements(self):
        """Test that all index creation statements are available."""
        indexes = DatabaseSchema.get_all_index_statements()

        assert len(indexes) == 10
        assert all("CREATE INDEX" in idx for idx in indexes)

    def test_schema_constraints(self):
        """Test that schema includes proper constraints."""
        # Check for CHECK constraints in raw_content
        assert "CHECK(source_type IN ('newsletter', 'youtube'))" in DatabaseSchema.CREATE_RAW_CONTENT_TABLE

        # Check for CHECK constraints in processed_content
        assert "CHECK(importance_score >= 0.0 AND importance_score <= 1.0)" in DatabaseSchema.CREATE_PROCESSED_CONTENT_TABLE

        # Check for foreign key constraint
        assert "FOREIGN KEY" in DatabaseSchema.CREATE_PROCESSED_CONTENT_TABLE

    def test_schema_indexes(self):
        """Test that indexes are created for key fields."""
        indexes = DatabaseSchema.get_all_index_statements()

        index_text = " ".join(indexes)
        assert "collected_at" in index_text
        assert "processed_at" in index_text
        assert "category" in index_text
        assert "source_type" in index_text
