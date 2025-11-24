"""Test suite for newsletter assembler module."""

import pytest
from unittest.mock import Mock
from datetime import datetime, timedelta
from src.delivery.newsletter_assembler import (
    NewsletterAssembler,
    NewsletterAssemblyError,
    NewsletterConfig,
    TopicSection,
)
from src.database.storage import DatabaseStorage


class TestNewsletterAssemblerInitialization:
    """Test NewsletterAssembler initialization."""

    def test_init_with_valid_storage(self):
        """Test initialization with valid storage."""
        storage = Mock(spec=DatabaseStorage)
        assembler = NewsletterAssembler(storage=storage)

        assert assembler.storage == storage
        assert assembler.config.include_date is True
        assert assembler.config.skip_empty_categories is True

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        storage = Mock(spec=DatabaseStorage)
        config = NewsletterConfig(
            include_date=False,
            include_footer=False,
            skip_empty_categories=False,
        )
        assembler = NewsletterAssembler(storage=storage, config=config)

        assert assembler.config.include_date is False
        assert assembler.config.include_footer is False
        assert assembler.config.skip_empty_categories is False

    def test_init_with_invalid_storage(self):
        """Test initialization with invalid storage."""
        with pytest.raises(NewsletterAssemblyError):
            NewsletterAssembler(storage="not_a_storage")

    def test_init_creates_default_config(self):
        """Test that default config is created when not provided."""
        storage = Mock(spec=DatabaseStorage)
        assembler = NewsletterAssembler(storage=storage)

        assert isinstance(assembler.config, NewsletterConfig)


class TestNewsletterConfigDataclass:
    """Test NewsletterConfig dataclass."""

    def test_config_defaults(self):
        """Test NewsletterConfig default values."""
        config = NewsletterConfig()

        assert config.include_date is True
        assert config.include_footer is True
        assert config.skip_empty_categories is True
        assert config.header_format == "bold"

    def test_config_custom_values(self):
        """Test NewsletterConfig with custom values."""
        config = NewsletterConfig(
            include_date=False,
            header_format="markdown",
            week_identifier="Week 1, 2025",
        )

        assert config.include_date is False
        assert config.header_format == "markdown"
        assert config.week_identifier == "Week 1, 2025"


class TestGroupContentByCategory:
    """Test grouping content by category."""

    @pytest.fixture
    def assembler(self):
        """Create assembler for testing."""
        storage = Mock(spec=DatabaseStorage)
        return NewsletterAssembler(storage=storage)

    def test_group_empty_list(self, assembler):
        """Test grouping empty content list."""
        result = assembler.group_content_by_category([])

        assert result == {}

    def test_group_single_category(self, assembler):
        """Test grouping content with single category."""
        content = [
            {"title": "Item 1", "categories": ["AI"]},
            {"title": "Item 2", "categories": ["AI"]},
            {"title": "Item 3", "categories": ["AI"]},
        ]

        result = assembler.group_content_by_category(content)

        assert len(result) == 1
        assert "AI" in result
        assert len(result["AI"]) == 3

    def test_group_multiple_categories(self, assembler):
        """Test grouping content with multiple categories."""
        content = [
            {"title": "Item 1", "categories": ["AI"]},
            {"title": "Item 2", "categories": ["Security"]},
            {"title": "Item 3", "categories": ["Cloud"]},
            {"title": "Item 4", "categories": ["AI", "Security"]},
        ]

        result = assembler.group_content_by_category(content)

        assert len(result) == 3
        assert len(result["AI"]) == 2
        assert len(result["Security"]) == 2
        assert len(result["Cloud"]) == 1

    def test_group_with_category_field(self, assembler):
        """Test grouping with 'category' field instead of 'categories'."""
        content = [
            {"title": "Item 1", "category": "AI"},
            {"title": "Item 2", "category": "Security"},
        ]

        result = assembler.group_content_by_category(content)

        assert len(result) == 2
        assert "AI" in result
        assert "Security" in result

    def test_group_invalid_content_type(self, assembler):
        """Test grouping with invalid content type."""
        with pytest.raises(NewsletterAssemblyError):
            assembler.group_content_by_category("not a list")


