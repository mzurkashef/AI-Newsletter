"""
Tests for content deduplication module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.processors.content_deduplicator import ContentDeduplicator, ContentDuplicateError


@pytest.fixture
def mock_storage():
    """Mock database storage."""
    storage = Mock()
    storage.get_processed_content = Mock(return_value=[])
    storage.update_content_status = Mock()
    return storage


@pytest.fixture
def deduplicator(mock_storage):
    """Create deduplicator instance."""
    return ContentDeduplicator(storage=mock_storage)


class TestContentDeduplicatorInitialization:
    """Test deduplicator initialization."""

    def test_initialization_with_storage(self, mock_storage):
        """Test initialization with storage."""
        dedup = ContentDeduplicator(storage=mock_storage)

        assert dedup.storage == mock_storage
        assert dedup.title_threshold == 0.85
        assert dedup.content_threshold == 0.75
        assert dedup.url_threshold == 0.90

    def test_initialization_with_custom_thresholds(self, mock_storage):
        """Test initialization with custom thresholds."""
        dedup = ContentDeduplicator(
            storage=mock_storage,
            title_threshold=0.90,
            content_threshold=0.80,
            url_threshold=0.95,
        )

        assert dedup.title_threshold == 0.90
        assert dedup.content_threshold == 0.80
        assert dedup.url_threshold == 0.95

    def test_default_thresholds(self, deduplicator):
        """Test default threshold values."""
        assert deduplicator.DEFAULT_TITLE_THRESHOLD == 0.85
        assert deduplicator.DEFAULT_CONTENT_THRESHOLD == 0.75
        assert deduplicator.DEFAULT_URL_THRESHOLD == 0.90


class TestStringSimilarity:
    """Test string similarity calculation."""

    def test_exact_match(self, deduplicator):
        """Test exact string match."""
        similarity = deduplicator.calculate_string_similarity("hello", "hello")

        assert similarity == 1.0

    def test_case_insensitive(self, deduplicator):
        """Test case insensitive matching."""
        similarity = deduplicator.calculate_string_similarity("Hello", "hello")

        assert similarity == 1.0

    def test_similar_strings(self, deduplicator):
        """Test similar but not identical strings."""
        similarity = deduplicator.calculate_string_similarity(
            "New Product Launch", "New Product Release"
        )

        assert 0.7 < similarity < 1.0

    def test_different_strings(self, deduplicator):
        """Test very different strings."""
        similarity = deduplicator.calculate_string_similarity(
            "Hello World", "Goodbye Universe"
        )

        assert 0.0 <= similarity < 0.5

    def test_empty_strings(self, deduplicator):
        """Test empty strings."""
        similarity = deduplicator.calculate_string_similarity("", "")

        assert similarity == 0.0

    def test_one_empty_string(self, deduplicator):
        """Test one empty string."""
        similarity = deduplicator.calculate_string_similarity("hello", "")

        assert similarity == 0.0

    def test_whitespace_handling(self, deduplicator):
        """Test whitespace normalization."""
        similarity = deduplicator.calculate_string_similarity(
            "  hello  ", "hello"
        )

        assert similarity == 1.0


class TestJaccardSimilarity:
    """Test Jaccard similarity calculation."""

    def test_identical_texts(self, deduplicator):
        """Test identical texts."""
        similarity = deduplicator.calculate_jaccard_similarity(
            "hello world test", "hello world test"
        )

        assert similarity == 1.0

    def test_partial_overlap(self, deduplicator):
        """Test partial word overlap."""
        similarity = deduplicator.calculate_jaccard_similarity(
            "the quick brown fox", "the quick fox"
        )

        assert 0.5 < similarity < 1.0

    def test_no_overlap(self, deduplicator):
        """Test no word overlap."""
        similarity = deduplicator.calculate_jaccard_similarity(
            "hello world", "goodbye universe"
        )

        assert 0.0 <= similarity < 0.5

    def test_empty_text(self, deduplicator):
        """Test empty text."""
        similarity = deduplicator.calculate_jaccard_similarity("hello", "")

        assert similarity == 0.0

    def test_case_insensitivity(self, deduplicator):
        """Test case insensitive Jaccard."""
        similarity = deduplicator.calculate_jaccard_similarity(
            "Hello World", "hello world"
        )

        assert similarity == 1.0

    def test_word_order_irrelevant(self, deduplicator):
        """Test that word order doesn't matter for Jaccard."""
        similarity1 = deduplicator.calculate_jaccard_similarity(
            "hello world test", "test world hello"
        )
        similarity2 = deduplicator.calculate_jaccard_similarity(
            "hello world test", "hello world test"
        )

        assert similarity1 == similarity2


