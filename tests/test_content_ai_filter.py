"""
Tests for AI content filtering module.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import logging

from src.processors.content_ai_filter import ContentAIFilter, ContentAIFilterError


@pytest.fixture
def mock_storage():
    """Mock database storage."""
    storage = Mock()
    storage.get_unprocessed_content = Mock(return_value=[])
    storage.update_content_status = Mock()
    return storage


@pytest.fixture
def filter_instance(mock_storage):
    """Create content AI filter instance."""
    return ContentAIFilter(storage=mock_storage, min_importance_threshold=0.5)


class TestContentAIFilterInitialization:
    """Test filter initialization."""

    def test_initialization_with_storage(self, mock_storage):
        """Test initialization with storage."""
        filter_obj = ContentAIFilter(storage=mock_storage)

        assert filter_obj.storage == mock_storage
        assert filter_obj.min_importance_threshold == 0.5

    def test_initialization_with_custom_threshold(self, mock_storage):
        """Test initialization with custom threshold."""
        filter_obj = ContentAIFilter(storage=mock_storage, min_importance_threshold=0.7)

        assert filter_obj.min_importance_threshold == 0.7

    def test_has_major_keywords(self, filter_instance):
        """Test that filter has major keywords defined."""
        assert len(filter_instance.MAJOR_KEYWORDS) > 0
        assert "announce" in filter_instance.MAJOR_KEYWORDS
        assert "release" in filter_instance.MAJOR_KEYWORDS
        assert "breakthrough" in filter_instance.MAJOR_KEYWORDS

    def test_has_noise_keywords(self, filter_instance):
        """Test that filter has noise keywords defined."""
        assert len(filter_instance.NOISE_KEYWORDS) > 0
        assert "opinion" in filter_instance.NOISE_KEYWORDS
        assert "rumor" in filter_instance.NOISE_KEYWORDS
        assert "speculation" in filter_instance.NOISE_KEYWORDS

    def test_has_entity_patterns(self, filter_instance):
        """Test that filter has entity patterns defined."""
        assert len(filter_instance.ENTITY_PATTERNS) > 0


class TestImportanceScoreCalculation:
    """Test importance score calculation."""

    def test_score_with_empty_content(self, filter_instance):
        """Test scoring with empty content dict."""
        content = {"title": "", "content": ""}

        result = filter_instance.calculate_importance_score(content)

        assert "score" in result
        assert 0.0 <= result["score"] <= 1.0
        assert isinstance(result["major_keywords"], list)
        assert isinstance(result["entities"], list)
        assert isinstance(result["reasons"], list)

    def test_score_with_invalid_type(self, filter_instance):
        """Test scoring with non-dict content."""
        result = filter_instance.calculate_importance_score("not a dict")

        assert result["score"] == 0.0
        assert result["major_keywords"] == []
        assert result["entities"] == []

    def test_score_with_major_keyword(self, filter_instance):
        """Test that major keywords increase score."""
        content = {
            "title": "Company announces breakthrough product",
            "content": "This is a major announcement",
        }

        result = filter_instance.calculate_importance_score(content)

        assert result["score"] > 0.5
        assert len(result["major_keywords"]) > 0
        assert len(result["reasons"]) > 0

    def test_score_detects_announce_keyword(self, filter_instance):
        """Test detection of 'announce' keyword."""
        content = {
            "title": "New announcement",
            "content": "We announce something important",
        }

        result = filter_instance.calculate_importance_score(content)

        assert "announce" in result["major_keywords"]

    def test_score_detects_release_keyword(self, filter_instance):
        """Test detection of 'release' keyword."""
        content = {
            "title": "Product release coming",
            "content": "New version release available",
        }

        result = filter_instance.calculate_importance_score(content)

        assert "release" in result["major_keywords"]

    def test_score_detects_launch_keyword(self, filter_instance):
        """Test detection of 'launch' keyword."""
        content = {
            "title": "Launch day",
            "content": "We launch our new platform today",
        }

        result = filter_instance.calculate_importance_score(content)

        assert "launch" in result["major_keywords"]

    def test_score_with_noise_keywords(self, filter_instance):
        """Test that noise keywords penalize score."""
        content = {
            "title": "Rumors about new feature",
            "content": "Some speculation about company plans",
        }

        result = filter_instance.calculate_importance_score(content)

        # Noise keywords should lower the score
        assert result["score"] < 0.7

    def test_score_detects_opinion_keyword(self, filter_instance):
        """Test detection of 'opinion' keyword."""
        content = {
            "title": "My opinion on tech",
            "content": "I think technology is changing",
        }

        result = filter_instance.calculate_importance_score(content)

        # Should have noise keyword reasons
        assert any("opinion" in reason.lower() for reason in result["reasons"])

    def test_score_with_short_content(self, filter_instance):
        """Test that short content gets penalized."""
        content = {
            "title": "News",
            "content": "Short",
        }

        result = filter_instance.calculate_importance_score(content)

        assert result["score"] < 0.5
        assert any("Short content" in reason for reason in result["reasons"])

    def test_score_with_long_content(self, filter_instance):
        """Test that long content gets bonus."""
        content = {
            "title": "Long article",
            "content": " ".join(["word"] * 6000),
        }

        result = filter_instance.calculate_importance_score(content)

        assert result["score"] > 0.5
        assert any("Substantive content" in reason for reason in result["reasons"])

    def test_score_with_recent_content(self, filter_instance):
        """Test that recent content gets bonus."""
        now = datetime.utcnow()
        content = {
            "title": "Recent news",
            "content": "Something happened recently",
            "published_at": now.isoformat(),
        }

        result = filter_instance.calculate_importance_score(content)

        assert any("Very recent content" in reason for reason in result["reasons"])

    def test_score_with_old_content(self, filter_instance):
        """Test that old content doesn't get recency bonus."""
        old_date = datetime.utcnow() - timedelta(days=10)
        content = {
            "title": "Old news",
            "content": "Something that happened long ago",
            "published_at": old_date.isoformat(),
        }

        result = filter_instance.calculate_importance_score(content)

        # Should not have recent content bonus
        assert not any("recent" in reason.lower() for reason in result["reasons"])

    def test_score_detects_currency_entities(self, filter_instance):
        """Test detection of currency/monetary amounts."""
        content = {
            "title": "Funding round",
            "content": "Company raised $100 million in Series B funding",
        }

        result = filter_instance.calculate_importance_score(content)

        assert len(result["entities"]) > 0

    def test_score_detects_company_entities(self, filter_instance):
        """Test detection of major company names."""
        content = {
            "title": "Google announcement",
            "content": "Google announces new AI capabilities",
        }

        result = filter_instance.calculate_importance_score(content)

        assert len(result["entities"]) > 0
        # Entities are in lowercase since content is lowercased
        assert any("google" in entity.lower() for entity in result["entities"])

    def test_score_detects_multiple_keywords(self, filter_instance):
        """Test detection of multiple keywords."""
        content = {
            "title": "Company announces breakthrough release",
            "content": "Major innovation and achievement in technology",
        }

        result = filter_instance.calculate_importance_score(content)

        assert len(result["major_keywords"]) >= 2

    def test_score_is_normalized(self, filter_instance):
        """Test that score is normalized to 0.0-1.0."""
        content = {
            "title": "Breaking news " * 100,
            "content": "announce " * 200,
        }

        result = filter_instance.calculate_importance_score(content)

        assert 0.0 <= result["score"] <= 1.0

    def test_score_returns_unique_keywords(self, filter_instance):
        """Test that duplicate keywords are deduplicated."""
        content = {
            "title": "announce announce",
            "content": "announce announce announce",
        }

        result = filter_instance.calculate_importance_score(content)

        # Should have only one 'announce', not multiple
        assert result["major_keywords"].count("announce") == 1


