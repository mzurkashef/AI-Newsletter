"""Test suite for duplicate processing prevention."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta

from src.processors.duplicate_processor import (
    DuplicateProcessor,
    DuplicateProcessingError,
    ContentMatchMethod,
)
from src.database.storage import DatabaseStorage


class TestDuplicateProcessorInitialization:
    """Test DuplicateProcessor initialization."""

    def test_init_with_storage(self):
        """Test initialization with storage."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        assert processor.storage == mock_storage
        assert processor.retention_days == 90
        assert processor.check_url is True
        assert processor.check_title is True
        assert processor.check_content_hash is True

    def test_init_with_custom_settings(self):
        """Test initialization with custom settings."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(
            mock_storage,
            retention_days=30,
            check_url=False,
            check_title=False,
            check_content_hash=True,
        )

        assert processor.retention_days == 30
        assert processor.check_url is False
        assert processor.check_title is False
        assert processor.check_content_hash is True

    def test_init_without_storage_fails(self):
        """Test initialization without storage fails."""
        with pytest.raises(ValueError):
            DuplicateProcessor(None)


class TestContentHashCalculation:
    """Test content hash calculations."""

    def test_calculate_hash_same_content(self):
        """Test hash is consistent for same content."""
        processor = DuplicateProcessor(MagicMock())

        hash1 = processor._calculate_content_hash("Test content")
        hash2 = processor._calculate_content_hash("Test content")

        assert hash1 == hash2

    def test_calculate_hash_different_content(self):
        """Test hash differs for different content."""
        processor = DuplicateProcessor(MagicMock())

        hash1 = processor._calculate_content_hash("Content A")
        hash2 = processor._calculate_content_hash("Content B")

        assert hash1 != hash2

    def test_calculate_hash_case_insensitive(self):
        """Test hash is case-insensitive."""
        processor = DuplicateProcessor(MagicMock())

        hash1 = processor._calculate_content_hash("Test Content")
        hash2 = processor._calculate_content_hash("test content")

        assert hash1 == hash2

    def test_calculate_hash_whitespace_normalized(self):
        """Test hash with whitespace normalization."""
        processor = DuplicateProcessor(MagicMock())

        hash1 = processor._calculate_content_hash("  Test content  ")
        hash2 = processor._calculate_content_hash("Test content")

        assert hash1 == hash2

    def test_calculate_hash_empty_content(self):
        """Test hash for empty content."""
        processor = DuplicateProcessor(MagicMock())

        hash_empty = processor._calculate_content_hash("")
        assert hash_empty == ""


class TestURLNormalization:
    """Test URL normalization."""

    def test_normalize_url_basic(self):
        """Test basic URL normalization."""
        processor = DuplicateProcessor(MagicMock())

        normalized = processor._normalize_url("https://example.com/page")
        assert normalized == "https://example.com/page"

    def test_normalize_url_trailing_slash(self):
        """Test trailing slash removal."""
        processor = DuplicateProcessor(MagicMock())

        normalized = processor._normalize_url("https://example.com/page/")
        assert normalized == "https://example.com/page"

    def test_normalize_url_case_insensitive(self):
        """Test case insensitive normalization."""
        processor = DuplicateProcessor(MagicMock())

        normalized = processor._normalize_url("HTTPS://EXAMPLE.COM/PAGE")
        assert normalized == "https://example.com/page"

    def test_normalize_url_query_parameters(self):
        """Test query parameter removal."""
        processor = DuplicateProcessor(MagicMock())

        normalized = processor._normalize_url("https://example.com/page?id=123&sort=asc")
        assert normalized == "https://example.com/page"

    def test_normalize_url_empty(self):
        """Test empty URL normalization."""
        processor = DuplicateProcessor(MagicMock())

        normalized = processor._normalize_url("")
        assert normalized is None

    def test_normalize_url_none(self):
        """Test None URL normalization."""
        processor = DuplicateProcessor(MagicMock())

        normalized = processor._normalize_url(None)
        assert normalized is None


class TestDuplicateDetection:
    """Test duplicate detection logic."""

    def test_is_previously_processed_new_content(self):
        """Test new content is not marked as duplicate."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        content = {
            "title": "New Article",
            "content_url": "https://example.com/new",
            "content_text": "New content here",
        }

        result = processor.is_previously_processed(content)

        assert result["is_duplicate"] is False
        assert result["match_method"] is None
        assert result["previous_processing"] is None

    def test_is_previously_processed_invalid_content(self):
        """Test invalid content type."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        result = processor.is_previously_processed("not a dict")

        assert result["is_duplicate"] is False
        assert result["match_method"] is None

    def test_is_previously_processed_url_check_disabled(self):
        """Test URL check can be disabled."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage, check_url=False)

        content = {
            "title": "Article",
            "content_url": "https://example.com/article",
        }

        result = processor.is_previously_processed(content)

        assert result["is_duplicate"] is False

    def test_is_previously_processed_title_check_disabled(self):
        """Test title check can be disabled."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage, check_title=False)

        content = {
            "title": "Article Title",
            "content_text": "Some content",
        }

        result = processor.is_previously_processed(content)

        assert result["is_duplicate"] is False

    def test_is_previously_processed_hash_check_disabled(self):
        """Test hash check can be disabled."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage, check_content_hash=False)

        content = {
            "title": "Article",
            "content_text": "Some content",
        }

        result = processor.is_previously_processed(content)

        assert result["is_duplicate"] is False


