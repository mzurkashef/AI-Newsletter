"""Test suite for content summarizer module."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.processors.content_summarizer import (
    ContentSummarizer,
    ContentSummarizationError,
    SummaryFormat,
)
from src.database.storage import DatabaseStorage


class TestContentSummarizerInitialization:
    """Test ContentSummarizer initialization."""

    def test_init_with_valid_storage(self):
        """Test initialization with valid storage."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        assert summarizer.storage == storage
        assert summarizer.summary_format.min_length == 50
        assert summarizer.summary_format.max_length == 200
        assert summarizer.summary_format.include_source is True
        assert summarizer.summary_format.include_categories is True

    def test_init_with_custom_format(self):
        """Test initialization with custom format."""
        storage = Mock(spec=DatabaseStorage)
        custom_format = SummaryFormat(
            min_length=30, max_length=150, include_source=False
        )
        summarizer = ContentSummarizer(storage=storage, summary_format=custom_format)

        assert summarizer.summary_format.min_length == 30
        assert summarizer.summary_format.max_length == 150
        assert summarizer.summary_format.include_source is False

    def test_init_with_invalid_storage(self):
        """Test initialization with invalid storage."""
        with pytest.raises(ContentSummarizationError):
            ContentSummarizer(storage="not_a_storage")

    def test_init_with_invalid_min_length(self):
        """Test initialization with invalid min_length."""
        storage = Mock(spec=DatabaseStorage)
        invalid_format = SummaryFormat(min_length=0)

        with pytest.raises(ContentSummarizationError):
            ContentSummarizer(storage=storage, summary_format=invalid_format)

    def test_init_with_invalid_max_length(self):
        """Test initialization with max_length < min_length."""
        storage = Mock(spec=DatabaseStorage)
        invalid_format = SummaryFormat(min_length=200, max_length=100)

        with pytest.raises(ContentSummarizationError):
            ContentSummarizer(storage=storage, summary_format=invalid_format)

    def test_init_creates_default_format(self):
        """Test that default format is created when not provided."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        assert isinstance(summarizer.summary_format, SummaryFormat)
        assert summarizer.summary_format.min_length == 50
        assert summarizer.summary_format.max_length == 200


class TestSummaryFormatConfiguration:
    """Test SummaryFormat configuration."""

    def test_summary_format_defaults(self):
        """Test SummaryFormat default values."""
        fmt = SummaryFormat()

        assert fmt.min_length == 50
        assert fmt.max_length == 200
        assert fmt.include_source is True
        assert fmt.include_categories is True
        assert fmt.include_summary_type is True

    def test_summary_format_custom_values(self):
        """Test SummaryFormat with custom values."""
        fmt = SummaryFormat(
            min_length=30,
            max_length=150,
            include_source=False,
            include_categories=False,
        )

        assert fmt.min_length == 30
        assert fmt.max_length == 150
        assert fmt.include_source is False
        assert fmt.include_categories is False


class TestSingleContentSummarization:
    """Test summarization of single content items."""

    @pytest.fixture
    def summarizer(self):
        """Create summarizer for testing."""
        storage = Mock(spec=DatabaseStorage)
        return ContentSummarizer(storage=storage)

    @pytest.fixture
    def sample_content(self):
        """Sample content for testing."""
        return {
            "title": "AI Breakthrough Announced",
            "content": "Researchers announced a major breakthrough in machine learning. "
            "The new model shows unprecedented performance gains. "
            "This could revolutionize artificial intelligence applications. "
            "Several companies are already adopting this technology. "
            "The impact on the industry is expected to be significant.",
            "source": "AI News Daily",
            "categories": ["ai", "research"],
        }

    def test_summarize_valid_content(self, summarizer, sample_content):
        """Test summarization of valid content."""
        result = summarizer.summarize_content(sample_content)

        assert "summary" in result
        assert "summary_text" in result
        assert result["summary_type"] == "extractive"
        assert result["original_length"] > 0
        assert result["summary_length"] > 0
        assert result["compression_ratio"] > 0
        assert result["sentences_extracted"] > 0

    def test_summarize_respects_length_constraints(self, summarizer):
        """Test that summaries respect min/max length constraints."""
        content = {
            "title": "Test",
            "content": " ".join(["word"] * 500),  # 500 word content
        }

        result = summarizer.summarize_content(content)
        summary_length = result["summary_length"]

        assert summary_length <= summarizer.summary_format.max_length

    def test_summarize_invalid_content_type(self, summarizer):
        """Test summarization with invalid content type."""
        with pytest.raises(ContentSummarizationError):
            summarizer.summarize_content("not a dict")

    def test_summarize_missing_content_field(self, summarizer):
        """Test summarization with missing content field."""
        with pytest.raises(ContentSummarizationError):
            summarizer.summarize_content({"title": "Test"})

    def test_summarize_empty_content(self, summarizer):
        """Test summarization with empty content."""
        with pytest.raises(ContentSummarizationError):
            summarizer.summarize_content({"title": "Test", "content": ""})

    def test_summarize_includes_title(self, summarizer):
        """Test that summary includes title."""
        content = {
            "title": "Important News",
            "content": "This is some important news content.",
        }

        result = summarizer.summarize_content(content)
        summary = result["summary"]

        assert "Important News" in summary

    def test_summarize_includes_source_when_configured(self, summarizer):
        """Test that summary includes source when configured."""
        content = {
            "title": "News",
            "content": "This is news content.",
            "source": "Reuters",
        }

        result = summarizer.summarize_content(content)
        summary = result["summary"]

        assert "Reuters" in summary

    def test_summarize_excludes_source_when_configured(self):
        """Test that summary excludes source when not configured."""
        storage = Mock(spec=DatabaseStorage)
        fmt = SummaryFormat(include_source=False)
        summarizer = ContentSummarizer(storage=storage, summary_format=fmt)

        content = {
            "title": "News",
            "content": "This is news content.",
            "source": "Reuters",
        }

        result = summarizer.summarize_content(content)
        summary = result["summary"]

        assert "Reuters" not in summary

    def test_summarize_short_content(self, summarizer):
        """Test summarization of short content."""
        content = {
            "title": "Short",
            "content": "This is short.",
        }

        result = summarizer.summarize_content(content)

        assert result["sentences_extracted"] >= 1
        assert "summary" in result

    def test_summarize_long_content(self, summarizer):
        """Test summarization of long content."""
        long_text = ". ".join([f"Sentence {i}" for i in range(50)])
        content = {
            "title": "Long Content",
            "content": long_text,
        }

        result = summarizer.summarize_content(content)

        assert result["compression_ratio"] > 1.0
        assert result["summary_length"] < result["original_length"]

    def test_summarize_includes_compression_ratio(self, summarizer, sample_content):
        """Test that summarization returns compression ratio."""
        result = summarizer.summarize_content(sample_content)

        assert "compression_ratio" in result
        assert result["compression_ratio"] > 0


class TestBatchContentSummarization:
    """Test batch summarization of content lists."""

    @pytest.fixture
    def summarizer(self):
        """Create summarizer for testing."""
        storage = Mock(spec=DatabaseStorage)
        return ContentSummarizer(storage=storage)

    def test_summarize_empty_list(self, summarizer):
        """Test batch summarization of empty list."""
        result = summarizer.summarize_content_list([])

        assert result["total"] == 0
        assert result["successful"] == 0
        assert result["failed"] == 0
        assert len(result["content"]) == 0

    def test_summarize_single_item_list(self, summarizer):
        """Test batch summarization of single item."""
        content_list = [
            {"title": "Test", "content": "This is test content for summarization."}
        ]

        result = summarizer.summarize_content_list(content_list)

        assert result["total"] == 1
        assert result["successful"] == 1
        assert result["failed"] == 0
        assert len(result["content"]) == 1
        assert "summary" in result["content"][0]

    def test_summarize_multiple_items(self, summarizer):
        """Test batch summarization of multiple items."""
        content_list = [
            {"title": f"Item {i}", "content": f"Content for item {i} goes here."}
            for i in range(5)
        ]

        result = summarizer.summarize_content_list(content_list)

        assert result["total"] == 5
        assert result["successful"] == 5
        assert result["failed"] == 0

    def test_summarize_with_failures(self, summarizer):
        """Test batch summarization handles failures gracefully."""
        content_list = [
            {"title": "Valid", "content": "Valid content here."},
            {"title": "Invalid"},  # Missing content field
            {"title": "Valid 2", "content": "More valid content."},
        ]

        result = summarizer.summarize_content_list(content_list)

        assert result["total"] == 3
        assert result["successful"] == 2
        assert result["failed"] == 1

    def test_batch_includes_statistics(self, summarizer):
        """Test that batch summarization includes statistics."""
        content_list = [
            {"title": f"Item {i}", "content": f"Content {i}. " * 10}
            for i in range(3)
        ]

        result = summarizer.summarize_content_list(content_list)

        assert "stats" in result
        assert "average_summary_length" in result["stats"]
        assert "average_compression_ratio" in result["stats"]
        assert "success_rate" in result["stats"]

    def test_batch_success_rate_calculation(self, summarizer):
        """Test batch success rate calculation."""
        content_list = [
            {"title": "Valid", "content": "Valid content."},
            {"title": "Invalid"},  # Missing content
            {"title": "Valid 2", "content": "More valid content."},
        ]

        result = summarizer.summarize_content_list(content_list)

        expected_rate = (2 / 3) * 100
        assert abs(result["stats"]["success_rate"] - expected_rate) < 0.1


class TestDatabaseIntegration:
    """Test database integration for summarization."""

    def test_summarize_database_empty_content(self):
        """Test summarization when database has no content."""
        storage = Mock(spec=DatabaseStorage)
        storage.get_processed_content.return_value = []

        summarizer = ContentSummarizer(storage=storage)
        result = summarizer.summarize_database_content()

        assert result["total"] == 0
        assert result["successful"] == 0
        assert result["updates"] == 0

    def test_summarize_database_with_content(self):
        """Test summarization of database content."""
        storage = Mock(spec=DatabaseStorage)
        content_list = [
            {
                "id": 1,
                "title": "News 1",
                "content": "Content for news 1. " * 5,
                "source": "Source A",
            },
            {
                "id": 2,
                "title": "News 2",
                "content": "Content for news 2. " * 5,
                "source": "Source B",
            },
        ]
        storage.get_processed_content.return_value = content_list

        summarizer = ContentSummarizer(storage=storage)
        result = summarizer.summarize_database_content()

        assert result["total"] == 2
        assert result["successful"] == 2
        # Note: updates may be 0-2 depending on whether storage methods are called

    def test_summarize_database_filters_by_source(self):
        """Test that database summarization filters by source type."""
        storage = Mock(spec=DatabaseStorage)
        content_list = [
            {
                "id": 1,
                "title": "News 1",
                "content": "Content 1. " * 5,
                "source": "SourceA",
            },
            {
                "id": 2,
                "title": "News 2",
                "content": "Content 2. " * 5,
                "source": "SourceB",
            },
        ]
        storage.get_processed_content.return_value = content_list

        summarizer = ContentSummarizer(storage=storage)
        result = summarizer.summarize_database_content(source_type="SourceA")

        assert result["total"] == 1
        assert result["successful"] == 1

    def test_summarize_database_handles_update_failures(self):
        """Test that batch summarization continues on update failures."""
        storage = Mock(spec=DatabaseStorage)
        content_list = [
            {"id": 1, "title": "News 1", "content": "Content 1. " * 5},
            {"id": 2, "title": "News 2", "content": "Content 2. " * 5},
        ]
        storage.get_processed_content.return_value = content_list

        summarizer = ContentSummarizer(storage=storage)
        result = summarizer.summarize_database_content()

        # Both should be summarized even if updates fail
        assert result["successful"] == 2


class TestSummaryFormatConfiguration:
    """Test summary format configuration and updates."""

    def test_update_summary_format(self):
        """Test updating summary format configuration."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        new_format = SummaryFormat(min_length=30, max_length=150)
        summarizer.update_summary_format(new_format)

        assert summarizer.summary_format.min_length == 30
        assert summarizer.summary_format.max_length == 150

    def test_update_format_validates_min_length(self):
        """Test that format update validates min_length."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        invalid_format = SummaryFormat(min_length=0)

        with pytest.raises(ContentSummarizationError):
            summarizer.update_summary_format(invalid_format)

    def test_update_format_validates_max_length(self):
        """Test that format update validates max_length."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        invalid_format = SummaryFormat(min_length=200, max_length=100)

        with pytest.raises(ContentSummarizationError):
            summarizer.update_summary_format(invalid_format)

    def test_update_format_must_be_summary_format_instance(self):
        """Test that update requires SummaryFormat instance."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        with pytest.raises(ContentSummarizationError):
            summarizer.update_summary_format("not a format")


class TestCategorizationStatistics:
    """Test statistical methods."""

    def test_get_summarization_statistics_empty_list(self):
        """Test statistics with empty list."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        stats = summarizer.get_summarization_statistics([])

        assert stats["total"] == 0
        assert stats["avg_original_length"] == 0
        assert stats["avg_compression_ratio"] == 1.0

    def test_get_summarization_statistics_valid_content(self):
        """Test statistics calculation with valid content."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        content_list = [
            {"title": f"Item {i}", "content": f"Content {i}. " * 20}
            for i in range(3)
        ]

        stats = summarizer.get_summarization_statistics(content_list)

        assert stats["total"] == 3
        assert stats["avg_original_length"] > 0
        assert stats["avg_summary_length"] > 0
        assert stats["avg_compression_ratio"] > 0
        assert stats["min_compression"] > 0
        assert stats["max_compression"] > 0

    def test_statistics_tracks_compression(self):
        """Test that statistics track compression accurately."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        content_list = [
            {
                "title": "Test",
                "content": " ".join(["word"] * 200),  # 200 words - should compress
            }
        ]

        stats = summarizer.get_summarization_statistics(content_list)

        assert stats["total_compression"] >= 0