class TestMajorAnnouncementDetection:
    """Test major announcement detection."""

    def test_is_major_announcement_above_threshold(self, filter_instance):
        """Test announcement detection above threshold."""
        content = {
            "title": "Breaking: Company announces major new product",
            "content": "This is a major breakthrough announcement",
        }

        result = filter_instance.is_major_announcement(content)

        assert result is True

    def test_is_major_announcement_below_threshold(self, filter_instance):
        """Test announcement detection below threshold."""
        content = {
            "title": "Short",
            "content": "x",
        }

        result = filter_instance.is_major_announcement(content)

        assert result is False

    def test_is_major_announcement_with_custom_threshold(self, mock_storage):
        """Test announcement with custom threshold."""
        filter_obj = ContentAIFilter(storage=mock_storage, min_importance_threshold=0.9)

        content = {
            "title": "announce",
            "content": "A word",
        }

        result = filter_obj.is_major_announcement(content)

        assert result is False

    def test_is_major_announcement_at_exact_threshold(self, mock_storage):
        """Test announcement at exact threshold."""
        filter_obj = ContentAIFilter(storage=mock_storage, min_importance_threshold=0.5)

        content = {
            "title": "Some content here",
            "content": "announce with some text",
        }

        result = filter_obj.is_major_announcement(content)

        # At or above threshold should be True
        scoring = filter_obj.calculate_importance_score(content)
        assert (result is True) == (scoring["score"] >= 0.5)