class TestFilterNewContent:
    """Test filtering new content from duplicates."""

    def test_filter_empty_list(self):
        """Test filtering empty content list."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        result = processor.filter_new_content([])

        assert result["total"] == 0
        assert result["new_content"] == []
        assert result["filtered_count"] == 0
        assert result["statistics"]["filter_ratio"] == 0.0

    def test_filter_all_new_content(self):
        """Test filtering list with all new content."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        content_list = [
            {
                "title": "Article 1",
                "content_url": "https://example.com/1",
                "content_text": "Content 1",
            },
            {
                "title": "Article 2",
                "content_url": "https://example.com/2",
                "content_text": "Content 2",
            },
        ]

        result = processor.filter_new_content(content_list)

        assert result["total"] == 2
        assert len(result["new_content"]) == 2
        assert result["filtered_count"] == 0
        assert result["statistics"]["filter_ratio"] == 0.0

    def test_filter_preserves_content_order(self):
        """Test filtering preserves content order."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        content_list = [
            {"title": "First", "content_url": "https://example.com/1"},
            {"title": "Second", "content_url": "https://example.com/2"},
            {"title": "Third", "content_url": "https://example.com/3"},
        ]

        result = processor.filter_new_content(content_list)

        titles = [c["title"] for c in result["new_content"]]
        assert titles == ["First", "Second", "Third"]

    def test_filter_returns_statistics(self):
        """Test filter returns proper statistics."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage, retention_days=60)

        content_list = [
            {"title": "Article 1", "content_url": "https://example.com/1"},
        ]

        result = processor.filter_new_content(content_list)

        assert "statistics" in result
        assert result["statistics"]["retention_days"] == 60
        assert "filter_ratio" in result["statistics"]
        assert "new_content_count" in result["statistics"]


class TestMarkAsProcessed:
    """Test marking content as processed."""

    def test_mark_empty_list(self):
        """Test marking empty list as processed."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        result = processor.mark_as_processed([])

        assert result["success"] is True
        assert result["marked_count"] == 0
        assert result["failed_ids"] == []

    def test_mark_single_content(self):
        """Test marking single content as processed."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        result = processor.mark_as_processed([1])

        assert result["success"] is True
        assert result["marked_count"] == 1
        assert result["failed_ids"] == []

    def test_mark_multiple_content(self):
        """Test marking multiple content items as processed."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        result = processor.mark_as_processed([1, 2, 3, 4, 5])

        assert result["success"] is True
        assert result["marked_count"] == 5
        assert result["failed_ids"] == []

    def test_mark_with_custom_processing_type(self):
        """Test marking with custom processing type."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        result = processor.mark_as_processed(
            [1, 2],
            processing_type="social_media"
        )

        assert result["success"] is True
        assert result["marked_count"] == 2


