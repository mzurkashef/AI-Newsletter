"""Test suite for delivery status tracking."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

from src.delivery.delivery_status_tracker import (
    DeliveryStatusTracker,
    DeliveryStatus,
    DeliveryRecord,
)
from src.database.storage import DatabaseStorage


class TestDeliveryRecord:
    """Test DeliveryRecord dataclass."""

    def test_create_record_success(self):
        """Test creating successful delivery record."""
        record = DeliveryRecord(
            newsletter_content="Newsletter text",
            delivered_at=datetime.utcnow().isoformat(),
            delivery_status=DeliveryStatus.SUCCESS,
            telegram_message_id="101,102",
            telegram_chat_id=987654321,
            message_count=2,
        )

        assert record.newsletter_content == "Newsletter text"
        assert record.delivery_status == DeliveryStatus.SUCCESS
        assert record.message_count == 2

    def test_create_record_failure(self):
        """Test creating failed delivery record."""
        record = DeliveryRecord(
            newsletter_content="Newsletter text",
            delivered_at=datetime.utcnow().isoformat(),
            delivery_status=DeliveryStatus.FAILURE,
            error_message="Network timeout",
        )

        assert record.delivery_status == DeliveryStatus.FAILURE
        assert record.error_message == "Network timeout"

    def test_record_to_dict(self):
        """Test converting record to dictionary."""
        record = DeliveryRecord(
            newsletter_content="Newsletter",
            delivered_at="2025-11-21T10:00:00",
            delivery_status=DeliveryStatus.SUCCESS,
            telegram_message_id="101",
            telegram_chat_id=987654321,
        )

        data = record.to_dict()

        assert data["newsletter_content"] == "Newsletter"
        assert data["delivery_status"] == DeliveryStatus.SUCCESS
        assert data["telegram_message_id"] == "101"


class TestDeliveryStatusTrackerInitialization:
    """Test DeliveryStatusTracker initialization."""

    def test_init_with_storage(self):
        """Test initialization with storage."""
        mock_storage = MagicMock()
        tracker = DeliveryStatusTracker(mock_storage)

        assert tracker.storage == mock_storage

    def test_init_without_storage(self):
        """Test initialization without storage fails."""
        with pytest.raises(ValueError):
            DeliveryStatusTracker(None)


class TestRecordDelivery:
    """Test recording delivery attempts."""

    def test_record_successful_delivery(self):
        """Test recording successful delivery."""
        mock_storage = MagicMock()
        tracker = DeliveryStatusTracker(mock_storage)

        result = tracker.record_delivery(
            newsletter_content="Newsletter",
            chat_id=987654321,
            status=DeliveryStatus.SUCCESS,
            message_ids=[101, 102],
        )

        assert result["success"] is True
        assert result["status"] == DeliveryStatus.SUCCESS
        assert result["message_count"] == 2
        mock_storage.insert.assert_called_once()

    def test_record_failed_delivery(self):
        """Test recording failed delivery."""
        mock_storage = MagicMock()
        tracker = DeliveryStatusTracker(mock_storage)

        result = tracker.record_delivery(
            newsletter_content="Newsletter",
            chat_id=987654321,
            status=DeliveryStatus.FAILURE,
            error_message="Network error",
        )

        assert result["success"] is True
        assert result["status"] == DeliveryStatus.FAILURE
        mock_storage.insert.assert_called_once()

    def test_record_partial_delivery(self):
        """Test recording partial delivery."""
        mock_storage = MagicMock()
        tracker = DeliveryStatusTracker(mock_storage)

        result = tracker.record_delivery(
            newsletter_content="Newsletter",
            chat_id=987654321,
            status=DeliveryStatus.PARTIAL,
            message_ids=[101],  # Some messages sent
            error_message="2 of 3 messages failed",
        )

        assert result["success"] is True
        assert result["status"] == DeliveryStatus.PARTIAL
        assert result["message_count"] == 1

    def test_record_empty_content(self):
        """Test recording with empty content fails."""
        mock_storage = MagicMock()
        tracker = DeliveryStatusTracker(mock_storage)

        with pytest.raises(ValueError):
            tracker.record_delivery(
                newsletter_content="",
                chat_id=987654321,
                status=DeliveryStatus.SUCCESS,
            )

    def test_record_invalid_chat_id(self):
        """Test recording with invalid chat ID fails."""
        mock_storage = MagicMock()
        tracker = DeliveryStatusTracker(mock_storage)

        with pytest.raises(ValueError):
            tracker.record_delivery(
                newsletter_content="Newsletter",
                chat_id="invalid",
                status=DeliveryStatus.SUCCESS,
            )

    def test_record_invalid_status(self):
        """Test recording with invalid status fails."""
        mock_storage = MagicMock()
        tracker = DeliveryStatusTracker(mock_storage)

        with pytest.raises(ValueError):
            tracker.record_delivery(
                newsletter_content="Newsletter",
                chat_id=987654321,
                status="invalid_status",
            )


class TestGetDeliveryHistory:
    """Test retrieving delivery history."""

    def test_get_all_history(self):
        """Test getting all delivery history."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = [
            [
                {
                    "id": 1,
                    "delivery_status": "success",
                    "delivered_at": "2025-11-21T10:00:00",
                },
                {
                    "id": 2,
                    "delivery_status": "failure",
                    "delivered_at": "2025-11-20T10:00:00",
                },
            ],
            [{"count": 2}],
        ]

        tracker = DeliveryStatusTracker(mock_storage)
        result = tracker.get_delivery_history()

        assert len(result["records"]) == 2
        assert result["total_count"] == 2
        assert result["limit"] == 100
        assert result["offset"] == 0

    def test_get_history_by_chat(self):
        """Test getting delivery history for specific chat."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = [
            [
                {
                    "id": 1,
                    "delivery_status": "success",
                    "telegram_chat_id": 987654321,
                }
            ],
            [{"count": 1}],
        ]

        tracker = DeliveryStatusTracker(mock_storage)
        result = tracker.get_delivery_history(chat_id=987654321)

        assert len(result["records"]) == 1
        assert result["total_count"] == 1

    def test_get_history_with_pagination(self):
        """Test getting history with pagination."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = [
            [{"id": i} for i in range(10)],
            [{"count": 50}],
        ]

        tracker = DeliveryStatusTracker(mock_storage)
        result = tracker.get_delivery_history(limit=10, offset=20)

        assert result["limit"] == 10
        assert result["offset"] == 20
        assert result["total_count"] == 50