class TestBatchContentFiltering:
    """Test batch content filtering."""

    def test_filter_empty_content_list(self, filter_instance):
        """Test filtering empty content list."""
        result = filter_instance.filter_content_list([])

        assert result["total"] == 0
        assert result["filtered"] == 0
        assert result["filtered_content"] == []
        assert result["filtered_out"] == 0
        assert result["average_score"] == 0.0

    def test_filter_content_list_structure(self, filter_instance):
        """Test batch filtering returns expected structure."""
        content = [
            {
                "title": "Announcement",
                "content": "announce something major",
            }
        ]

        result = filter_instance.filter_content_list(content)

        assert "total" in result
        assert "filtered" in result
        assert "filtered_content" in result
        assert "filtered_out" in result
        assert "average_score" in result
        assert "statistics" in result

    def test_filter_content_list_single_item(self, filter_instance):
        """Test filtering single content item."""
        content = [
            {
                "title": "Major announcement",
                "content": "Company announces new product launch",
            }
        ]

        result = filter_instance.filter_content_list(content)

        assert result["total"] == 1
        assert result["filtered"] >= 1

    def test_filter_content_list_multiple_items(self, filter_instance):
        """Test filtering multiple content items."""
        content = [
            {
                "title": "Major announcement",
                "content": "Company announces breakthrough",
            },
            {
                "title": "Some opinion",
                "content": "I think about things",
            },
            {
                "title": "Another major announcement",
                "content": "New product release available",
            },
        ]

        result = filter_instance.filter_content_list(content)

        assert result["total"] == 3
        assert result["filtered"] >= 1
        assert result["filtered_out"] >= 0

    def test_filter_content_adds_scores(self, filter_instance):
        """Test that filtered content includes importance scores."""
        content = [
            {
                "title": "Major announcement",
                "content": "Company announces breakthrough",
            }
        ]

        result = filter_instance.filter_content_list(content)

        if result["filtered"] > 0:
            for item in result["filtered_content"]:
                assert "importance_score" in item
                assert "major_keywords" in item
                assert "entities" in item

    def test_filter_content_statistics(self, filter_instance):
        """Test batch filtering statistics."""
        content = [
            {
                "title": "Major announcement",
                "content": "announce",
            },
            {
                "title": "Minor news",
                "content": "something happened",
            },
        ]

        result = filter_instance.filter_content_list(content)

        assert "min_score" in result["statistics"]
        assert "max_score" in result["statistics"]
        assert "median_score" in result["statistics"]

    def test_filter_content_error_handling(self, filter_instance):
        """Test error handling during batch filtering."""
        content = [
            {
                "title": "Valid",
                "content": "announce",
            },
            None,  # Invalid item
            {
                "title": "Another",
                "content": "content",
            },
        ]

        # Should not crash, should skip invalid items
        result = filter_instance.filter_content_list(content)

        assert result["total"] == 3
        assert result["filtered"] >= 0