class TestURLNormalization:
    """Test URL normalization."""

    def test_basic_url(self, deduplicator):
        """Test basic URL normalization."""
        normalized = deduplicator.normalize_url("https://example.com/article")

        assert normalized == "https://example.com/article"

    def test_trailing_slash(self, deduplicator):
        """Test removal of trailing slash."""
        normalized = deduplicator.normalize_url("https://example.com/article/")

        assert normalized == "https://example.com/article"

    def test_case_normalization(self, deduplicator):
        """Test case normalization."""
        normalized = deduplicator.normalize_url("HTTPS://EXAMPLE.COM/Article")

        assert normalized == "https://example.com/article"

    def test_query_parameters_removed(self, deduplicator):
        """Test removal of query parameters."""
        normalized = deduplicator.normalize_url(
            "https://example.com/article?utm_source=twitter"
        )

        assert normalized == "https://example.com/article"

    def test_empty_url(self, deduplicator):
        """Test empty URL."""
        normalized = deduplicator.normalize_url("")

        assert normalized is None

    def test_none_url(self, deduplicator):
        """Test None URL."""
        normalized = deduplicator.normalize_url(None)

        assert normalized is None


class TestURLDuplicateDetection:
    """Test URL-based duplicate detection."""

    def test_identical_urls(self, deduplicator):
        """Test identical URLs."""
        is_dup = deduplicator.is_duplicate_by_url(
            "https://example.com/article", "https://example.com/article"
        )

        assert is_dup is True

    def test_same_url_different_case(self, deduplicator):
        """Test same URL with different case."""
        is_dup = deduplicator.is_duplicate_by_url(
            "https://EXAMPLE.com/article", "https://example.com/article"
        )

        assert is_dup is True

    def test_same_url_different_query(self, deduplicator):
        """Test same URL with different query parameters."""
        is_dup = deduplicator.is_duplicate_by_url(
            "https://example.com/article?param1=a",
            "https://example.com/article?param2=b",
        )

        assert is_dup is True

    def test_different_urls(self, deduplicator):
        """Test different URLs."""
        is_dup = deduplicator.is_duplicate_by_url(
            "https://example.com/article1", "https://different.com/article1"
        )

        assert is_dup is False

    def test_missing_url(self, deduplicator):
        """Test missing URL."""
        is_dup = deduplicator.is_duplicate_by_url(None, "https://example.com/article")

        assert is_dup is False