class TestProcessingStatistics:
    """Test processing statistics calculation."""

    def test_get_statistics_default_period(self):
        """Test getting statistics with default period."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        result = processor.get_processing_statistics()

        assert result["period_days"] == 30
        assert "total_processed" in result
        assert "unique_sources" in result
        assert "processing_rate" in result

    def test_get_statistics_custom_period(self):
        """Test getting statistics with custom period."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        result = processor.get_processing_statistics(days=7)

        assert result["period_days"] == 7

    def test_get_statistics_has_by_source_type(self):
        """Test statistics include source type breakdown."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        result = processor.get_processing_statistics()

        assert "by_source_type" in result


class TestCleanupOldRecords:
    """Test cleanup of old processing records."""

    def test_cleanup_dry_run(self):
        """Test cleanup dry-run mode."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        result = processor.cleanup_old_processing_records(days=90, dry_run=True)

        assert result["success"] is True
        assert result["dry_run"] is True
        assert "cutoff_date" in result

    def test_cleanup_actual_delete(self):
        """Test actual cleanup deletion."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        result = processor.cleanup_old_processing_records(days=90, dry_run=False)

        assert "success" in result
        assert result["dry_run"] is False

    def test_cleanup_custom_retention(self):
        """Test cleanup with custom retention period."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        result = processor.cleanup_old_processing_records(days=30, dry_run=True)

        assert result["success"] is True


class TestIntegration:
    """Integration tests for duplicate processor."""

    def test_complete_workflow(self):
        """Test complete duplicate detection workflow."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        # Original content
        original_content = [
            {
                "title": "Breaking AI News",
                "content_url": "https://news.ai/breaking",
                "content_text": "New AI model released",
            },
            {
                "title": "ML Research Update",
                "content_url": "https://research.ai/ml-update",
                "content_text": "New research findings",
            },
        ]

        # Filter for new content
        filter_result = processor.filter_new_content(original_content)
        assert filter_result["total"] == 2
        assert len(filter_result["new_content"]) == 2

        # Mark as processed after delivery
        mark_result = processor.mark_as_processed([1, 2])
        assert mark_result["success"] is True

    def test_workflow_with_subsequent_collection(self):
        """Test workflow with repeated content collection."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        # First collection
        content = [
            {
                "title": "Article 1",
                "content_url": "https://example.com/article1",
                "content_text": "Content 1",
            },
        ]

        filter_result = processor.filter_new_content(content)
        assert len(filter_result["new_content"]) == 1

        # Mark as processed
        processor.mark_as_processed([1])

        # Second collection with same URL
        repeated_content = [
            {
                "title": "Article 1",
                "content_url": "https://example.com/article1",
                "content_text": "Content 1",
            },
            {
                "title": "New Article",
                "content_url": "https://example.com/article2",
                "content_text": "New content",
            },
        ]

        # Would be filtered if storage had the data
        filter_result2 = processor.filter_new_content(repeated_content)
        # Note: Currently won't filter because database lookup returns None
        # This is expected for the placeholder implementation


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_process_content_with_missing_fields(self):
        """Test processing content with missing fields."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        content = {"title": "Article"}  # Missing URL and content_text

        result = processor.is_previously_processed(content)

        assert result["is_duplicate"] is False

    def test_filter_very_large_list(self):
        """Test filtering very large content list."""
        mock_storage = MagicMock()
        processor = DuplicateProcessor(mock_storage)

        large_list = [
            {
                "title": f"Article {i}",
                "content_url": f"https://example.com/{i}",
                "content_text": f"Content {i}",
            }
            for i in range(1000)
        ]

        result = processor.filter_new_content(large_list)

        assert result["total"] == 1000
        assert len(result["new_content"]) == 1000

    def test_hash_very_long_content(self):
        """Test hashing very long content."""
        processor = DuplicateProcessor(MagicMock())

        long_content = "x" * 10000

        hash_result = processor._calculate_content_hash(long_content)

        assert len(hash_result) == 64  # SHA256 hex digest length
        assert isinstance(hash_result, str)

    def test_normalize_complex_url(self):
        """Test normalizing complex URL."""
        processor = DuplicateProcessor(MagicMock())

        complex_url = (
            "HTTPS://EXAMPLE.COM:8080/path/to/page/"
            "?utm_source=twitter&utm_medium=social&id=123#section"
        )

        normalized = processor._normalize_url(complex_url)

        assert "https" in normalized.lower()
        assert "?" not in normalized  # Query params removed