class TestCreateHeader:
    """Test header creation."""

    @pytest.fixture
    def assembler(self):
        """Create assembler for testing."""
        storage = Mock(spec=DatabaseStorage)
        return NewsletterAssembler(storage=storage)

    def test_create_header_default(self, assembler):
        """Test default header creation."""
        header = assembler.create_header()

        assert "AI NEWSLETTER" in header
        assert "=" * 50 in header

    def test_create_header_without_date(self):
        """Test header creation without date."""
        storage = Mock(spec=DatabaseStorage)
        config = NewsletterConfig(include_date=False)
        assembler = NewsletterAssembler(storage=storage, config=config)

        header = assembler.create_header()

        assert "AI NEWSLETTER" in header
        assert "Week of" not in header

    def test_create_header_with_custom_week(self):
        """Test header with custom week identifier."""
        storage = Mock(spec=DatabaseStorage)
        config = NewsletterConfig(week_identifier="Week 1, 2025")
        assembler = NewsletterAssembler(storage=storage, config=config)

        header = assembler.create_header()

        assert "Week 1, 2025" in header

    def test_create_header_markdown_format(self):
        """Test header with markdown format."""
        storage = Mock(spec=DatabaseStorage)
        config = NewsletterConfig(header_format="markdown")
        assembler = NewsletterAssembler(storage=storage, config=config)

        header = assembler.create_header()

        assert "# 📰 AI NEWSLETTER" in header


class TestCreateFooter:
    """Test footer creation."""

    @pytest.fixture
    def assembler(self):
        """Create assembler for testing."""
        storage = Mock(spec=DatabaseStorage)
        return NewsletterAssembler(storage=storage)

    def test_create_footer_default(self, assembler):
        """Test default footer creation."""
        footer = assembler.create_footer()

        assert "=" * 50 in footer
        assert "Generated" in footer

    def test_create_footer_without_credits(self):
        """Test footer without source credits."""
        storage = Mock(spec=DatabaseStorage)
        config = NewsletterConfig(include_source_credits=False)
        assembler = NewsletterAssembler(storage=storage, config=config)

        footer = assembler.create_footer()

        assert "Sources" not in footer
        assert "=" * 50 in footer


class TestCreateTopicSection:
    """Test topic section creation."""

    @pytest.fixture
    def assembler(self):
        """Create assembler for testing."""
        storage = Mock(spec=DatabaseStorage)
        return NewsletterAssembler(storage=storage)

    def test_create_section_single_item(self, assembler):
        """Test section creation with single item."""
        content = [
            {
                "summary_text": "AI breakthrough announced",
                "source": "AI News Daily",
                "content_url": "https://example.com/article",
            }
        ]

        section = assembler.create_topic_section("Announcements", content)

        assert "ANNOUNCEMENTS" in section
        assert "AI breakthrough announced" in section
        assert "AI News Daily" in section

    def test_create_section_multiple_items(self, assembler):
        """Test section creation with multiple items."""
        content = [
            {
                "summary_text": "Item 1",
                "source": "Source A",
                "content_url": "https://example.com/1",
            },
            {
                "summary_text": "Item 2",
                "source": "Source B",
                "content_url": "https://example.com/2",
            },
            {
                "summary_text": "Item 3",
                "source": "Source C",
                "content_url": "https://example.com/3",
            },
        ]

        section = assembler.create_topic_section("Research", content)

        assert "1." in section
        assert "2." in section
        assert "3." in section

    def test_create_section_truncates_long_summary(self, assembler):
        """Test that long summaries are truncated."""
        content = [
            {
                "summary_text": "x" * 300,
                "source": "Source",
                "content_url": "https://example.com",
            }
        ]

        section = assembler.create_topic_section("Topic", content)

        assert "..." in section