class TestGetDeliveryStatistics:
    """Test calculating delivery statistics."""

    def test_get_statistics_all_success(self):
        """Test statistics when all deliveries successful."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = [
            [{"delivery_status": "success", "count": 10}],
            [{"total_messages": 20}],
        ]

        tracker = DeliveryStatusTracker(mock_storage)
        stats = tracker.get_delivery_statistics(days=30)

        assert stats["total_deliveries"] == 10
        assert stats["successful"] == 10
        assert stats["failures"] == 0
        assert stats["success_rate"] == 100.0

    def test_get_statistics_mixed(self):
        """Test statistics with mixed results."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = [
            [
                {"delivery_status": "success", "count": 8},
                {"delivery_status": "partial", "count": 1},
                {"delivery_status": "failure", "count": 1},
            ],
            [{"total_messages": 16}],
        ]

        tracker = DeliveryStatusTracker(mock_storage)
        stats = tracker.get_delivery_statistics(days=30)

        assert stats["total_deliveries"] == 10
        assert stats["successful"] == 8
        assert stats["partial"] == 1
        assert stats["failures"] == 1
        assert stats["success_rate"] == 85.0  # 8 + (1 * 0.5)

    def test_get_statistics_by_chat(self):
        """Test statistics for specific chat."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = [
            [{"delivery_status": "success", "count": 5}],
            [{"total_messages": 10}],
        ]

        tracker = DeliveryStatusTracker(mock_storage)
        stats = tracker.get_delivery_statistics(
            days=30, chat_id=987654321
        )

        assert stats["total_deliveries"] == 5


class TestGetFailures:
    """Test retrieving failures."""

    def test_get_recent_failures(self):
        """Test getting recent failures."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = [
            {
                "id": 1,
                "delivery_status": "failure",
                "error_message": "Network timeout",
            },
            {
                "id": 2,
                "delivery_status": "failure",
                "error_message": "Invalid chat ID",
            },
        ]

        tracker = DeliveryStatusTracker(mock_storage)
        result = tracker.get_failures(limit=50, days=30)

        assert len(result["failures"]) == 2
        assert result["count"] == 2
        assert result["period_days"] == 30

    def test_get_no_failures(self):
        """Test getting failures when none exist."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = []

        tracker = DeliveryStatusTracker(mock_storage)
        result = tracker.get_failures()

        assert len(result["failures"]) == 0
        assert result["count"] == 0


class TestGetRecentStatus:
    """Test getting recent status."""

    def test_get_recent_status(self):
        """Test getting recent delivery status."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = [
            {
                "id": 1,
                "delivery_status": "success",
                "delivered_at": "2025-11-21T10:00:00",
            },
            {
                "id": 2,
                "delivery_status": "success",
                "delivered_at": "2025-11-20T10:00:00",
            },
        ]

        tracker = DeliveryStatusTracker(mock_storage)
        result = tracker.get_recent_status(limit=10)

        assert result["count"] == 2
        assert result["latest_status"] == "success"
        assert result["latest_timestamp"] == "2025-11-21T10:00:00"

    def test_get_recent_status_by_chat(self):
        """Test getting recent status for chat."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = [
            {
                "id": 1,
                "delivery_status": "failure",
                "delivered_at": "2025-11-21T10:00:00",
            }
        ]

        tracker = DeliveryStatusTracker(mock_storage)
        result = tracker.get_recent_status(chat_id=987654321, limit=10)

        assert result["count"] == 1
        assert result["latest_status"] == "failure"


class TestCleanupOldRecords:
    """Test cleaning up old records."""

    def test_cleanup_dry_run(self):
        """Test cleanup dry-run mode."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = [{"count": 50}]

        tracker = DeliveryStatusTracker(mock_storage)
        result = tracker.cleanup_old_records(days=90, dry_run=True)

        assert result["success"] is True
        assert result["records_deleted"] == 50
        assert result["dry_run"] is True
        mock_storage.execute.assert_not_called()

    def test_cleanup_delete(self):
        """Test cleanup with actual deletion."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = [{"count": 50}]
        mock_storage.execute = MagicMock()

        tracker = DeliveryStatusTracker(mock_storage)
        result = tracker.cleanup_old_records(days=90, dry_run=False)

        assert result["success"] is True
        assert result["records_deleted"] == 50
        assert result["dry_run"] is False
        mock_storage.execute.assert_called_once()

    def test_cleanup_no_records(self):
        """Test cleanup when no old records exist."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = [{"count": 0}]

        tracker = DeliveryStatusTracker(mock_storage)
        result = tracker.cleanup_old_records(days=90, dry_run=False)

        assert result["success"] is True
        assert result["records_deleted"] == 0