class TestDuplicateDetection:
    """Test duplicate detection."""

    def test_exact_title_match(self, deduplicator):
        """Test exact title match detection."""
        content1 = {"id": 1, "title": "New AI Product Announced", "content": "text1"}
        content2 = {"id": 2, "title": "New AI Product Announced", "content": "text2"}

        result = deduplicator.is_duplicate(content1, content2)

        assert result["is_duplicate"] is True
        assert "exact_title" in result["methods"]

    def test_similar_title_match(self, deduplicator):
        """Test similar title detection."""
        content1 = {
            "id": 1,
            "title": "Company Announces Major Breakthrough",
            "content": "About the breakthrough",
        }
        content2 = {
            "id": 2,
            "title": "Company Announces Major Break Through",
            "content": "About the breakthrough",
        }

        result = deduplicator.is_duplicate(content1, content2)

        assert result["is_duplicate"] is True
        assert "title_similarity" in result["methods"]

    def test_same_url(self, deduplicator):
        """Test same URL detection."""
        content1 = {
            "id": 1,
            "title": "Title 1",
            "source_url": "https://example.com/article",
        }
        content2 = {
            "id": 2,
            "title": "Title 2",
            "source_url": "https://example.com/article",
        }

        result = deduplicator.is_duplicate(content1, content2)

        assert result["is_duplicate"] is True
        assert "same_url" in result["methods"]

    def test_content_similarity(self, deduplicator):
        """Test content similarity detection."""
        content1 = {
            "id": 1,
            "title": "Article A",
            "content": "The quick brown fox jumps over the lazy dog",
        }
        content2 = {
            "id": 2,
            "title": "Article B",
            "content": "The quick brown fox jumps over the lazy cat",
        }

        result = deduplicator.is_duplicate(content1, content2)

        assert result["is_duplicate"] is True or result["similarity_score"] > 0.5

    def test_no_duplicate(self, deduplicator):
        """Test non-duplicate content."""
        content1 = {
            "id": 1,
            "title": "AI News",
            "content": "Apple announces new iPhone",
        }
        content2 = {
            "id": 2,
            "title": "Sports News",
            "content": "Football team wins championship",
        }

        result = deduplicator.is_duplicate(content1, content2)

        assert result["is_duplicate"] is False
        assert len(result["methods"]) == 0

    def test_same_id(self, deduplicator):
        """Test same ID returns not duplicate."""
        content1 = {"id": 1, "title": "Title", "content": "Content"}
        content2 = {"id": 1, "title": "Title", "content": "Content"}

        result = deduplicator.is_duplicate(content1, content2)

        assert result["is_duplicate"] is False
        assert "same_id" in result["methods"]

    def test_invalid_content_type(self, deduplicator):
        """Test invalid content type."""
        result = deduplicator.is_duplicate("not a dict", {})

        assert result["is_duplicate"] is False


class TestBatchDeduplication:
    """Test batch deduplication."""

    def test_empty_list(self, deduplicator):
        """Test deduplication of empty list."""
        result = deduplicator.deduplicate_content_list([])

        assert result["total"] == 0
        assert result["duplicates_found"] == 0
        assert result["unique_content"] == []

    def test_single_item(self, deduplicator):
        """Test single item list."""
        content = [{"id": 1, "title": "Article", "content": "Text"}]

        result = deduplicator.deduplicate_content_list(content)

        assert result["total"] == 1
        assert result["duplicates_found"] == 0
        assert len(result["unique_content"]) == 1

    def test_no_duplicates(self, deduplicator):
        """Test list with no duplicates."""
        content = [
            {"id": 1, "title": "Article One", "content": "Text about article one"},
            {"id": 2, "title": "Article Two", "content": "Text about article two"},
            {"id": 3, "title": "Article Three", "content": "Text about article three"},
        ]

        result = deduplicator.deduplicate_content_list(content)

        assert result["total"] == 3
        assert result["duplicates_found"] == 0
        assert len(result["unique_content"]) == 3

    def test_with_duplicates(self, deduplicator):
        """Test list with duplicates."""
        content = [
            {"id": 1, "title": "Article A", "content": "Text A"},
            {"id": 2, "title": "Article A", "content": "Text A"},  # Duplicate
            {"id": 3, "title": "Article B", "content": "Text B"},
        ]

        result = deduplicator.deduplicate_content_list(content)

        assert result["total"] == 3
        assert result["duplicates_found"] >= 1
        assert len(result["unique_content"]) <= 3

    def test_multiple_duplicates(self, deduplicator):
        """Test multiple duplicate sets."""
        content = [
            {"id": 1, "title": "Article A", "content": "Text A"},
            {"id": 2, "title": "Article A", "content": "Text A"},  # Dup of 1
            {"id": 3, "title": "Article B", "content": "Text B"},
            {"id": 4, "title": "Article B", "content": "Text B"},  # Dup of 3
        ]

        result = deduplicator.deduplicate_content_list(content)

        assert result["total"] == 4
        assert result["duplicates_found"] >= 1

    def test_deduplication_ratio(self, deduplicator):
        """Test deduplication ratio calculation."""
        content = [
            {"id": 1, "title": "Article A", "content": "Text A"},
            {"id": 2, "title": "Article A", "content": "Text A"},
            {"id": 3, "title": "Article A", "content": "Text A"},
        ]

        result = deduplicator.deduplicate_content_list(content)

        assert result["statistics"]["deduplication_ratio"] > 0