class TestAssembleNewsletter:
    """Test complete newsletter assembly."""

    @pytest.fixture
    def assembler(self):
        """Create assembler for testing."""
        storage = Mock(spec=DatabaseStorage)
        return NewsletterAssembler(storage=storage)

    @pytest.fixture
    def sample_content(self):
        """Sample content for testing."""
        return [
            {
                "title": "AI Breakthrough",
                "summary_text": "Major AI model released",
                "categories": ["AI"],
                "source": "AI News",
                "content_url": "https://example.com/1",
            },
            {
                "title": "Security Update",
                "summary_text": "New vulnerability disclosed",
                "categories": ["Security"],
                "source": "Security Weekly",
                "content_url": "https://example.com/2",
            },
            {
                "title": "Cloud News",
                "summary_text": "Cloud provider announces new service",
                "categories": ["Cloud"],
                "source": "Cloud Digest",
                "content_url": "https://example.com/3",
            },
        ]

    def test_assemble_valid_content(self, assembler, sample_content):
        """Test assembling valid content."""
        result = assembler.assemble_newsletter(sample_content)

        assert "newsletter" in result
        assert "topic_sections" in result
        assert result["total_items"] == 3
        assert result["total_topics"] == 3

    def test_assemble_empty_content(self, assembler):
        """Test assembly with empty content list."""
        with pytest.raises(NewsletterAssemblyError):
            assembler.assemble_newsletter([])

    def test_assemble_invalid_content_type(self, assembler):
        """Test assembly with invalid content type."""
        with pytest.raises(NewsletterAssemblyError):
            assembler.assemble_newsletter("not a list")

    def test_assemble_includes_header(self, assembler, sample_content):
        """Test that assembly includes header."""
        result = assembler.assemble_newsletter(sample_content)

        assert "AI NEWSLETTER" in result["newsletter"]

    def test_assemble_includes_footer(self, assembler, sample_content):
        """Test that assembly includes footer."""
        result = assembler.assemble_newsletter(sample_content)

        assert "=" * 50 in result["newsletter"]

    def test_assemble_skips_empty_categories(self, assembler):
        """Test that empty categories are skipped."""
        content = [
            {
                "title": "Item 1",
                "summary_text": "Content",
                "categories": ["AI"],
                "source": "Source",
                "content_url": "https://example.com",
            }
        ]

        result = assembler.assemble_newsletter(content)

        assert result["total_topics"] == 1

    def test_assemble_with_week_identifier(self, assembler, sample_content):
        """Test assembly with week identifier."""
        result = assembler.assemble_newsletter(sample_content, "Week 1, 2025")

        assert "Week 1, 2025" in result["newsletter"]

    def test_assemble_returns_metadata(self, assembler, sample_content):
        """Test that assembly returns metadata."""
        result = assembler.assemble_newsletter(sample_content)

        assert "metadata" in result
        assert "assembled_at" in result["metadata"]
        assert "character_count" in result["metadata"]


class TestValidateNewsletterStructure:
    """Test newsletter validation."""

    @pytest.fixture
    def assembler(self):
        """Create assembler for testing."""
        storage = Mock(spec=DatabaseStorage)
        return NewsletterAssembler(storage=storage)

    def test_validate_valid_newsletter(self, assembler):
        """Test validation of valid newsletter."""
        newsletter = (
            "AI NEWSLETTER\n"
            "Week of January 20 - January 26, 2025\n\n"
            "🔹 AI\n"
            "-" * 40 + "\n"
            "1. Item 1\n"
            "2. Item 2\n\n"
            "=" * 50
        )

        result = assembler.validate_newsletter_structure(newsletter)

        assert result["is_valid"] is True

    def test_validate_empty_newsletter(self, assembler):
        """Test validation of empty newsletter."""
        with pytest.raises(NewsletterAssemblyError):
            assembler.validate_newsletter_structure("")

    def test_validate_newsletter_missing_sections(self, assembler):
        """Test validation of newsletter with missing sections."""
        newsletter = "Some content but no proper structure"

        result = assembler.validate_newsletter_structure(newsletter)

        assert result["is_valid"] is False
        assert len(result["issues"]) > 0

    def test_validate_invalid_type(self, assembler):
        """Test validation with invalid type."""
        with pytest.raises(NewsletterAssemblyError):
            assembler.validate_newsletter_structure(123)


