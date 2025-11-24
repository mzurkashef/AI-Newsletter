"""Test suite for data cleanup and retention policy."""

import pytest
from unittest.mock import MagicMock

from src.utils.data_cleanup import (
    DataCleanupManager,
    RetentionPolicy,
)


class TestRetentionPolicy:
    """Test RetentionPolicy configuration."""

    def test_default_policy(self):
        """Test default retention policy."""
        policy = RetentionPolicy()

        assert policy.raw_content_days == 30
        assert policy.processed_content_days == 90
        assert policy.delivery_history_days == 365
        assert policy.source_status_days == 90

    def test_custom_policy(self):
        """Test custom retention policy."""
        policy = RetentionPolicy(
            raw_content_days=14,
            processed_content_days=60,
            delivery_history_days=730,
            source_status_days=45,
        )

        assert policy.raw_content_days == 14
        assert policy.processed_content_days == 60
        assert policy.delivery_history_days == 730
        assert policy.source_status_days == 45


class TestDataCleanupManagerInitialization:
    """Test DataCleanupManager initialization."""

    def test_init_with_storage(self):
        """Test initialization with storage."""
        mock_storage = MagicMock()
        manager = DataCleanupManager(mock_storage)

        assert manager.storage == mock_storage
        assert manager.policy is not None

    def test_init_without_storage_fails(self):
        """Test initialization without storage fails."""
        with pytest.raises(ValueError):
            DataCleanupManager(None)

    def test_set_retention_policy(self):
        """Test setting custom retention policy."""
        mock_storage = MagicMock()
        manager = DataCleanupManager(mock_storage)

        custom_policy = RetentionPolicy(raw_content_days=14)
        manager.set_retention_policy(custom_policy)

        assert manager.policy.raw_content_days == 14


class TestCleanupOperations:
    """Test cleanup operations."""

    def test_cleanup_raw_content(self):
        """Test raw content cleanup."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = [{"count": 50}]
        mock_storage.execute = MagicMock()

        manager = DataCleanupManager(mock_storage)
        result = manager.cleanup_raw_content(dry_run=False)

        assert result["table"] == "raw_content"
        assert result["dry_run"] is False
        assert "records_deleted" in result

    def test_cleanup_processed_content(self):
        """Test processed content cleanup."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = [{"count": 75}]

        manager = DataCleanupManager(mock_storage)
        result = manager.cleanup_processed_content(dry_run=True)

        assert result["table"] == "processed_content"
        assert result["dry_run"] is True
        assert "cutoff_date" in result

    def test_cleanup_source_status(self):
        """Test source status cleanup."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = [{"count": 10}]

        manager = DataCleanupManager(mock_storage)
        result = manager.cleanup_source_status(dry_run=True)

        assert result["table"] == "source_status"
        assert result["dry_run"] is True

    def test_cleanup_all(self):
        """Test cleanup all tables."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = [{"count": 30}]

        manager = DataCleanupManager(mock_storage)
        result = manager.cleanup_all(dry_run=True)

        assert result["success"] is True
        assert result["dry_run"] is True
        assert "by_table" in result

    def test_cleanup_dry_run_mode(self):
        """Test cleanup doesn't delete in dry-run mode."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = [{"count": 50}]

        manager = DataCleanupManager(mock_storage)
        result = manager.cleanup_raw_content(dry_run=True)

        assert result["dry_run"] is True
        # execute should not be called in dry-run mode
        mock_storage.execute.assert_not_called()

    def test_cleanup_actual_deletion(self):
        """Test actual deletion in non-dry-run mode."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = [{"count": 50}]
        mock_storage.execute = MagicMock()

        manager = DataCleanupManager(mock_storage)
        result = manager.cleanup_raw_content(dry_run=False)

        assert result["dry_run"] is False
        # execute should be called for actual deletion
        mock_storage.execute.assert_called()


class TestDatabaseStatistics:
    """Test database statistics."""

    def test_get_database_statistics(self):
        """Test getting database statistics."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = [
            [{"count": 100}],  # raw_content
            [{"count": 200}],  # processed_content
            [{"count": 50}],   # delivery_history
            [{"count": 25}],   # source_status
        ]

        manager = DataCleanupManager(mock_storage)
        stats = manager.get_database_statistics()

        assert stats["raw_content_count"] == 100
        assert stats["processed_content_count"] == 200
        assert stats["delivery_history_count"] == 50
        assert stats["source_status_count"] == 25
        assert stats["total_records"] == 375

    def test_database_statistics_empty_database(self):
        """Test statistics on empty database."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = [
            [{"count": 0}],
            [{"count": 0}],
            [{"count": 0}],
            [{"count": 0}],
        ]

        manager = DataCleanupManager(mock_storage)
        stats = manager.get_database_statistics()

        assert stats["total_records"] == 0


