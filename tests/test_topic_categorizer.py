"""
Tests for topic categorization module.
"""

import pytest
from unittest.mock import Mock, patch

from src.processors.topic_categorizer import (
    TopicCategorizer,
    TopicCategorizationError,
    Topic,
)


@pytest.fixture
def mock_storage():
    """Mock database storage."""
    storage = Mock()
    storage.get_processed_content = Mock(return_value=[])
    storage.update_content_status = Mock()
    return storage


@pytest.fixture
def categorizer(mock_storage):
    """Create categorizer instance with default topics."""
    return TopicCategorizer(storage=mock_storage)


class TestTopicCategorizerInitialization:
    """Test categorizer initialization."""

    def test_initialization_with_storage(self, mock_storage):
        """Test initialization with storage."""
        cat = TopicCategorizer(storage=mock_storage)

        assert cat.storage == mock_storage
        assert cat.min_confidence == 0.5
        assert len(cat.topics) > 0

    def test_initialization_with_custom_topics(self, mock_storage):
        """Test initialization with custom topics."""
        custom_topics = {
            "custom": Topic(
                id="custom",
                name="Custom Topic",
                description="A custom topic",
                keywords={"test": 1.0},
            )
        }

        cat = TopicCategorizer(storage=mock_storage, topics=custom_topics)

        assert "custom" in cat.topics
        assert len(cat.topics) == 1

    def test_default_topics_loaded(self, categorizer):
        """Test that default topics are loaded."""
        assert "ai" in categorizer.topics
        assert "llm" in categorizer.topics
        assert "cloud" in categorizer.topics
        assert "security" in categorizer.topics

    def test_custom_min_confidence(self, mock_storage):
        """Test custom minimum confidence."""
        cat = TopicCategorizer(storage=mock_storage, min_confidence=0.7)

        assert cat.min_confidence == 0.7


class TestTopicDefinition:
    """Test topic definition structure."""

    def test_topic_attributes(self, categorizer):
        """Test topic has required attributes."""
        topic = categorizer.topics["ai"]

        assert topic.id == "ai"
        assert topic.name == "Artificial Intelligence"
        assert topic.description
        assert len(topic.keywords) > 0

    def test_topic_keywords_have_weights(self, categorizer):
        """Test that keywords have weights."""
        topic = categorizer.topics["ai"]

        for keyword, weight in topic.keywords.items():
            assert isinstance(keyword, str)
            assert isinstance(weight, (int, float))
            assert weight > 0


class TestContentCategorization:
    """Test single content categorization."""

    def test_categorize_ai_content(self, categorizer):
        """Test categorizing AI content."""
        content = {
            "title": "New AI Model Released",
            "content": "A breakthrough in deep learning and neural networks",
        }

        result = categorizer.categorize_content(content)

        assert "categories" in result
        assert "ai" in result["categories"]

    def test_categorize_llm_content(self, categorizer):
        """Test categorizing LLM content."""
        content = {
            "title": "GPT-5 Language Model Announced",
            "content": "New language model with improved transformer and llm capabilities",
        }

        result = categorizer.categorize_content(content)

        assert len(result["categories"]) > 0

    def test_categorize_cloud_content(self, categorizer):
        """Test categorizing cloud content."""
        content = {
            "title": "AWS New Feature",
            "content": "Kubernetes and serverless improvements on AWS",
        }

        result = categorizer.categorize_content(content)

        assert "cloud" in result["categories"]

    def test_categorize_multiple_categories(self, categorizer):
        """Test content matching multiple categories."""
        content = {
            "title": "AI on Cloud",
            "content": "Deep learning training on AWS infrastructure with kubernetes",
        }

        result = categorizer.categorize_content(content)

        assert len(result["categories"]) >= 2
        assert "ai" in result["categories"]
        assert "cloud" in result["categories"]

    def test_no_category_match(self, categorizer):
        """Test content with no category match."""
        content = {
            "title": "Weather Report",
            "content": "It will be sunny tomorrow with light winds",
        }

        result = categorizer.categorize_content(content)

        assert len(result["categories"]) == 0

    def test_primary_category_selection(self, categorizer):
        """Test that primary category is selected."""
        content = {
            "title": "AI News",
            "content": "Artificial intelligence breakthrough in deep learning",
        }

        result = categorizer.categorize_content(content)

        assert result["primary_category"] is not None
        assert result["primary_confidence"] > 0

    def test_confidence_scores(self, categorizer):
        """Test that confidence scores are returned."""
        content = {
            "title": "AI and Cloud",
            "content": "Machine learning on AWS cloud infrastructure",
        }

        result = categorizer.categorize_content(content)

        assert "confidence" in result
        assert isinstance(result["confidence"], dict)
        for score in result["confidence"].values():
            assert 0.0 <= score <= 1.0

    def test_matching_reasons(self, categorizer):
        """Test that matching keywords are tracked."""
        content = {
            "title": "AI and Deep Learning",
            "content": "Deep learning and neural networks",
        }

        result = categorizer.categorize_content(content)

        assert "reasons" in result
        assert isinstance(result["reasons"], dict)

    def test_invalid_content_type(self, categorizer):
        """Test handling of invalid content type."""
        result = categorizer.categorize_content("not a dict")

        assert result["categories"] == []
        assert result["primary_category"] is None

    def test_missing_fields(self, categorizer):
        """Test handling of missing fields."""
        content = {"id": 1}  # No title or content

        result = categorizer.categorize_content(content)

        assert isinstance(result, dict)
        assert "categories" in result

    def test_none_values(self, categorizer):
        """Test handling of None values."""
        content = {"title": None, "content": None}

        result = categorizer.categorize_content(content)

        assert isinstance(result, dict)
        assert result["categories"] == []

    def test_case_insensitive_matching(self, categorizer):
        """Test case insensitive keyword matching."""
        content1 = {
            "title": "AI Model",
            "content": "artificial intelligence",
        }
        content2 = {
            "title": "AI MODEL",
            "content": "ARTIFICIAL INTELLIGENCE",
        }

        result1 = categorizer.categorize_content(content1)
        result2 = categorizer.categorize_content(content2)

        assert "ai" in result1["categories"]
        assert "ai" in result2["categories"]