class TestUpdateConfig:
    """Test configuration updates."""

    @pytest.fixture
    def assembler(self):
        """Create assembler for testing."""
        storage = Mock(spec=DatabaseStorage)
        return NewsletterAssembler(storage=storage)

    def test_update_config(self, assembler):
        """Test updating configuration."""
        new_config = NewsletterConfig(include_date=False)
        assembler.update_config(new_config)

        assert assembler.config.include_date is False

    def test_update_config_invalid_type(self, assembler):
        """Test update with invalid config type."""
        with pytest.raises(NewsletterAssemblyError):
            assembler.update_config("not a config")


class TestAssemblyStatistics:
    """Test assembly statistics calculation."""

    @pytest.fixture
    def assembler(self):
        """Create assembler for testing."""
        storage = Mock(spec=DatabaseStorage)
        return NewsletterAssembler(storage=storage)

    def test_statistics_empty_content(self, assembler):
        """Test statistics with empty content."""
        stats = assembler.get_assembly_statistics([])

        assert stats["total_items"] == 0
        assert stats["total_categories"] == 0

    def test_statistics_single_category(self, assembler):
        """Test statistics with single category."""
        content = [
            {"categories": ["AI"], "content": "Item 1"},
            {"categories": ["AI"], "content": "Item 2"},
        ]

        stats = assembler.get_assembly_statistics(content)

        assert stats["total_items"] == 2
        assert stats["total_categories"] == 1
        assert stats["categories"]["AI"] == 2

    def test_statistics_multiple_categories(self, assembler):
        """Test statistics with multiple categories."""
        content = [
            {"categories": ["AI"], "content": "Item 1"},
            {"categories": ["Security"], "content": "Item 2"},
            {"categories": ["Cloud"], "content": "Item 3"},
            {"categories": ["Cloud"], "content": "Item 4"},
        ]

        stats = assembler.get_assembly_statistics(content)

        assert stats["total_items"] == 4
        assert stats["total_categories"] == 3
        assert stats["max_items_per_category"] == 2


class TestTopicSectionDataclass:
    """Test TopicSection dataclass."""

    def test_topic_section_creation(self):
        """Test TopicSection creation."""
        section = TopicSection(
            topic_name="AI",
            content_items=[{"title": "Item 1"}],
        )

        assert section.topic_name == "AI"
        assert len(section.content_items) == 1
        assert section.item_count == 1

    def test_topic_section_empty(self):
        """Test TopicSection with no items."""
        section = TopicSection(topic_name="AI")

        assert section.topic_name == "AI"
        assert section.item_count == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def assembler(self):
        """Create assembler for testing."""
        storage = Mock(spec=DatabaseStorage)
        return NewsletterAssembler(storage=storage)

    def test_assemble_very_long_content(self, assembler):
        """Test assembly with very long content."""
        content = [
            {
                "title": f"Item {i}",
                "summary_text": "x" * 500,
                "categories": ["Topic"],
                "source": f"Source {i}",
                "content_url": f"https://example.com/{i}",
            }
            for i in range(50)
        ]

        result = assembler.assemble_newsletter(content)

        assert result["total_items"] == 50
        assert result["metadata"]["character_count"] > 10000

    def test_assemble_many_categories(self, assembler):
        """Test assembly with many categories."""
        content = [
            {
                "title": f"Item {i}",
                "summary_text": f"Content {i}",
                "categories": [f"Category{i % 20}"],
                "source": "Source",
                "content_url": "https://example.com",
            }
            for i in range(100)
        ]

        result = assembler.assemble_newsletter(content)

        assert result["total_topics"] <= 20

    def test_assemble_missing_summary_field(self, assembler):
        """Test assembly with missing summary field."""
        content = [
            {
                "title": "Item",
                "categories": ["AI"],
                "source": "Source",
                "content_url": "https://example.com",
            }
        ]

        result = assembler.assemble_newsletter(content)

        assert "newsletter" in result
        assert result["total_items"] == 1

    def test_assemble_with_special_characters(self, assembler):
        """Test assembly with special characters."""
        content = [
            {
                "title": "Item with émojis 🚀 and spëcial chars",
                "summary_text": "Content with © and ® symbols",
                "categories": ["AI"],
                "source": "Source™",
                "content_url": "https://example.com",
            }
        ]

        result = assembler.assemble_newsletter(content)

        assert "newsletter" in result
        assert result["total_items"] == 1