class TestGetChatSummary:
    """Test getting chat delivery summary."""

    def test_get_chat_summary(self):
        """Test getting summary for specific chat."""
        mock_storage = MagicMock()

        # Mock multiple query results
        mock_storage.query.side_effect = [
            # Statistics query
            [
                {"delivery_status": "success", "count": 8},
                {"delivery_status": "failure", "count": 2},
            ],
            # Message count query
            [{"total_messages": 16}],
            # Recent query
            [
                {
                    "id": 1,
                    "delivery_status": "success",
                    "delivered_at": "2025-11-21T10:00:00",
                }
            ],
            # Failures query
            [
                {
                    "id": 2,
                    "delivery_status": "failure",
                    "telegram_chat_id": 987654321,
                }
            ],
        ]

        tracker = DeliveryStatusTracker(mock_storage)
        summary = tracker.get_chat_summary(chat_id=987654321, days=30)

        assert summary["chat_id"] == 987654321
        assert summary["total_deliveries"] == 10
        assert summary["period_days"] == 30
        assert "statistics" in summary
        assert "recent" in summary
        assert "failures" in summary

    def test_get_chat_summary_invalid_chat_id(self):
        """Test chat summary with invalid chat ID."""
        mock_storage = MagicMock()
        tracker = DeliveryStatusTracker(mock_storage)

        with pytest.raises(ValueError):
            tracker.get_chat_summary(chat_id="invalid", days=30)