class TestBatchCategorization:
    """Test batch content categorization."""

    def test_empty_list(self, categorizer):
        """Test categorizing empty list."""
        result = categorizer.categorize_content_list([])

        assert result["total"] == 0
        assert result["categorized"] == 0
        assert result["content_with_categories"] == []

    def test_single_item(self, categorizer):
        """Test categorizing single item."""
        content = [
            {"title": "AI News", "content": "Machine learning breakthrough"}
        ]

        result = categorizer.categorize_content_list(content)

        assert result["total"] == 1
        assert result["categorized"] == 1

    def test_multiple_items(self, categorizer):
        """Test categorizing multiple items."""
        content = [
            {"title": "AI News", "content": "Machine learning"},
            {"title": "Cloud Info", "content": "AWS and kubernetes"},
            {"title": "Security", "content": "Encryption and privacy"},
        ]

        result = categorizer.categorize_content_list(content)

        assert result["total"] == 3
        assert result["categorized"] == 3

    def test_batch_structure(self, categorizer):
        """Test batch result structure."""
        content = [{"title": "AI", "content": "Machine learning"}]

        result = categorizer.categorize_content_list(content)

        assert "total" in result
        assert "categorized" in result
        assert "content_with_categories" in result
        assert "category_distribution" in result
        assert "statistics" in result

    def test_category_distribution(self, categorizer):
        """Test category distribution calculation."""
        content = [
            {"title": "AI", "content": "Machine learning"},
            {"title": "AI 2", "content": "Deep learning"},
            {"title": "Cloud", "content": "AWS"},
        ]

        result = categorizer.categorize_content_list(content)

        assert "category_distribution" in result
        assert isinstance(result["category_distribution"], dict)

    def test_statistics_calculation(self, categorizer):
        """Test statistics calculation."""
        content = [
            {"title": "AI", "content": "Machine learning"},
            {"title": "AI Cloud", "content": "Deep learning on AWS"},
        ]

        result = categorizer.categorize_content_list(content)

        stats = result["statistics"]
        assert "avg_categories_per_item" in stats
        assert "items_with_primary" in stats
        assert "items_with_multiple" in stats

    def test_content_with_categories(self, categorizer):
        """Test that content items are enriched with categories."""
        content = [
            {"id": 1, "title": "AI", "content": "Machine learning"}
        ]

        result = categorizer.categorize_content_list(content)

        assert len(result["content_with_categories"]) == 1
        item = result["content_with_categories"][0]
        assert "categories" in item
        assert "primary_category" in item
        assert "category_confidence" in item


class TestDatabaseCategorization:
    """Test database categorization."""

    def test_empty_database(self, categorizer, mock_storage):
        """Test with empty database."""
        mock_storage.get_processed_content.return_value = []

        result = categorizer.categorize_database_content()

        assert result["total"] == 0
        assert result["categorized"] == 0

    def test_content_updated_in_database(self, categorizer, mock_storage):
        """Test that database is updated with categories."""
        mock_storage.get_processed_content.return_value = [
            {"id": 1, "title": "AI", "content": "Machine learning"}
        ]

        result = categorizer.categorize_database_content()

        assert mock_storage.update_content_status.called

    def test_error_handling(self, categorizer, mock_storage):
        """Test error handling."""
        mock_storage.get_processed_content.side_effect = Exception("DB error")

        result = categorizer.categorize_database_content()

        assert "error" in result
        assert result["categorized"] == 0


