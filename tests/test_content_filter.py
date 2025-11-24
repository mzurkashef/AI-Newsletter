"""
Tests for content filtering module.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import logging

from src.collectors.content_filter import (
    ContentFilter,
    ContentFilterError,
)
from src.database.models import RawContent


@pytest.fixture
def mock_storage():
    """Mock database storage."""
    storage = Mock()
    storage.get_unprocessed_content = Mock(return_value=[])
    return storage


@pytest.fixture
def content_filter(mock_storage):
    """Create content filter instance with mock storage."""
    return ContentFilter(storage=mock_storage, window_days=7, min_confidence=0.0)


class TestContentFilterTimeWindow:
    """Test time window validation."""

    def test_is_within_window_recent_content(self, content_filter):
        """Test that recent content is within window."""
        now = datetime.utcnow()
        result = content_filter.is_within_window(now)
        assert result is True

    def test_is_within_window_boundary(self, content_filter):
        """Test boundary condition at exactly window_days ago."""
        cutoff = datetime.utcnow() - timedelta(days=7)
        result = content_filter.is_within_window(cutoff)
        assert result is True

    def test_is_within_window_just_outside(self, content_filter):
        """Test content just outside window."""
        outside = datetime.utcnow() - timedelta(days=7, seconds=1)
        result = content_filter.is_within_window(outside)
        assert result is False

    def test_is_within_window_old_content(self, content_filter):
        """Test old content outside window."""
        old = datetime.utcnow() - timedelta(days=30)
        result = content_filter.is_within_window(old)
        assert result is False

    def test_is_within_window_custom_cutoff(self, content_filter):
        """Test with custom cutoff date."""
        now = datetime.utcnow()
        custom_cutoff = now - timedelta(days=3)

        # Within custom window
        recent = now - timedelta(days=1)
        assert content_filter.is_within_window(recent, custom_cutoff) is True

        # Outside custom window
        old = now - timedelta(days=5)
        assert content_filter.is_within_window(old, custom_cutoff) is False

    def test_is_within_window_invalid_type(self, content_filter, caplog):
        """Test with invalid date type."""
        with caplog.at_level(logging.WARNING):
            result = content_filter.is_within_window("not-a-date")
        assert result is False
        assert len(caplog.records) > 0

    def test_is_within_window_future_content(self, content_filter):
        """Test future content."""
        future = datetime.utcnow() + timedelta(days=1)
        result = content_filter.is_within_window(future)
        assert result is True


class TestContentFilterCriteria:
    """Test content inclusion criteria."""

    def test_should_include_content_all_valid(self, content_filter):
        """Test inclusion when all criteria pass."""
        now = datetime.utcnow()
        result = content_filter.should_include_content(
            published_at=now,
            confidence=0.8,
            source_type="newsletter"
        )
        assert result is True

    def test_should_include_content_outside_window(self, content_filter):
        """Test exclusion when outside time window."""
        old = datetime.utcnow() - timedelta(days=30)
        result = content_filter.should_include_content(
            published_at=old,
            confidence=0.8
        )
        assert result is False

    def test_should_include_content_low_confidence(self, content_filter):
        """Test exclusion when confidence below threshold."""
        content_filter.min_confidence = 0.5
        now = datetime.utcnow()
        result = content_filter.should_include_content(
            published_at=now,
            confidence=0.3
        )
        assert result is False

    def test_should_include_content_at_confidence_boundary(self, content_filter):
        """Test at exact confidence threshold."""
        content_filter.min_confidence = 0.5
        now = datetime.utcnow()

        # Exactly at threshold
        result = content_filter.should_include_content(
            published_at=now,
            confidence=0.5
        )
        assert result is True

        # Just below threshold
        result = content_filter.should_include_content(
            published_at=now,
            confidence=0.49999
        )
        assert result is False

    def test_should_include_content_zero_confidence(self, content_filter):
        """Test with zero confidence."""
        content_filter.min_confidence = 0.0
        now = datetime.utcnow()
        result = content_filter.should_include_content(
            published_at=now,
            confidence=0.0
        )
        assert result is True

    def test_should_include_content_high_confidence(self, content_filter):
        """Test with confidence of 1.0."""
        now = datetime.utcnow()
        result = content_filter.should_include_content(
            published_at=now,
            confidence=1.0
        )
        assert result is True


class TestContentFilterBatchList:
    """Test batch list filtering."""

    def test_filter_content_list_empty(self, content_filter):
        """Test filtering empty list."""
        result = content_filter.filter_content_list([])

        assert result["total"] == 0
        assert result["included"] == 0
        assert result["excluded"] == 0
        assert result["filtered"] == []
        assert "exclusion_reasons" in result

    def test_filter_content_list_all_included(self, content_filter):
        """Test when all content passes filters."""
        now = datetime.utcnow()
        content_list = [
            {
                "id": 1,
                "published_at": now.isoformat(),
                "confidence": 0.8,
                "title": "Test 1",
                "content": "Content 1"
            },
            {
                "id": 2,
                "published_at": now.isoformat(),
                "confidence": 0.9,
                "title": "Test 2",
                "content": "Content 2"
            }
        ]

        result = content_filter.filter_content_list(content_list)

        assert result["total"] == 2
        assert result["included"] == 2
        assert result["excluded"] == 0
        assert len(result["filtered"]) == 2

    def test_filter_content_list_all_excluded(self, content_filter):
        """Test when all content is excluded."""
        old = datetime.utcnow() - timedelta(days=30)
        content_list = [
            {
                "id": 1,
                "published_at": old.isoformat(),
                "confidence": 0.8,
                "title": "Old 1",
                "content": "Content 1"
            },
            {
                "id": 2,
                "published_at": old.isoformat(),
                "confidence": 0.9,
                "title": "Old 2",
                "content": "Content 2"
            }
        ]

        result = content_filter.filter_content_list(content_list)

        assert result["total"] == 2
        assert result["included"] == 0
        assert result["excluded"] == 2
        assert len(result["filtered"]) == 0
        assert result["exclusion_reasons"]["outside_window"] == 2

    def test_filter_content_list_mixed(self, content_filter):
        """Test with mixed content (some pass, some excluded)."""
        now = datetime.utcnow()
        old = datetime.utcnow() - timedelta(days=30)

        content_filter.min_confidence = 0.7

        content_list = [
            {
                "id": 1,
                "published_at": now.isoformat(),
                "confidence": 0.8,
                "title": "Recent High Confidence",
                "content": "Content 1"
            },
            {
                "id": 2,
                "published_at": old.isoformat(),
                "confidence": 0.9,
                "title": "Old High Confidence",
                "content": "Content 2"
            },
            {
                "id": 3,
                "published_at": now.isoformat(),
                "confidence": 0.5,
                "title": "Recent Low Confidence",
                "content": "Content 3"
            },
            {
                "id": 4,
                "published_at": now.isoformat(),
                "confidence": 0.9,
                "title": "Recent Very High Confidence",
                "content": "Content 4"
            }
        ]

        result = content_filter.filter_content_list(content_list)

        assert result["total"] == 4
        assert result["included"] == 2  # Items 1 and 4
        assert result["excluded"] == 2  # Items 2 and 3
        assert result["exclusion_reasons"]["outside_window"] == 1  # Item 2
        assert result["exclusion_reasons"]["low_confidence"] == 1  # Item 3

    def test_filter_content_list_missing_date(self, content_filter):
        """Test with missing published_at."""
        now = datetime.utcnow()
        content_list = [
            {
                "id": 1,
                "published_at": now.isoformat(),
                "confidence": 0.8,
                "title": "Valid",
                "content": "Content 1"
            },
            {
                "id": 2,
                "published_at": None,
                "confidence": 0.8,
                "title": "Missing Date",
                "content": "Content 2"
            }
        ]

        result = content_filter.filter_content_list(content_list)

        assert result["total"] == 2
        assert result["included"] == 1
        assert result["excluded"] == 1
        assert result["exclusion_reasons"]["invalid_date"] == 1

    def test_filter_content_list_invalid_date_format(self, content_filter):
        """Test with invalid date format."""
        now = datetime.utcnow()
        content_list = [
            {
                "id": 1,
                "published_at": now.isoformat(),
                "confidence": 0.8,
                "title": "Valid",
                "content": "Content 1"
            },
            {
                "id": 2,
                "published_at": "not-a-date",
                "confidence": 0.8,
                "title": "Invalid Date",
                "content": "Content 2"
            }
        ]

        result = content_filter.filter_content_list(content_list)

        assert result["total"] == 2
        assert result["included"] == 1
        assert result["excluded"] == 1
        assert result["exclusion_reasons"]["invalid_date"] == 1

    def test_filter_content_list_datetime_object(self, content_filter):
        """Test with datetime objects instead of strings."""
        now = datetime.utcnow()
        content_list = [
            {
                "id": 1,
                "published_at": now,  # datetime object
                "confidence": 0.8,
                "title": "Valid",
                "content": "Content 1"
            }
        ]

        result = content_filter.filter_content_list(content_list)

        assert result["total"] == 1
        assert result["included"] == 1
        assert result["excluded"] == 0

    def test_filter_content_list_missing_confidence(self, content_filter):
        """Test with missing confidence (defaults to 1.0)."""
        now = datetime.utcnow()
        content_filter.min_confidence = 0.5
        content_list = [
            {
                "id": 1,
                "published_at": now.isoformat(),
                "title": "No Confidence Field",
                "content": "Content 1"
                # confidence is missing
            }
        ]

        result = content_filter.filter_content_list(content_list)

        assert result["total"] == 1
        assert result["included"] == 1  # Defaults to 1.0, which is >= 0.5

    def test_filter_content_list_string_confidence(self, content_filter):
        """Test with confidence as string."""
        now = datetime.utcnow()
        content_filter.min_confidence = 0.5
        content_list = [
            {
                "id": 1,
                "published_at": now.isoformat(),
                "confidence": "0.8",  # String instead of float
                "title": "String Confidence",
                "content": "Content 1"
            }
        ]

        result = content_filter.filter_content_list(content_list)

        assert result["total"] == 1
        assert result["included"] == 1

    def test_filter_content_list_statistics(self, content_filter):
        """Test that statistics are calculated correctly."""
        now = datetime.utcnow()
        old = datetime.utcnow() - timedelta(days=30)

        content_filter.min_confidence = 0.7

        content_list = [
            {"id": 1, "published_at": now.isoformat(), "confidence": 0.9},
            {"id": 2, "published_at": now.isoformat(), "confidence": 0.8},
            {"id": 3, "published_at": now.isoformat(), "confidence": 0.5},
            {"id": 4, "published_at": old.isoformat(), "confidence": 0.9},
            {"id": 5, "published_at": None, "confidence": 0.9},
        ]

        result = content_filter.filter_content_list(content_list)

        assert result["total"] == 5
        assert result["included"] == 2
        assert result["excluded"] == 3
        reasons = result["exclusion_reasons"]
        assert reasons["low_confidence"] == 1
        assert reasons["outside_window"] == 1
        assert reasons["invalid_date"] == 1


class TestContentFilterDatabase:
    """Test database filtering."""

    def test_filter_recent_content_empty_database(self, content_filter, mock_storage):
        """Test filtering when database is empty."""
        mock_storage.get_unprocessed_content.return_value = []

        result = content_filter.filter_recent_content()

        assert result["total"] == 0
        assert result["included"] == 0
        assert result["excluded"] == 0
        assert result["content_ids"] == []

    def test_filter_recent_content_all_recent(self, content_filter, mock_storage):
        """Test filtering when all content is recent."""
        now = datetime.utcnow()
        unprocessed = [
            {
                "id": 1,
                "published_at": now.isoformat(),
                "source_type": "newsletter",
                "confidence": 0.8,
                "title": "Test 1"
            },
            {
                "id": 2,
                "published_at": now.isoformat(),
                "source_type": "youtube",
                "confidence": 0.9,
                "title": "Test 2"
            }
        ]
        mock_storage.get_unprocessed_content.return_value = unprocessed

        result = content_filter.filter_recent_content()

        assert result["total"] == 2
        assert result["included"] == 2
        assert result["excluded"] == 0
        assert result["content_ids"] == [1, 2]

    def test_filter_recent_content_all_old(self, content_filter, mock_storage):
        """Test filtering when all content is old."""
        old = datetime.utcnow() - timedelta(days=30)
        unprocessed = [
            {
                "id": 1,
                "published_at": old.isoformat(),
                "source_type": "newsletter",
                "confidence": 0.8,
                "title": "Old 1"
            },
            {
                "id": 2,
                "published_at": old.isoformat(),
                "source_type": "youtube",
                "confidence": 0.9,
                "title": "Old 2"
            }
        ]
        mock_storage.get_unprocessed_content.return_value = unprocessed

        result = content_filter.filter_recent_content()

        assert result["total"] == 2
        assert result["included"] == 0
        assert result["excluded"] == 2
        assert result["content_ids"] == []

    def test_filter_recent_content_by_source_type(self, content_filter, mock_storage):
        """Test filtering by source type."""
        now = datetime.utcnow()
        unprocessed = [
            {
                "id": 1,
                "published_at": now.isoformat(),
                "source_type": "newsletter",
                "confidence": 0.8
            },
            {
                "id": 2,
                "published_at": now.isoformat(),
                "source_type": "youtube",
                "confidence": 0.9
            },
            {
                "id": 3,
                "published_at": now.isoformat(),
                "source_type": "newsletter",
                "confidence": 0.7
            }
        ]
        mock_storage.get_unprocessed_content.return_value = unprocessed

        result = content_filter.filter_recent_content(source_type="newsletter")

        assert result["total"] == 3
        assert result["included"] == 2  # Items 1 and 3
        assert result["excluded"] == 1  # Item 2 (wrong source type)
        assert result["content_ids"] == [1, 3]
        assert result["exclusion_reasons"]["wrong_source_type"] == 1

    def test_filter_recent_content_mixed_content(self, content_filter, mock_storage):
        """Test filtering with mixed content."""
        now = datetime.utcnow()
        old = datetime.utcnow() - timedelta(days=30)

        content_filter.min_confidence = 0.7

        unprocessed = [
            {
                "id": 1,
                "published_at": now.isoformat(),
                "source_type": "newsletter",
                "confidence": 0.8
            },
            {
                "id": 2,
                "published_at": old.isoformat(),
                "source_type": "newsletter",
                "confidence": 0.9
            },
            {
                "id": 3,
                "published_at": now.isoformat(),
                "source_type": "newsletter",
                "confidence": 0.5
            },
            {
                "id": 4,
                "published_at": now.isoformat(),
                "source_type": "youtube",
                "confidence": 0.9
            }
        ]
        mock_storage.get_unprocessed_content.return_value = unprocessed

        result = content_filter.filter_recent_content(source_type="newsletter")

        assert result["total"] == 4
        assert result["included"] == 1  # Item 1 only
        assert result["excluded"] == 3
        assert result["content_ids"] == [1]

    def test_filter_recent_content_error_handling(self, content_filter, mock_storage):
        """Test error handling when database query fails."""
        mock_storage.get_unprocessed_content.side_effect = Exception("Database error")

        result = content_filter.filter_recent_content()

        assert result["total"] == 0
        assert result["included"] == 0
        assert result["excluded"] == 0
        assert result["content_ids"] == []
        assert "error" in result["exclusion_reasons"]


class TestContentFilterConfiguration:
    """Test filter configuration and updates."""

    def test_update_window_days_valid(self, content_filter):
        """Test updating window days with valid value."""
        content_filter.update_window_days(14)

        assert content_filter.window_days == 14

    def test_update_window_days_minimum(self, content_filter):
        """Test updating to minimum window (1 day)."""
        content_filter.update_window_days(1)

        assert content_filter.window_days == 1

    def test_update_window_days_invalid_zero(self, content_filter):
        """Test that zero days is rejected."""
        with pytest.raises(ContentFilterError):
            content_filter.update_window_days(0)

    def test_update_window_days_invalid_negative(self, content_filter):
        """Test that negative days are rejected."""
        with pytest.raises(ContentFilterError):
            content_filter.update_window_days(-1)

    def test_update_min_confidence_valid(self, content_filter):
        """Test updating minimum confidence with valid value."""
        content_filter.update_min_confidence(0.5)

        assert content_filter.min_confidence == 0.5

    def test_update_min_confidence_boundaries(self, content_filter):
        """Test confidence boundary values."""
        content_filter.update_min_confidence(0.0)
        assert content_filter.min_confidence == 0.0

        content_filter.update_min_confidence(1.0)
        assert content_filter.min_confidence == 1.0

    def test_update_min_confidence_invalid_negative(self, content_filter):
        """Test that negative confidence is rejected."""
        with pytest.raises(ContentFilterError):
            content_filter.update_min_confidence(-0.1)

    def test_update_min_confidence_invalid_over_one(self, content_filter):
        """Test that confidence > 1.0 is rejected."""
        with pytest.raises(ContentFilterError):
            content_filter.update_min_confidence(1.1)


class TestContentFilterWindowDates:
    """Test window date calculations."""

    def test_get_window_dates_structure(self, content_filter):
        """Test that window dates have expected structure."""
        dates = content_filter.get_window_dates()

        assert "cutoff_date" in dates
        assert "current_date" in dates
        assert "window_days" in dates

    def test_get_window_dates_correct_window(self, content_filter):
        """Test that cutoff is exactly window_days ago."""
        dates = content_filter.get_window_dates()

        current = dates["current_date"]
        cutoff = dates["cutoff_date"]
        diff = current - cutoff

        # Should be approximately 7 days
        assert diff.days == 7

    def test_get_window_dates_custom_window(self, content_filter):
        """Test window dates with custom window size."""
        content_filter.update_window_days(14)
        dates = content_filter.get_window_dates()

        current = dates["current_date"]
        cutoff = dates["cutoff_date"]
        diff = current - cutoff

        assert diff.days == 14
        assert dates["window_days"] == 14

    def test_get_window_dates_one_day(self, content_filter):
        """Test window dates with 1-day window."""
        content_filter.update_window_days(1)
        dates = content_filter.get_window_dates()

        current = dates["current_date"]
        cutoff = dates["cutoff_date"]
        diff = current - cutoff

        assert diff.days == 1


class TestContentFilterIntegration:
    """Integration tests."""

    def test_filter_workflow_complete(self, content_filter, mock_storage):
        """Test complete filtering workflow."""
        now = datetime.utcnow()
        old = datetime.utcnow() - timedelta(days=30)

        # Setup storage with mixed content
        unprocessed = [
            {
                "id": 1,
                "published_at": now.isoformat(),
                "source_type": "newsletter",
                "confidence": 0.8,
                "title": "Recent Newsletter"
            },
            {
                "id": 2,
                "published_at": old.isoformat(),
                "source_type": "youtube",
                "confidence": 0.9,
                "title": "Old YouTube"
            },
            {
                "id": 3,
                "published_at": now.isoformat(),
                "source_type": "newsletter",
                "confidence": 0.9,
                "title": "Recent Newsletter 2"
            }
        ]
        mock_storage.get_unprocessed_content.return_value = unprocessed

        # First filter: get all recent content
        all_recent = content_filter.filter_recent_content()
        assert all_recent["included"] == 2
        assert 1 in all_recent["content_ids"]
        assert 3 in all_recent["content_ids"]

        # Second filter: get only newsletters
        newsletters = content_filter.filter_recent_content(source_type="newsletter")
        assert newsletters["included"] == 2
        assert newsletters["content_ids"] == [1, 3]

        # Third filter: increase confidence threshold
        content_filter.update_min_confidence(0.85)
        mock_storage.get_unprocessed_content.return_value = unprocessed
        high_confidence = content_filter.filter_recent_content(source_type="newsletter")
        assert high_confidence["included"] == 1  # Only item 3 (0.9)
        assert high_confidence["content_ids"] == [3]

    def test_filter_list_and_database_consistency(self, content_filter, mock_storage):
        """Test that list filtering matches database filtering."""
        now = datetime.utcnow()

        content_list = [
            {
                "id": 1,
                "published_at": now.isoformat(),
                "source_type": "newsletter",
                "confidence": 0.8,
                "title": "Test 1",
                "content": "Content 1"
            },
            {
                "id": 2,
                "published_at": now.isoformat(),
                "source_type": "newsletter",
                "confidence": 0.9,
                "title": "Test 2",
                "content": "Content 2"
            }
        ]

        # Filter as list
        list_result = content_filter.filter_content_list(content_list)

        # Filter from "database"
        mock_storage.get_unprocessed_content.return_value = content_list
        db_result = content_filter.filter_recent_content()

        # Should have same counts
        assert list_result["included"] == db_result["included"]
        assert list_result["excluded"] == db_result["excluded"]
        assert len(list_result["filtered"]) == len(db_result["content_ids"])

    def test_filter_configuration_persistence(self, content_filter):
        """Test that configuration changes persist."""
        # Change configuration
        content_filter.update_window_days(10)
        content_filter.update_min_confidence(0.6)

        # Get dates - should use new window
        dates = content_filter.get_window_dates()
        assert dates["window_days"] == 10

        # Filter should use new confidence
        now = datetime.utcnow()
        should_include = content_filter.should_include_content(
            published_at=now,
            confidence=0.5
        )
        assert should_include is False  # 0.5 < 0.6


class TestContentFilterLogging:
    """Test logging integration."""

    def test_filter_recent_content_logs_operation(self, content_filter, mock_storage, caplog):
        """Test that filtering operation is logged."""
        mock_storage.get_unprocessed_content.return_value = []

        with caplog.at_level(logging.INFO):
            content_filter.filter_recent_content()

        # Should log the operation
        assert len(caplog.records) > 0

    def test_update_window_logs_change(self, content_filter, caplog):
        """Test that window updates are logged."""
        with caplog.at_level(logging.INFO):
            content_filter.update_window_days(14)

        # Should log the change
        assert any("Updated time window" in record.message for record in caplog.records)

    def test_update_confidence_logs_change(self, content_filter, caplog):
        """Test that confidence updates are logged."""
        with caplog.at_level(logging.INFO):
            content_filter.update_min_confidence(0.5)

        # Should log the change
        assert any("Updated minimum confidence" in record.message for record in caplog.records)

    def test_invalid_type_logs_warning(self, content_filter, caplog):
        """Test that invalid types are logged as warnings."""
        with caplog.at_level(logging.WARNING):
            content_filter.is_within_window("not-a-date")

        # Should log warning about invalid type
        assert len(caplog.records) > 0
        assert any("Invalid published_at type" in record.message for record in caplog.records)
