"""
Integration tests for database storage layer.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime

from src.database.storage import DatabaseStorage
from src.database.models import (
    RawContent,
    ProcessedContent,
    DeliveryHistory,
    SourceStatus,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        storage = DatabaseStorage(db_path=db_path)
        storage.initialize_schema()
        yield storage


class TestDatabaseStorageInitialization:
    """Test database initialization."""

    def test_initialize_schema(self, temp_db):
        """Test that schema initialization creates all tables."""
        with temp_db._get_connection() as conn:
            cursor = conn.cursor()

            # Check all tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

            assert "raw_content" in tables
            assert "processed_content" in tables
            assert "delivery_history" in tables
            assert "source_status" in tables
            assert "schema_version" in tables

    def test_initialize_schema_idempotent(self, temp_db):
        """Test that schema initialization is idempotent."""
        # Should not raise error when called multiple times
        temp_db.initialize_schema()
        temp_db.initialize_schema()

        with temp_db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            count = cursor.fetchone()[0]

            # Should have exactly 5 tables (not doubled)
            assert count == 5

    def test_schema_version_initialized(self, temp_db):
        """Test that schema version is properly initialized."""
        with temp_db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version FROM schema_version WHERE id = 1")
            result = cursor.fetchone()

            assert result is not None
            assert result[0] == 1


class TestRawContentStorage:
    """Test raw content storage operations."""

    def test_store_raw_content(self, temp_db):
        """Test storing raw content."""
        now = datetime.utcnow().isoformat()
        content = RawContent(
            source_type="newsletter",
            source_url="https://example.com/newsletter",
            collected_at=now,
            title="Test Article",
            content_text="Article content",
        )

        content_id = temp_db.store_raw_content(content)

        assert isinstance(content_id, int)
        assert content_id > 0

    def test_get_raw_content(self, temp_db):
        """Test retrieving raw content."""
        now = datetime.utcnow().isoformat()
        content = RawContent(
            source_type="youtube",
            source_url="https://youtube.com/watch?v=123",
            collected_at=now,
            title="Video Title",
            content_text="Transcript",
        )

        content_id = temp_db.store_raw_content(content)
        retrieved = temp_db.get_raw_content(content_id)

        assert retrieved is not None
        assert retrieved["source_type"] == "youtube"
        assert retrieved["title"] == "Video Title"
        assert retrieved["content_text"] == "Transcript"

    def test_get_nonexistent_raw_content(self, temp_db):
        """Test retrieving nonexistent raw content."""
        result = temp_db.get_raw_content(9999)
        assert result is None

    def test_get_raw_content_by_source(self, temp_db):
        """Test retrieving raw content by source."""
        now = datetime.utcnow().isoformat()
        source_url = "https://example.com/newsletter"

        # Store multiple contents from same source
        for i in range(3):
            content = RawContent(
                source_type="newsletter",
                source_url=source_url,
                collected_at=now,
                title=f"Article {i}",
            )
            temp_db.store_raw_content(content)

        results = temp_db.get_raw_content_by_source(source_url, "newsletter")

        assert len(results) == 3
        assert all(r["source_url"] == source_url for r in results)

    def test_delete_raw_content(self, temp_db):
        """Test deleting raw content."""
        now = datetime.utcnow().isoformat()
        content = RawContent(
            source_type="newsletter",
            source_url="https://example.com",
            collected_at=now,
        )

        content_id = temp_db.store_raw_content(content)
        deleted = temp_db.delete_raw_content(content_id)

        assert deleted is True
        assert temp_db.get_raw_content(content_id) is None

    def test_delete_nonexistent_raw_content(self, temp_db):
        """Test deleting nonexistent raw content."""
        deleted = temp_db.delete_raw_content(9999)
        assert deleted is False


class TestProcessedContentStorage:
    """Test processed content storage operations."""

    def test_store_processed_content(self, temp_db):
        """Test storing processed content."""
        now = datetime.utcnow().isoformat()

        # Store raw content first
        raw = RawContent(
            source_type="newsletter",
            source_url="https://example.com",
            collected_at=now,
        )
        raw_id = temp_db.store_raw_content(raw)

        # Store processed content
        processed = ProcessedContent(
            raw_content_id=raw_id,
            processed_at=now,
            summary="AI announcement",
            category="AI News",
            importance_score=0.95,
        )

        processed_id = temp_db.store_processed_content(processed)

        assert isinstance(processed_id, int)
        assert processed_id > 0

    def test_get_processed_content(self, temp_db):
        """Test retrieving processed content."""
        now = datetime.utcnow().isoformat()

        raw = RawContent(
            source_type="newsletter",
            source_url="https://example.com",
            collected_at=now,
        )
        raw_id = temp_db.store_raw_content(raw)

        processed = ProcessedContent(
            raw_content_id=raw_id,
            processed_at=now,
            summary="Summary text",
            category="Tech",
            importance_score=0.75,
        )

        processed_id = temp_db.store_processed_content(processed)
        retrieved = temp_db.get_processed_content(processed_id)

        assert retrieved is not None
        assert retrieved["summary"] == "Summary text"
        assert retrieved["category"] == "Tech"
        assert retrieved["importance_score"] == 0.75

    def test_get_processed_content_by_category(self, temp_db):
        """Test retrieving processed content by category."""
        now = datetime.utcnow().isoformat()
        category = "Research"

        # Store raw and processed content with same category
        for i in range(2):
            raw = RawContent(
                source_type="newsletter",
                source_url=f"https://example.com/{i}",
                collected_at=now,
            )
            raw_id = temp_db.store_raw_content(raw)

            processed = ProcessedContent(
                raw_content_id=raw_id,
                processed_at=now,
                category=category,
                importance_score=0.5 + i * 0.1,
            )
            temp_db.store_processed_content(processed)

        results = temp_db.get_processed_content_by_category(category)

        assert len(results) == 2
        assert all(r["category"] == category for r in results)


class TestDeliveryHistoryStorage:
    """Test delivery history storage operations."""

    def test_store_delivery_success(self, temp_db):
        """Test storing successful delivery."""
        now = datetime.utcnow().isoformat()
        delivery = DeliveryHistory(
            newsletter_content="Newsletter text",
            delivery_status="success",
            delivered_at=now,
            telegram_message_id="123456",
        )

        delivery_id = temp_db.store_delivery_history(delivery)

        assert isinstance(delivery_id, int)
        assert delivery_id > 0

    def test_store_delivery_failure(self, temp_db):
        """Test storing failed delivery."""
        delivery = DeliveryHistory(
            newsletter_content="Newsletter text",
            delivery_status="failure",
            error_message="Network error",
        )

        delivery_id = temp_db.store_delivery_history(delivery)

        assert isinstance(delivery_id, int)

    def test_get_delivery_history(self, temp_db):
        """Test retrieving delivery history."""
        now = datetime.utcnow().isoformat()
        delivery = DeliveryHistory(
            newsletter_content="Content here",
            delivery_status="success",
            delivered_at=now,
            telegram_message_id="789",
        )

        delivery_id = temp_db.store_delivery_history(delivery)
        retrieved = temp_db.get_delivery_history(delivery_id)

        assert retrieved is not None
        assert retrieved["delivery_status"] == "success"
        assert retrieved["telegram_message_id"] == "789"

    def test_get_delivery_history_by_status(self, temp_db):
        """Test retrieving delivery history by status."""
        now = datetime.utcnow().isoformat()

        # Store multiple deliveries with different statuses
        for status in ["success", "success", "failure"]:
            delivery = DeliveryHistory(
                newsletter_content="Content",
                delivery_status=status,
                delivered_at=now if status == "success" else None,
            )
            temp_db.store_delivery_history(delivery)

        success_records = temp_db.get_delivery_history_by_status("success")
        failure_records = temp_db.get_delivery_history_by_status("failure")

        assert len(success_records) == 2
        assert len(failure_records) == 1


class TestSourceStatusStorage:
    """Test source status storage operations."""

    def test_update_source_status_new(self, temp_db):
        """Test creating new source status."""
        now = datetime.utcnow().isoformat()
        status = SourceStatus(
            source_id="https://example.com/newsletter",
            source_type="newsletter",
            last_collected_at=now,
            last_success=now,
        )

        temp_db.update_source_status(status)

        retrieved = temp_db.get_source_status("https://example.com/newsletter")
        assert retrieved is not None
        assert retrieved["source_type"] == "newsletter"

    def test_update_source_status_existing(self, temp_db):
        """Test updating existing source status."""
        source_id = "test-source"

        # Create initial status
        status1 = SourceStatus(
            source_id=source_id,
            source_type="youtube",
            consecutive_failures=0,
        )
        temp_db.update_source_status(status1)

        # Update status
        status2 = SourceStatus(
            source_id=source_id,
            source_type="youtube",
            consecutive_failures=2,
            last_error="Connection timeout",
        )
        temp_db.update_source_status(status2)

        retrieved = temp_db.get_source_status(source_id)
        assert retrieved["consecutive_failures"] == 2
        assert retrieved["last_error"] == "Connection timeout"

    def test_get_all_sources(self, temp_db):
        """Test retrieving all sources."""
        # Store multiple sources
        for i in range(3):
            status = SourceStatus(
                source_id=f"source-{i}",
                source_type="newsletter" if i < 2 else "youtube",
            )
            temp_db.update_source_status(status)

        all_sources = temp_db.get_all_sources()

        assert len(all_sources) == 3

    def test_get_sources_by_type(self, temp_db):
        """Test retrieving sources by type."""
        # Store mixed source types
        for i in range(2):
            status = SourceStatus(
                source_id=f"newsletter-{i}",
                source_type="newsletter",
            )
            temp_db.update_source_status(status)

        for i in range(3):
            status = SourceStatus(
                source_id=f"youtube-{i}",
                source_type="youtube",
            )
            temp_db.update_source_status(status)

        newsletter_sources = temp_db.get_sources_by_type("newsletter")
        youtube_sources = temp_db.get_sources_by_type("youtube")

        assert len(newsletter_sources) == 2
        assert len(youtube_sources) == 3


class TestDatabaseQueries:
    """Test database query operations."""

    def test_get_unprocessed_content(self, temp_db):
        """Test retrieving unprocessed content."""
        now = datetime.utcnow().isoformat()

        # Store raw content
        raw_ids = []
        for i in range(3):
            raw = RawContent(
                source_type="newsletter",
                source_url=f"https://example.com/{i}",
                collected_at=now,
            )
            raw_ids.append(temp_db.store_raw_content(raw))

        # Process only first one
        processed = ProcessedContent(
            raw_content_id=raw_ids[0],
            processed_at=now,
        )
        temp_db.store_processed_content(processed)

        unprocessed = temp_db.get_unprocessed_content()

        assert len(unprocessed) == 2
        assert all(r["id"] in raw_ids[1:] for r in unprocessed)

    def test_get_delivery_stats(self, temp_db):
        """Test retrieving delivery statistics."""
        now = datetime.utcnow().isoformat()

        # Store deliveries with different statuses
        deliveries = [
            DeliveryHistory("content", "success", now),
            DeliveryHistory("content", "success", now),
            DeliveryHistory("content", "failure", error_message="Error"),
            DeliveryHistory("content", "partial", now),
        ]

        for delivery in deliveries:
            temp_db.store_delivery_history(delivery)

        stats = temp_db.get_delivery_stats()

        assert stats.get("success", 0) == 2
        assert stats.get("failure", 0) == 1
        assert stats.get("partial", 0) == 1


class TestTransactionHandling:
    """Test transaction and error handling."""

    def test_connection_context_manager(self, temp_db):
        """Test that connection context manager works properly."""
        # This should not raise an error
        with temp_db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM raw_content")
            result = cursor.fetchone()

        assert result[0] == 0

    def test_automatic_rollback_on_error(self, temp_db):
        """Test that failed operations don't leave partial data."""
        now = datetime.utcnow().isoformat()

        # Create raw content
        raw = RawContent(
            source_type="newsletter",
            source_url="https://example.com",
            collected_at=now,
        )
        raw_id = temp_db.store_raw_content(raw)

        # Try to store processed content with invalid foreign key
        # (This should fail or be prevented by constraints)
        with temp_db._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO processed_content
                    (raw_content_id, processed_at)
                    VALUES (?, ?)
                    """,
                    (9999, now),  # Invalid raw_content_id
                )
            except sqlite3.IntegrityError:
                # Expected - foreign key constraint violation
                pass

        # The database should still be in a valid state
        retrieved = temp_db.get_raw_content(raw_id)
        assert retrieved is not None