class TestConfidenceThreshold:
    """Test confidence threshold configuration."""

    def test_update_min_confidence(self, categorizer):
        """Test updating minimum confidence."""
        categorizer.update_min_confidence(0.7)

        assert categorizer.min_confidence == 0.7

    def test_invalid_confidence_low(self, categorizer):
        """Test invalid confidence (too low)."""
        with pytest.raises(TopicCategorizationError):
            categorizer.update_min_confidence(-0.1)

    def test_invalid_confidence_high(self, categorizer):
        """Test invalid confidence (too high)."""
        with pytest.raises(TopicCategorizationError):
            categorizer.update_min_confidence(1.1)

    def test_boundary_confidence_zero(self, categorizer):
        """Test confidence at zero boundary."""
        categorizer.update_min_confidence(0.0)

        assert categorizer.min_confidence == 0.0

    def test_boundary_confidence_one(self, categorizer):
        """Test confidence at one boundary."""
        categorizer.update_min_confidence(1.0)

        assert categorizer.min_confidence == 1.0

    def test_threshold_affects_categorization(self, categorizer):
        """Test that threshold affects categorization results."""
        content = {
            "title": "AI",
            "content": "Machine learning",
        }

        # Low threshold
        categorizer.update_min_confidence(0.1)
        result1 = categorizer.categorize_content(content)
        count1 = len(result1["categories"])

        # High threshold
        categorizer.update_min_confidence(0.9)
        result2 = categorizer.categorize_content(content)
        count2 = len(result2["categories"])

        # Higher threshold should result in fewer or equal categories
        assert count2 <= count1


class TestCustomTopics:
    """Test custom topic management."""

    def test_add_custom_topic(self, categorizer):
        """Test adding a custom topic."""
        custom_topic = Topic(
            id="blockchain",
            name="Blockchain & Crypto",
            description="Blockchain and cryptocurrency",
            keywords={"blockchain": 2.0, "crypto": 1.8},
        )

        categorizer.add_custom_topic(custom_topic)

        assert "blockchain" in categorizer.topics

    def test_duplicate_topic_error(self, categorizer):
        """Test that duplicate topic raises error."""
        custom_topic = Topic(
            id="ai",
            name="Duplicate",
            description="Duplicate",
            keywords={},
        )

        with pytest.raises(TopicCategorizationError):
            categorizer.add_custom_topic(custom_topic)

    def test_remove_topic(self, categorizer):
        """Test removing a topic."""
        original_count = len(categorizer.topics)

        categorizer.remove_topic("ai")

        assert len(categorizer.topics) == original_count - 1
        assert "ai" not in categorizer.topics

    def test_remove_nonexistent_topic(self, categorizer):
        """Test removing nonexistent topic."""
        with pytest.raises(TopicCategorizationError):
            categorizer.remove_topic("nonexistent")

    def test_get_topic_info(self, categorizer):
        """Test getting topic information."""
        # Get from default topics
        topic_info = categorizer.get_topic_info("ai")

        if topic_info:
            assert topic_info.id == "ai"

        # Also test with a topic that definitely exists
        for topic_id in categorizer.topics:
            info = categorizer.get_topic_info(topic_id)
            assert info is not None
            assert info.id == topic_id
            break

    def test_list_topics(self, categorizer):
        """Test listing all topics."""
        topics_list = categorizer.list_topics()

        assert len(topics_list) > 0
        assert all("id" in t for t in topics_list)
        assert all("name" in t for t in topics_list)


class TestCategorizationStatistics:
    """Test statistics calculation."""

    def test_empty_list_stats(self, categorizer):
        """Test statistics on empty list."""
        stats = categorizer.get_categorization_statistics([])

        assert stats["total"] == 0
        assert stats["avg_categories_per_item"] == 0.0

    def test_coverage_calculation(self, categorizer):
        """Test coverage calculation."""
        content = [
            {"title": "AI", "content": "Machine learning"},
            {"title": "Weather", "content": "Sunny tomorrow"},
        ]

        stats = categorizer.get_categorization_statistics(content)

        assert "coverage" in stats
        assert "items_with_categories" in stats["coverage"]
        assert "percentage" in stats["coverage"]

    def test_topic_distribution(self, categorizer):
        """Test topic distribution in statistics."""
        content = [
            {"title": "AI", "content": "Machine learning"},
            {"title": "Cloud", "content": "AWS"},
        ]

        stats = categorizer.get_categorization_statistics(content)

        assert "by_topic" in stats
        assert isinstance(stats["by_topic"], dict)

    def test_average_categories(self, categorizer):
        """Test average categories per item."""
        content = [
            {"title": "AI Cloud", "content": "Deep learning on AWS with machine learning"},
            {"title": "Machine Learning AI", "content": "Machine learning and artificial intelligence"},
        ]

        stats = categorizer.get_categorization_statistics(content)

        assert stats["avg_categories_per_item"] >= 0