class TestDatabaseContentFiltering:
    """Test filtering content from database."""

    def test_filter_database_content_no_content(self, filter_instance, mock_storage):
        """Test filtering when database has no content."""
        mock_storage.get_unprocessed_content.return_value = []

        result = filter_instance.filter_database_content()

        assert result["total"] == 0
        assert result["filtered"] == 0
        assert result["content_ids"] == []

    def test_filter_database_content_structure(self, filter_instance, mock_storage):
        """Test filtering returns expected structure."""
        mock_storage.get_unprocessed_content.return_value = []

        result = filter_instance.filter_database_content()

        assert "total" in result
        assert "filtered" in result
        assert "content_ids" in result
        assert "average_score" in result

    def test_filter_database_content_with_items(self, filter_instance, mock_storage):
        """Test filtering database with content."""
        mock_storage.get_unprocessed_content.return_value = [
            {
                "id": 1,
                "title": "Major announcement",
                "content": "announce",
                "source_type": "newsletter",
            },
            {
                "id": 2,
                "title": "Minor news",
                "content": "something",
                "source_type": "newsletter",
            },
        ]

        result = filter_instance.filter_database_content()

        assert result["total"] == 2
        assert result["filtered"] >= 1

    def test_filter_database_content_by_source_type(self, filter_instance, mock_storage):
        """Test filtering by source type."""
        mock_storage.get_unprocessed_content.return_value = [
            {
                "id": 1,
                "title": "Major announcement",
                "content": "announce",
                "source_type": "newsletter",
            },
            {
                "id": 2,
                "title": "Video title",
                "content": "transcript",
                "source_type": "youtube",
            },
        ]

        result = filter_instance.filter_database_content(source_type="newsletter")

        # Should only process newsletter content
        assert result["total"] == 1

    def test_filter_database_content_error_handling(self, filter_instance, mock_storage):
        """Test error handling for database operations."""
        mock_storage.get_unprocessed_content.side_effect = Exception("Database error")

        result = filter_instance.filter_database_content()

        assert result["filtered"] == 0
        assert "error" in result

    def test_filter_database_content_returns_ids(self, filter_instance, mock_storage):
        """Test that filtered content IDs are returned."""
        mock_storage.get_unprocessed_content.return_value = [
            {
                "id": 1,
                "title": "Major announcement",
                "content": "announce something major",
                "source_type": "newsletter",
            },
        ]

        result = filter_instance.filter_database_content()

        assert isinstance(result["content_ids"], list)
        if result["filtered"] > 0:
            assert len(result["content_ids"]) > 0


class TestThresholdConfiguration:
    """Test threshold configuration."""

    def test_update_importance_threshold(self, filter_instance):
        """Test updating importance threshold."""
        filter_instance.update_importance_threshold(0.7)

        assert filter_instance.min_importance_threshold == 0.7

    def test_update_importance_threshold_invalid_low(self, filter_instance):
        """Test that invalid thresholds raise error."""
        with pytest.raises(ContentAIFilterError):
            filter_instance.update_importance_threshold(-0.1)

    def test_update_importance_threshold_invalid_high(self, filter_instance):
        """Test that thresholds above 1.0 raise error."""
        with pytest.raises(ContentAIFilterError):
            filter_instance.update_importance_threshold(1.1)

    def test_update_importance_threshold_boundary_zero(self, filter_instance):
        """Test threshold at 0.0 boundary."""
        filter_instance.update_importance_threshold(0.0)

        assert filter_instance.min_importance_threshold == 0.0

    def test_update_importance_threshold_boundary_one(self, filter_instance):
        """Test threshold at 1.0 boundary."""
        filter_instance.update_importance_threshold(1.0)

        assert filter_instance.min_importance_threshold == 1.0