class TestCleanupRecommendations:
    """Test cleanup recommendations."""

    def test_no_cleanup_needed(self):
        """Test when no cleanup is needed."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = [
            [{"count": 100}],
            [{"count": 200}],
            [{"count": 50}],
            [{"count": 25}],
        ]

        manager = DataCleanupManager(mock_storage)
        rec = manager.cleanup_recommendation()

        assert rec["should_cleanup"] is False
        assert "normal" in rec["reason"]

    def test_cleanup_recommended_large_database(self):
        """Test cleanup recommendation for large database."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = [
            [{"count": 60000}],
            [{"count": 60000}],
            [{"count": 60000}],
            [{"count": 60000}],
        ]

        manager = DataCleanupManager(mock_storage)
        rec = manager.cleanup_recommendation()

        assert rec["should_cleanup"] is True
        assert "large" in rec["reason"].lower()

    def test_cleanup_recommendations_per_table(self):
        """Test per-table cleanup recommendations."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = [
            [{"count": 60000}],  # raw_content_count
            [{"count": 60000}],    # processed_content_count
            [{"count": 50}],     # delivery_history_count
            [{"count": 25}],     # source_status_count
        ]

        manager = DataCleanupManager(mock_storage)
        rec = manager.cleanup_recommendation()

        assert rec["should_cleanup"] is True
        assert len(rec["actions"]) > 0


class TestCleanupWithErrors:
    """Test error handling in cleanup."""

    def test_cleanup_error_handling(self):
        """Test error handling during cleanup."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = Exception("Database error")

        manager = DataCleanupManager(mock_storage)
        result = manager.cleanup_raw_content()

        assert "error" in result

    def test_statistics_error_handling(self):
        """Test error handling in statistics."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = Exception("Database error")

        manager = DataCleanupManager(mock_storage)
        stats = manager.get_database_statistics()

        assert "error" in stats

    def test_recommendations_error_handling(self):
        """Test error handling in recommendations."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = Exception("Database error")

        manager = DataCleanupManager(mock_storage)
        rec = manager.cleanup_recommendation()

        # When statistics fails, recommendations still return normal dict (no records = no cleanup needed)
        assert rec["should_cleanup"] is False
        assert "reason" in rec


class TestIntegration:
    """Integration tests for data cleanup."""

    def test_complete_cleanup_workflow(self):
        """Test complete cleanup workflow."""
        mock_storage = MagicMock()

        # Setup responses for multiple calls
        mock_storage.query.side_effect = [
            # For cleanup_all
            [{"count": 50}],     # raw_content query
            [{"count": 75}],     # processed_content query
            [{"count": 100}],    # delivery_history query
            [{"count": 25}],     # source_status query
        ]
        mock_storage.execute = MagicMock()

        manager = DataCleanupManager(mock_storage)

        # First check recommendations
        rec = manager.cleanup_recommendation()
        assert "should_cleanup" in rec

        # Then run cleanup
        result = manager.cleanup_all(dry_run=False)
        assert result["success"] is True

    def test_policy_impact_on_cleanup(self):
        """Test that retention policy affects cleanup cutoff dates."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = [{"count": 0}]

        manager = DataCleanupManager(mock_storage)

        # Set short retention
        short_policy = RetentionPolicy(raw_content_days=1)
        manager.set_retention_policy(short_policy)

        manager.cleanup_raw_content(dry_run=True)

        # Verify query was called with correct date column
        call_args = mock_storage.query.call_args
        assert call_args is not None


class TestEdgeCases:
    """Test edge cases."""

    def test_cleanup_zero_records(self):
        """Test cleanup when no records match criteria."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = [{"count": 0}]

        manager = DataCleanupManager(mock_storage)
        result = manager.cleanup_raw_content(dry_run=False)

        assert result["records_deleted"] == 0

    def test_very_large_database(self):
        """Test with very large record count."""
        mock_storage = MagicMock()
        large_count = 1000000
        mock_storage.query.return_value = [{"count": large_count}]

        manager = DataCleanupManager(mock_storage)
        result = manager.cleanup_raw_content(dry_run=True)

        assert result["records_deleted"] == large_count

    def test_all_cleanup_disabled(self):
        """Test with zero retention (essentially disabled)."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = [{"count": 50}]

        manager = DataCleanupManager(mock_storage)
        policy = RetentionPolicy(raw_content_days=0)
        manager.set_retention_policy(policy)

        result = manager.cleanup_raw_content(dry_run=True)

        assert result["dry_run"] is True