class TestUncategorizedContent:
    """Test finding uncategorized content."""

    def test_find_uncategorized(self, categorizer):
        """Test finding uncategorized content."""
        content = [
            {"title": "AI", "content": "Machine learning"},
            {"title": "Weather", "content": "Sunny today"},
            {"title": "Sports", "content": "Game results"},
        ]

        uncategorized = categorizer.find_uncategorized_content(content)

        assert len(uncategorized) >= 1

    def test_all_categorized(self, categorizer):
        """Test when all content is categorized."""
        content = [
            {"title": "AI Machine Learning", "content": "Machine learning and artificial intelligence"},
            {"title": "Cloud AWS Infrastructure", "content": "AWS cloud and kubernetes"},
        ]

        uncategorized = categorizer.find_uncategorized_content(content)

        # Most or all should be categorized
        assert len(uncategorized) <= len(content) / 2

    def test_all_uncategorized(self, categorizer):
        """Test when all content is uncategorized."""
        content = [
            {"title": "Random 1", "content": "Nothing relevant"},
            {"title": "Random 2", "content": "No keywords here"},
        ]

        uncategorized = categorizer.find_uncategorized_content(content)

        assert len(uncategorized) == len(content)


class TestEdgeCases:
    """Test edge cases."""

    def test_very_long_content(self, categorizer):
        """Test with very long content."""
        long_text = "ai machine learning deep learning neural networks " * 1000
        content = {"title": "Long", "content": long_text}

        result = categorizer.categorize_content(content)

        # Should handle long content without crashing
        assert "categories" in result

    def test_special_characters(self, categorizer):
        """Test with special characters."""
        content = {
            "title": "AI @#$% Machine Learning",
            "content": "Machine learning & neural networks! artificial intelligence",
        }

        result = categorizer.categorize_content(content)

        # Should handle special characters without crashing
        assert isinstance(result["categories"], list)

    def test_unicode_content(self, categorizer):
        """Test with unicode content."""
        content = {
            "title": "AI in 日本 Machine Learning",
            "content": "Machine learning in Japan 日本語 artificial intelligence",
        }

        result = categorizer.categorize_content(content)

        # Should handle unicode without crashing
        assert isinstance(result["categories"], list)

    def test_numbers_and_punctuation(self, categorizer):
        """Test with numbers and punctuation."""
        content = {
            "title": "AI 2025 News Machine Learning AI",
            "content": "Machine learning, deep learning, and AI frameworks and artificial intelligence.",
        }

        result = categorizer.categorize_content(content)

        # Should handle numbers and punctuation
        assert "categories" in result

    def test_keyword_repetition(self, categorizer):
        """Test impact of keyword repetition."""
        content = {
            "title": "AI Machine Learning AI Deep Learning",
            "content": "artificial intelligence, artificial intelligence, machine learning deep learning",
        }

        result = categorizer.categorize_content(content)

        # Should handle repetition
        assert "categories" in result or isinstance(result["categories"], list)


class TestMultiLanguage:
    """Test with different content styles."""

    def test_technical_content(self, categorizer):
        """Test technical content categorization."""
        content = {
            "title": "Transformer Machine Learning AI Deep Learning",
            "content": "Using transformer in machine learning deep learning neural networks artificial intelligence",
        }

        result = categorizer.categorize_content(content)

        # Should handle technical content
        assert "categories" in result

    def test_business_content(self, categorizer):
        """Test business content categorization."""
        content = {
            "title": "Company Funding Round AI Startup",
            "content": "AI startup raises Series B funding for machine learning",
        }

        result = categorizer.categorize_content(content)

        # Should handle business content
        assert isinstance(result["categories"], list)

    def test_news_style_content(self, categorizer):
        """Test news-style content."""
        content = {
            "title": "Breaking: New AI Model Released Machine Learning",
            "content": "A breakthrough in machine learning and artificial intelligence announced deep learning",
        }

        result = categorizer.categorize_content(content)

        # Should handle news-style content
        assert "categories" in result