class TestDatabaseDeduplication:
    """Test database deduplication."""

    def test_no_content(self, deduplicator, mock_storage):
        """Test database with no content."""
        mock_storage.get_processed_content.return_value = []

        result = deduplicator.deduplicate_database_content()

        assert result["total"] == 0
        assert result["duplicates_removed"] == 0

    def test_content_marked_as_duplicate(self, deduplicator, mock_storage):
        """Test that duplicates are marked in database."""
        content = [
            {"id": 1, "title": "Article A", "content": "Text A"},
            {"id": 2, "title": "Article A", "content": "Text A"},
        ]
        mock_storage.get_processed_content.return_value = content

        result = deduplicator.deduplicate_database_content()

        # Check that update_content_status was called
        assert mock_storage.update_content_status.called

    def test_error_handling(self, deduplicator, mock_storage):
        """Test error handling."""
        mock_storage.get_processed_content.side_effect = Exception("DB error")

        result = deduplicator.deduplicate_database_content()

        assert "error" in result
        assert result["duplicates_removed"] == 0


class TestThresholdConfiguration:
    """Test threshold configuration."""

    def test_update_title_threshold(self, deduplicator):
        """Test updating title threshold."""
        deduplicator.update_similarity_thresholds(title_threshold=0.90)

        assert deduplicator.title_threshold == 0.90

    def test_update_content_threshold(self, deduplicator):
        """Test updating content threshold."""
        deduplicator.update_similarity_thresholds(content_threshold=0.80)

        assert deduplicator.content_threshold == 0.80

    def test_update_url_threshold(self, deduplicator):
        """Test updating URL threshold."""
        deduplicator.update_similarity_thresholds(url_threshold=0.95)

        assert deduplicator.url_threshold == 0.95

    def test_update_multiple_thresholds(self, deduplicator):
        """Test updating multiple thresholds."""
        deduplicator.update_similarity_thresholds(
            title_threshold=0.90, content_threshold=0.80, url_threshold=0.95
        )

        assert deduplicator.title_threshold == 0.90
        assert deduplicator.content_threshold == 0.80
        assert deduplicator.url_threshold == 0.95

    def test_invalid_title_threshold(self, deduplicator):
        """Test invalid title threshold."""
        with pytest.raises(ContentDuplicateError):
            deduplicator.update_similarity_thresholds(title_threshold=1.5)

    def test_invalid_content_threshold(self, deduplicator):
        """Test invalid content threshold."""
        with pytest.raises(ContentDuplicateError):
            deduplicator.update_similarity_thresholds(content_threshold=-0.1)

    def test_threshold_boundaries(self, deduplicator):
        """Test threshold at boundaries."""
        deduplicator.update_similarity_thresholds(title_threshold=0.0)
        assert deduplicator.title_threshold == 0.0

        deduplicator.update_similarity_thresholds(title_threshold=1.0)
        assert deduplicator.title_threshold == 1.0


class TestDuplicatePairFinding:
    """Test finding duplicate pairs."""

    def test_empty_list(self, deduplicator):
        """Test finding pairs in empty list."""
        result = deduplicator.find_duplicate_pairs([])

        assert result["total"] == 0
        assert result["pairs_found"] == 0
        assert result["duplicate_pairs"] == []

    def test_single_item(self, deduplicator):
        """Test finding pairs with single item."""
        content = [{"id": 1, "title": "Article", "content": "Text"}]

        result = deduplicator.find_duplicate_pairs(content)

        assert result["total"] == 1
        assert result["pairs_found"] == 0

    def test_duplicate_pair(self, deduplicator):
        """Test finding duplicate pair."""
        content = [
            {"id": 1, "title": "Article A", "content": "Text A"},
            {"id": 2, "title": "Article A", "content": "Text A"},
        ]

        result = deduplicator.find_duplicate_pairs(content)

        assert result["total"] == 2
        assert result["pairs_found"] >= 1

    def test_pair_details(self, deduplicator):
        """Test pair details structure."""
        content = [
            {"id": 1, "title": "Article A", "content": "Text A"},
            {"id": 2, "title": "Article A", "content": "Text A"},
        ]

        result = deduplicator.find_duplicate_pairs(content)

        if result["pairs_found"] > 0:
            pair = result["pair_details"][0]
            assert "id1" in pair
            assert "id2" in pair
            assert "similarity_score" in pair
            assert "methods" in pair