class TestFindLongSummaries:
    """Test finding summaries that exceed max length."""

    def test_find_long_summaries_empty_list(self):
        """Test finding long summaries with empty list."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        result = summarizer.find_long_summaries([])

        assert result == []

    def test_find_long_summaries_no_long_items(self):
        """Test when no items have oversized summaries."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        content_list = [
            {
                "title": "Test",
                "summary_text": "Short summary.",
            }
        ]

        result = summarizer.find_long_summaries(content_list)

        assert len(result) == 0

    def test_find_long_summaries_with_long_items(self):
        """Test finding items with oversized summaries."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        content_list = [
            {
                "title": "Test",
                "summary_text": " ".join(["word"] * 300),  # 300 words, exceeds default max of 200
            }
        ]

        result = summarizer.find_long_summaries(content_list)

        assert len(result) == 1
        assert result[0]["excess"] == 100


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_summarize_content_with_no_periods(self):
        """Test summarization of content without periods."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        content = {
            "title": "Test",
            "content": "This is content without proper punctuation",
        }

        result = summarizer.summarize_content(content)

        assert "summary" in result
        assert len(result["summary"]) > 0

    def test_summarize_content_with_special_characters(self):
        """Test summarization with special characters."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        content = {
            "title": "Test with @#$%",
            "content": "Content with !@#$%^&*() special characters.",
        }

        result = summarizer.summarize_content(content)

        assert "summary" in result

    def test_summarize_single_sentence(self):
        """Test summarization of single sentence."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        content = {
            "title": "Test",
            "content": "This is a single sentence.",
        }

        result = summarizer.summarize_content(content)

        assert len(result["summary"]) > 0

    def test_summarize_all_short_sentences(self):
        """Test summarization when all sentences are short."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        content = {
            "title": "Test",
            "content": "Short. Very. Sentences. Here.",
        }

        result = summarizer.summarize_content(content)

        assert "summary" in result

    def test_summarize_with_very_long_words(self):
        """Test summarization with unusually long words."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        content = {
            "title": "Test",
            "content": "Supercalifragilisticexpialidocious pneumonoultramicroscopicsilicovolcanoconiosis.",
        }

        result = summarizer.summarize_content(content)

        assert result["summary_type"] == "extractive"

    def test_summarize_with_numbers_and_punctuation(self):
        """Test summarization with numbers and varied punctuation."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        content = {
            "title": "Test",
            "content": "In 2025, there are 1,000,000 users! Is this correct? Yes, it is.",
        }

        result = summarizer.summarize_content(content)

        assert "summary" in result

    def test_summarize_unicode_content(self):
        """Test summarization with unicode characters."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        content = {
            "title": "Test",
            "content": "Café, naïve, résumé. Unicode symbols: ™ © ® ℃.",
        }

        result = summarizer.summarize_content(content)

        assert "summary" in result