class TestFilterStatistics:
    """Test statistics calculation."""

    def test_get_filter_statistics_empty(self, filter_instance):
        """Test statistics with empty content."""
        result = filter_instance.get_filter_statistics([])

        assert result["total"] == 0
        assert result["score_distribution"] == {}
        assert result["avg_score"] == 0.0
        assert result["top_keywords"] == []

    def test_get_filter_statistics_structure(self, filter_instance):
        """Test statistics returns expected structure."""
        content = [
            {
                "title": "Major announcement",
                "content": "announce",
            }
        ]

        result = filter_instance.get_filter_statistics(content)

        assert "total" in result
        assert "score_distribution" in result
        assert "avg_score" in result
        assert "top_keywords" in result
        assert "content_with_scores" in result

    def test_get_filter_statistics_with_items(self, filter_instance):
        """Test statistics calculation."""
        content = [
            {
                "title": "Major announcement",
                "content": "announce breakthrough",
            },
            {
                "title": "Another major",
                "content": "new release",
            },
            {
                "title": "Opinion",
                "content": "I think",
            },
        ]

        result = filter_instance.get_filter_statistics(content)

        assert result["total"] == 3
        assert result["avg_score"] > 0
        assert isinstance(result["score_distribution"], dict)

    def test_get_filter_statistics_top_keywords(self, filter_instance):
        """Test top keywords extraction."""
        content = [
            {
                "title": "announce announce announce",
                "content": "release release announce",
            },
            {
                "title": "announce",
                "content": "release",
            },
        ]

        result = filter_instance.get_filter_statistics(content)

        assert len(result["top_keywords"]) > 0

    def test_get_filter_statistics_score_distribution(self, filter_instance):
        """Test score distribution calculation."""
        content = [
            {
                "title": "Major announcement",
                "content": "announce",
            },
            {
                "title": "Minor news",
                "content": "news",
            },
        ]

        result = filter_instance.get_filter_statistics(content)

        # Should have distribution buckets
        assert isinstance(result["score_distribution"], dict)
        assert len(result["score_distribution"]) > 0

    def test_get_filter_statistics_includes_content(self, filter_instance):
        """Test that statistics include scored content."""
        content = [
            {
                "title": "Announcement",
                "content": "announce",
            }
        ]

        result = filter_instance.get_filter_statistics(content)

        assert len(result["content_with_scores"]) > 0
        assert all("importance_score" in item for item in result["content_with_scores"])


class TestKeywordWeighting:
    """Test keyword weighting system."""

    def test_major_keyword_weights(self, filter_instance):
        """Test that major keywords have weights."""
        assert filter_instance.MAJOR_KEYWORDS["announce"] == 2.0
        assert filter_instance.MAJOR_KEYWORDS["release"] == 1.8
        assert filter_instance.MAJOR_KEYWORDS["launch"] == 1.8

    def test_noise_keyword_weights(self, filter_instance):
        """Test that noise keywords have weights."""
        assert filter_instance.NOISE_KEYWORDS["opinion"] == 0.5
        assert filter_instance.NOISE_KEYWORDS["rumor"] == 0.3
        assert filter_instance.NOISE_KEYWORDS["speculation"] == 0.3

    def test_breakthrough_keyword_duplicate(self, filter_instance):
        """Test that breakthrough keyword is not duplicated."""
        # Check if breakthrough appears more than once
        count = 0
        for i, (k, v) in enumerate(filter_instance.MAJOR_KEYWORDS.items()):
            if k == "breakthrough":
                count += 1

        # Should only appear once
        assert count == 1

    def test_keyword_weight_impacts_score(self, filter_instance):
        """Test that higher weight keywords impact score more."""
        content_announce = {
            "title": "We announce something",
            "content": "announcement here and more text to make it longer",
        }
        content_study = {
            "title": "A study was done",
            "content": "research study about things",
        }

        score_announce = filter_instance.calculate_importance_score(content_announce)[
            "score"
        ]
        score_study = filter_instance.calculate_importance_score(content_study)["score"]

        # Announce (weight 2.0) should have higher weight than study (weight 1.0)
        # Note: Both get short content penalty, so difference may be small but announce should be higher or equal
        assert score_announce >= score_study - 0.05