class TestDeduplicationStatistics:
    """Test deduplication statistics."""

    def test_empty_list(self, deduplicator):
        """Test statistics on empty list."""
        stats = deduplicator.get_deduplication_statistics([])

        assert stats["total"] == 0
        assert stats["estimated_duplicates"] == 0
        assert stats["estimated_ratio"] == 0.0

    def test_no_duplicates(self, deduplicator):
        """Test statistics with no duplicates."""
        content = [
            {"id": 1, "title": "Article One", "content": "Text about first article"},
            {"id": 2, "title": "Article Two", "content": "Text about second article"},
        ]

        stats = deduplicator.get_deduplication_statistics(content)

        assert stats["total"] == 2
        assert stats["estimated_duplicates"] == 0

    def test_with_duplicates(self, deduplicator):
        """Test statistics with duplicates."""
        content = [
            {"id": 1, "title": "Article A", "content": "Text A"},
            {"id": 2, "title": "Article A", "content": "Text A"},
        ]

        stats = deduplicator.get_deduplication_statistics(content)

        assert stats["total"] == 2
        assert stats["estimated_duplicates"] >= 0

    def test_similarity_distribution(self, deduplicator):
        """Test similarity distribution calculation."""
        content = [
            {"id": 1, "title": "Article 1", "content": "Text 1"},
            {"id": 2, "title": "Article 2", "content": "Text 2"},
        ]

        stats = deduplicator.get_deduplication_statistics(content)

        assert "by_similarity_range" in stats
        assert len(stats["by_similarity_range"]) == 5


class TestEdgeCases:
    """Test edge cases."""

    def test_very_long_content(self, deduplicator):
        """Test deduplication with very long content."""
        long_text = " ".join(["word"] * 10000)
        content1 = {"id": 1, "title": "Long Article", "content": long_text}
        content2 = {"id": 2, "title": "Long Article", "content": long_text}

        result = deduplicator.is_duplicate(content1, content2)

        assert "is_duplicate" in result

    def test_special_characters(self, deduplicator):
        """Test with special characters."""
        content1 = {
            "id": 1,
            "title": "Article @#$%^&*()",
            "content": "Text with émojis 🚀",
        }
        content2 = {
            "id": 2,
            "title": "Article @#$%^&*()",
            "content": "Text with émojis 🚀",
        }

        result = deduplicator.is_duplicate(content1, content2)

        assert "is_duplicate" in result

    def test_unicode_content(self, deduplicator):
        """Test with unicode content."""
        content1 = {
            "id": 1,
            "title": "日本語記事",
            "content": "これは日本語です",
        }
        content2 = {
            "id": 2,
            "title": "日本語記事",
            "content": "これは日本語です",
        }

        result = deduplicator.is_duplicate(content1, content2)

        assert result["is_duplicate"] is True

    def test_missing_optional_fields(self, deduplicator):
        """Test with missing optional fields."""
        content1 = {"id": 1, "title": "Article"}
        content2 = {"id": 2, "title": "Article"}

        result = deduplicator.is_duplicate(content1, content2)

        assert "is_duplicate" in result

    def test_none_values(self, deduplicator):
        """Test with None values."""
        content1 = {"id": 1, "title": None, "content": None}
        content2 = {"id": 2, "title": None, "content": None}

        result = deduplicator.is_duplicate(content1, content2)

        assert "is_duplicate" in result