class TestDeliveryStatusTrackerIntegration:
    """Integration tests for status tracker."""

    def test_complete_tracking_workflow(self):
        """Test complete tracking workflow."""
        mock_storage = MagicMock()

        # Setup mock responses for the workflow
        mock_storage.query.side_effect = [
            # For statistics
            [{"delivery_status": "success", "count": 5}],
            [{"total_messages": 10}],
            # For recent status
            [
                {
                    "id": 1,
                    "delivery_status": "success",
                    "delivered_at": "2025-11-21T10:00:00",
                }
            ],
            # For failures
            [],
        ]

        tracker = DeliveryStatusTracker(mock_storage)

        # Record delivery
        record_result = tracker.record_delivery(
            newsletter_content="Newsletter",
            chat_id=987654321,
            status=DeliveryStatus.SUCCESS,
            message_ids=[101, 102],
        )

        assert record_result["success"] is True

        # Get statistics
        stats = tracker.get_delivery_statistics(days=30, chat_id=987654321)
        assert stats["total_deliveries"] == 5

        # Get recent status
        recent = tracker.get_recent_status(chat_id=987654321)
        assert recent["count"] == 1

        # Get failures
        failures = tracker.get_failures(days=30)
        assert failures["count"] == 0


class TestEdgeCases:
    """Test edge cases."""

    def test_record_with_no_messages(self):
        """Test recording with no message IDs."""
        mock_storage = MagicMock()
        tracker = DeliveryStatusTracker(mock_storage)

        result = tracker.record_delivery(
            newsletter_content="Newsletter",
            chat_id=987654321,
            status=DeliveryStatus.FAILURE,
            message_ids=None,
        )

        assert result["success"] is True
        assert result["message_count"] == 0

    def test_record_with_empty_message_list(self):
        """Test recording with empty message list."""
        mock_storage = MagicMock()
        tracker = DeliveryStatusTracker(mock_storage)

        result = tracker.record_delivery(
            newsletter_content="Newsletter",
            chat_id=987654321,
            status=DeliveryStatus.FAILURE,
            message_ids=[],
        )

        assert result["success"] is True
        assert result["message_count"] == 0

    def test_get_history_empty_database(self):
        """Test getting history from empty database."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = [[], [{"count": 0}]]

        tracker = DeliveryStatusTracker(mock_storage)
        result = tracker.get_delivery_history()

        assert len(result["records"]) == 0
        assert result["total_count"] == 0

    def test_record_negative_chat_id(self):
        """Test recording with negative chat ID (group)."""
        mock_storage = MagicMock()
        tracker = DeliveryStatusTracker(mock_storage)

        result = tracker.record_delivery(
            newsletter_content="Newsletter",
            chat_id=-987654321,
            status=DeliveryStatus.SUCCESS,
            message_ids=[101],
        )

        assert result["success"] is True