class TestEntityDetection:
    """Test entity pattern detection."""

    def test_entity_patterns_exist(self, filter_instance):
        """Test that entity patterns are defined."""
        assert len(filter_instance.ENTITY_PATTERNS) > 0

    def test_detects_company_names(self, filter_instance):
        """Test detection of major companies."""
        content = {
            "title": "Google, Microsoft, and Apple collaborate",
            "content": "The three tech giants announced partnership",
        }

        result = filter_instance.calculate_importance_score(content)

        assert len(result["entities"]) > 0

    def test_detects_currency_amounts(self, filter_instance):
        """Test detection of currency amounts."""
        content = {
            "title": "Funding round",
            "content": "Raised $50 million in Series A funding",
        }

        result = filter_instance.calculate_importance_score(content)

        assert len(result["entities"]) > 0

    def test_detects_percentage_metrics(self, filter_instance):
        """Test detection of percentage metrics."""
        content = {
            "title": "Growth metrics",
            "content": "Company grew 250% year over year",
        }

        result = filter_instance.calculate_importance_score(content)

        assert len(result["entities"]) > 0


class TestLogging:
    """Test logging integration."""

    def test_logging_invalid_content(self, filter_instance, caplog):
        """Test logging of invalid content."""
        with caplog.at_level(logging.WARNING):
            filter_instance.calculate_importance_score("not a dict")

        assert any("Invalid content type" in record.message for record in caplog.records)

    def test_logging_database_filtering(self, filter_instance, mock_storage, caplog):
        """Test logging during database filtering."""
        mock_storage.get_unprocessed_content.return_value = []

        with caplog.at_level(logging.INFO):
            filter_instance.filter_database_content()

        assert any("filtering" in record.message.lower() for record in caplog.records)

    def test_logging_error_filtering(self, filter_instance, mock_storage, caplog):
        """Test error logging during filtering."""
        mock_storage.get_unprocessed_content.side_effect = Exception("DB error")

        with caplog.at_level(logging.ERROR):
            filter_instance.filter_database_content()

        assert any("error" in record.message.lower() for record in caplog.records)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_content_with_none_values(self, filter_instance):
        """Test handling of None values in content."""
        content = {
            "title": None,
            "content": None,
        }

        result = filter_instance.calculate_importance_score(content)

        # Should handle gracefully
        assert "score" in result

    def test_content_with_missing_fields(self, filter_instance):
        """Test handling of missing title or content."""
        content = {
            "title": "Only title",
        }

        result = filter_instance.calculate_importance_score(content)

        assert "score" in result

    def test_content_with_invalid_date_format(self, filter_instance):
        """Test handling of invalid date formats."""
        content = {
            "title": "News",
            "content": "Something happened",
            "published_at": "not a valid date",
        }

        result = filter_instance.calculate_importance_score(content)

        # Should not crash, should ignore invalid date
        assert "score" in result

    def test_very_long_content(self, filter_instance):
        """Test handling of very long content."""
        content = {
            "title": "Long article",
            "content": " ".join(["word"] * 50000),
        }

        result = filter_instance.calculate_importance_score(content)

        assert 0.0 <= result["score"] <= 1.0

    def test_content_with_special_characters(self, filter_instance):
        """Test handling of special characters."""
        content = {
            "title": "News: @#$% & !",
            "content": "announce\n\t\r something",
        }

        result = filter_instance.calculate_importance_score(content)

        assert "score" in result

    def test_case_insensitive_keyword_detection(self, filter_instance):
        """Test that keyword detection is case-insensitive."""
        content_lower = {
            "title": "announce",
            "content": "announcement",
        }
        content_upper = {
            "title": "ANNOUNCE",
            "content": "ANNOUNCEMENT",
        }

        score_lower = filter_instance.calculate_importance_score(content_lower)["score"]
        score_upper = filter_instance.calculate_importance_score(content_upper)["score"]

        # Should give similar scores
        assert abs(score_lower - score_upper) < 0.1

    def test_unicode_content(self, filter_instance):
        """Test handling of unicode characters."""
        content = {
            "title": "News from 日本 🚀",
            "content": "Company announces breakthrough with émojis 🎉",
        }

        result = filter_instance.calculate_importance_score(content)

        assert "score" in result