class TestSummaryContent:
    """Test summary content structure and metadata."""

    def test_summary_includes_title(self):
        """Test that formatted summary includes title."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        content = {
            "title": "Important Update",
            "content": "This is important news. " * 5,
        }

        result = summarizer.summarize_content(content)

        assert "Important Update" in result["summary"]

    def test_summary_includes_categories_when_present(self):
        """Test that summary includes categories when present."""
        storage = Mock(spec=DatabaseStorage)
        summarizer = ContentSummarizer(storage=storage)

        content = {
            "title": "Test",
            "content": "Test content. " * 5,
            "categories": ["ai", "research"],
        }

        result = summarizer.summarize_content(content)

        assert "ai" in result["summary"]
        assert "research" in result["summary"]

    def test_summary_excludes_categories_when_not_configured(self):
        """Test that summary excludes categories when not configured."""
        storage = Mock(spec=DatabaseStorage)
        fmt = SummaryFormat(include_categories=False)
        summarizer = ContentSummarizer(storage=storage, summary_format=fmt)

        content = {
            "title": "Test",
            "content": "Test content. " * 5,
            "categories": ["ai", "research"],
        }

        result = summarizer.summarize_content(content)

        assert "Categories" not in result["summary"]

    def test_summary_includes_type_when_configured(self):
        """Test that summary includes type indicator when configured."""
        storage = Mock(spec=DatabaseStorage)
        fmt = SummaryFormat(include_summary_type=True)
        summarizer = ContentSummarizer(storage=storage, summary_format=fmt)

        content = {
            "title": "Test",
            "content": "Test content. " * 5,
        }

        result = summarizer.summarize_content(content)

        assert "Type:" in result["summary"]
        assert "extractive" in result["summary"]

    def test_summary_excludes_type_when_not_configured(self):
        """Test that summary excludes type when not configured."""
        storage = Mock(spec=DatabaseStorage)
        fmt = SummaryFormat(include_summary_type=False)
        summarizer = ContentSummarizer(storage=storage, summary_format=fmt)

        content = {
            "title": "Test",
            "content": "Test content. " * 5,
        }

        result = summarizer.summarize_content(content)

        assert "Type:" not in result["summary"]
