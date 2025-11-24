"""
Tests for source health monitoring module.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock
import logging

from src.collectors.source_health import (
    SourceHealth,
    SourceHealthError,
)


@pytest.fixture
def mock_storage():
    """Mock database storage."""
    storage = Mock()
    storage.get_source_status = Mock(return_value=None)
    storage.update_source_status = Mock()
    storage.get_all_sources = Mock(return_value=[])
    return storage


@pytest.fixture
def source_health(mock_storage):
    """Create source health monitor with mock storage."""
    return SourceHealth(
        storage=mock_storage,
        failure_threshold=5,
        recovery_hours=24,
    )


@pytest.fixture
def healthy_source():
    """Create a healthy source status dict."""
    return {
        "source_id": "source_1",
        "source_type": "newsletter",
        "consecutive_failures": 0,
        "last_error": None,
        "last_error_at": None,
        "last_collected_at": datetime.utcnow().isoformat(),
        "last_success": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def failed_source():
    """Create a source with some failures."""
    return {
        "source_id": "source_2",
        "source_type": "newsletter",
        "consecutive_failures": 3,
        "last_error": "Connection timeout",
        "last_error_at": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
        "last_collected_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
        "last_success": (datetime.utcnow() - timedelta(days=2)).isoformat(),
    }


@pytest.fixture
def unhealthy_source():
    """Create an unhealthy source (threshold exceeded)."""
    return {
        "source_id": "source_3",
        "source_type": "newsletter",
        "consecutive_failures": 5,
        "last_error": "Connection refused",
        "last_error_at": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
        "last_collected_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
        "last_success": (datetime.utcnow() - timedelta(days=5)).isoformat(),
    }


@pytest.fixture
def recovered_source():
    """Create an unhealthy source that has recovered (past recovery period)."""
    return {
        "source_id": "source_4",
        "source_type": "newsletter",
        "consecutive_failures": 5,
        "last_error": "Network unavailable",
        "last_error_at": (datetime.utcnow() - timedelta(hours=30)).isoformat(),
        "last_collected_at": (datetime.utcnow() - timedelta(hours=30)).isoformat(),
        "last_success": (datetime.utcnow() - timedelta(days=2)).isoformat(),
    }


class TestSourceHealthIsHealthy:
    """Test health status checking."""

    def test_is_healthy_no_failures(self, source_health, healthy_source):
        """Test that source with no failures is healthy."""
        result = source_health.is_healthy(healthy_source)
        assert result is True

    def test_is_healthy_some_failures(self, source_health, failed_source):
        """Test that source with failures below threshold is healthy."""
        result = source_health.is_healthy(failed_source)
        assert result is True

    def test_is_healthy_at_threshold(self, source_health, unhealthy_source):
        """Test that source at threshold is unhealthy."""
        result = source_health.is_healthy(unhealthy_source)
        assert result is False

    def test_is_healthy_above_threshold(self, source_health):
        """Test that source above threshold is unhealthy."""
        source = {
            "source_id": "source_5",
            "source_type": "newsletter",
            "consecutive_failures": 10,
            "last_error": "Multiple failures",
            "last_error_at": datetime.utcnow().isoformat(),
            "last_collected_at": datetime.utcnow().isoformat(),
            "last_success": None,
        }
        result = source_health.is_healthy(source)
        assert result is False

    def test_is_healthy_invalid_type(self, source_health, caplog):
        """Test with invalid source_status type."""
        with caplog.at_level(logging.WARNING):
            result = source_health.is_healthy("not-a-source")
        assert result is False
        assert len(caplog.records) > 0

    def test_is_healthy_none_failures(self, source_health):
        """Test with None consecutive_failures."""
        source = {
            "source_id": "source_1",
            "source_type": "newsletter",
            "consecutive_failures": None,
            "last_error": None,
            "last_error_at": None,
            "last_collected_at": datetime.utcnow().isoformat(),
            "last_success": datetime.utcnow().isoformat(),
        }
        result = source_health.is_healthy(source)
        assert result is True


class TestSourceHealthInRecovery:
    """Test recovery period checking."""

    def test_is_in_recovery_healthy_source(self, source_health, healthy_source):
        """Test that healthy source is not in recovery."""
        result = source_health.is_in_recovery(healthy_source)
        assert result is False

    def test_is_in_recovery_no_error(self, source_health):
        """Test source with no error timestamp is not in recovery."""
        source = {
            "source_id": "source_1",
            "source_type": "newsletter",
            "consecutive_failures": 2,
            "last_error": None,
            "last_error_at": None,
            "last_collected_at": datetime.utcnow().isoformat(),
            "last_success": datetime.utcnow().isoformat(),
        }
        result = source_health.is_in_recovery(source)
        assert result is False

    def test_is_in_recovery_below_threshold(self, source_health, failed_source):
        """Test that source below threshold is not in recovery."""
        result = source_health.is_in_recovery(failed_source)
        assert result is False

    def test_is_in_recovery_within_window(self, source_health, unhealthy_source):
        """Test that unhealthy source within recovery window is in recovery."""
        result = source_health.is_in_recovery(unhealthy_source)
        assert result is True

    def test_is_in_recovery_outside_window(self, source_health, recovered_source):
        """Test that unhealthy source outside recovery window is not in recovery."""
        result = source_health.is_in_recovery(recovered_source)
        assert result is False


class TestSourceHealthCanCollect:
    """Test collection eligibility."""

    def test_can_collect_healthy(self, source_health, healthy_source):
        """Test that healthy sources can be collected from."""
        result = source_health.can_collect_from_source(healthy_source)
        assert result is True

    def test_can_collect_some_failures(self, source_health, failed_source):
        """Test that sources with failures below threshold can be collected from."""
        result = source_health.can_collect_from_source(failed_source)
        assert result is True

    def test_can_collect_unhealthy_in_recovery(self, source_health, unhealthy_source):
        """Test that unhealthy sources in recovery cannot be collected from."""
        result = source_health.can_collect_from_source(unhealthy_source)
        assert result is False

    def test_can_collect_unhealthy_recovered(self, source_health, recovered_source):
        """Test that unhealthy sources outside recovery can be collected from."""
        result = source_health.can_collect_from_source(recovered_source)
        assert result is True


class TestSourceHealthStatus:
    """Test detailed health status retrieval."""

    def test_get_health_status_healthy(self, source_health, healthy_source):
        """Test health status of healthy source."""
        status = source_health.get_health_status(healthy_source)

        assert status["is_healthy"] is True
        assert status["is_in_recovery"] is False
        assert status["can_collect"] is True
        assert status["consecutive_failures"] == 0
        assert status["failure_threshold"] == 5
        assert status["last_error"] is None

    def test_get_health_status_unhealthy(self, source_health, unhealthy_source):
        """Test health status of unhealthy source."""
        status = source_health.get_health_status(unhealthy_source)

        assert status["is_healthy"] is False
        assert status["is_in_recovery"] is True
        assert status["can_collect"] is False
        assert status["consecutive_failures"] == 5
        assert status["failure_threshold"] == 5
        assert status["last_error"] == "Connection refused"

    def test_get_health_status_structure(self, source_health, healthy_source):
        """Test that health status has expected structure."""
        status = source_health.get_health_status(healthy_source)

        assert "is_healthy" in status
        assert "is_in_recovery" in status
        assert "can_collect" in status
        assert "consecutive_failures" in status
        assert "failure_threshold" in status
        assert "last_error" in status
        assert "last_error_at" in status
        assert "recovery_until" in status


class TestSourceHealthMarkFailureSuccess:
    """Test failure and success marking."""

    def test_mark_failure_increments_counter(self, source_health, mock_storage, healthy_source):
        """Test that marking failure increments failure counter."""
        mock_storage.get_source_status.return_value = healthy_source.copy()
        mock_storage.get_source_status.side_effect = [healthy_source.copy(), {"consecutive_failures": 1}]

        result = source_health.mark_failure("source_1", "Test error")

        assert "consecutive_failures" in result

    def test_mark_failure_not_found(self, source_health, mock_storage):
        """Test marking failure for non-existent source."""
        mock_storage.get_source_status.return_value = None

        result = source_health.mark_failure("nonexistent", "Not found")

        assert "error" in result

    def test_mark_success_resets_counter(self, source_health, mock_storage, failed_source):
        """Test that marking success resets failure counter."""
        failed_copy = failed_source.copy()
        mock_storage.get_source_status.side_effect = [failed_copy, {"consecutive_failures": 0}]

        result = source_health.mark_success("source_2")

        assert "consecutive_failures" in result

    def test_mark_success_not_found(self, source_health, mock_storage):
        """Test marking success for non-existent source."""
        mock_storage.get_source_status.return_value = None

        result = source_health.mark_success("nonexistent")

        assert "error" in result


class TestSourceHealthCheckAll:
    """Test checking health of all sources."""

    def test_check_all_sources_empty(self, source_health, mock_storage):
        """Test checking when no sources exist."""
        mock_storage.get_all_sources.return_value = []

        result = source_health.check_all_sources()

        assert result["total"] == 0
        assert result["healthy"] == 0
        assert result["unhealthy"] == 0
        assert result["collectable"] == 0

    def test_check_all_sources_all_healthy(self, source_health, mock_storage, healthy_source):
        """Test checking when all sources are healthy."""
        mock_storage.get_all_sources.return_value = [healthy_source]

        result = source_health.check_all_sources()

        assert result["total"] == 1
        assert result["healthy"] == 1
        assert result["unhealthy"] == 0
        assert result["collectable"] == 1

    def test_check_all_sources_mixed(self, source_health, mock_storage, healthy_source, unhealthy_source, failed_source):
        """Test checking with mixed source health."""
        mock_storage.get_all_sources.return_value = [healthy_source, unhealthy_source, failed_source]

        result = source_health.check_all_sources()

        assert result["total"] == 3
        assert result["healthy"] == 2  # healthy and failed (below threshold)
        assert result["unhealthy"] == 1
        assert result["in_recovery"] == 1
        assert result["collectable"] == 2  # healthy and failed (below threshold)

    def test_check_all_sources_error_handling(self, source_health, mock_storage):
        """Test error handling during check_all_sources."""
        mock_storage.get_all_sources.side_effect = Exception("Database error")

        result = source_health.check_all_sources()

        assert result["total"] == 0
        assert result["healthy"] == 0
        assert "error" in result


class TestSourceHealthGetCollectable:
    """Test getting collectable sources."""

    def test_get_collectable_sources_empty(self, source_health, mock_storage):
        """Test getting collectable sources when none exist."""
        mock_storage.get_all_sources.return_value = []

        result = source_health.get_collectable_sources()

        assert result["total"] == 0
        assert result["collectable"] == 0
        assert result["skipped"] == 0

    def test_get_collectable_sources_all_collectable(self, source_health, mock_storage, healthy_source, failed_source):
        """Test getting collectable sources when all are collectable."""
        mock_storage.get_all_sources.return_value = [healthy_source, failed_source]

        result = source_health.get_collectable_sources()

        assert result["total"] == 2
        assert result["collectable"] == 2
        assert result["skipped"] == 0
        assert len(result["sources"]) == 2

    def test_get_collectable_sources_filters_unhealthy(self, source_health, mock_storage, healthy_source, unhealthy_source):
        """Test that unhealthy sources are filtered out."""
        mock_storage.get_all_sources.return_value = [healthy_source, unhealthy_source]

        result = source_health.get_collectable_sources()

        assert result["total"] == 2
        assert result["collectable"] == 1
        assert result["skipped"] == 1
        assert result["sources"][0]["source_id"] == "source_1"

    def test_get_collectable_sources_error_handling(self, source_health, mock_storage):
        """Test error handling during get_collectable_sources."""
        mock_storage.get_all_sources.side_effect = Exception("Database error")

        result = source_health.get_collectable_sources()

        assert result["collectable"] == 0
        assert "error" in result


class TestSourceHealthReset:
    """Test resetting failure counters."""

    def test_reset_all_failures_empty(self, source_health, mock_storage):
        """Test reset when no sources exist."""
        mock_storage.get_all_sources.return_value = []

        result = source_health.reset_all_failures()

        assert result["total"] == 0
        assert result["reset"] == 0

    def test_reset_all_failures_none_needed(self, source_health, mock_storage, healthy_source):
        """Test reset when no sources have failures."""
        mock_storage.get_all_sources.return_value = [healthy_source]

        result = source_health.reset_all_failures()

        assert result["total"] == 1
        assert result["reset"] == 0

    def test_reset_all_failures_resets_all(self, source_health, mock_storage, failed_source, unhealthy_source):
        """Test reset resets all failed sources."""
        mock_storage.get_all_sources.return_value = [failed_source, unhealthy_source]

        result = source_health.reset_all_failures()

        assert result["total"] == 2
        assert result["reset"] == 2

    def test_reset_all_failures_error_handling(self, source_health, mock_storage):
        """Test error handling during reset."""
        mock_storage.get_all_sources.side_effect = Exception("Database error")

        result = source_health.reset_all_failures()

        assert result["reset"] == 0
        assert "error" in result


class TestSourceHealthConfiguration:
    """Test configuration updates."""

    def test_update_failure_threshold_valid(self, source_health):
        """Test updating failure threshold with valid value."""
        source_health.update_failure_threshold(10)

        assert source_health.failure_threshold == 10

    def test_update_failure_threshold_minimum(self, source_health):
        """Test updating to minimum threshold (1)."""
        source_health.update_failure_threshold(1)

        assert source_health.failure_threshold == 1

    def test_update_failure_threshold_invalid_zero(self, source_health):
        """Test that zero threshold is rejected."""
        with pytest.raises(SourceHealthError):
            source_health.update_failure_threshold(0)

    def test_update_failure_threshold_invalid_negative(self, source_health):
        """Test that negative threshold is rejected."""
        with pytest.raises(SourceHealthError):
            source_health.update_failure_threshold(-1)

    def test_update_recovery_hours_valid(self, source_health):
        """Test updating recovery hours with valid value."""
        source_health.update_recovery_hours(48)

        assert source_health.recovery_hours == 48

    def test_update_recovery_hours_minimum(self, source_health):
        """Test updating to minimum hours (1)."""
        source_health.update_recovery_hours(1)

        assert source_health.recovery_hours == 1

    def test_update_recovery_hours_invalid_zero(self, source_health):
        """Test that zero hours is rejected."""
        with pytest.raises(SourceHealthError):
            source_health.update_recovery_hours(0)

    def test_update_recovery_hours_invalid_negative(self, source_health):
        """Test that negative hours is rejected."""
        with pytest.raises(SourceHealthError):
            source_health.update_recovery_hours(-1)


class TestSourceHealthIntegration:
    """Integration tests."""

    def test_health_decision_flow(self, source_health, healthy_source, unhealthy_source, recovered_source):
        """Test health decision flow with different source states."""
        # Healthy - always collectable
        assert source_health.can_collect_from_source(healthy_source) is True

        # Unhealthy in recovery - not collectable
        assert source_health.can_collect_from_source(unhealthy_source) is False

        # Unhealthy but recovery expired - collectable again
        assert source_health.can_collect_from_source(recovered_source) is True

    def test_health_configuration_affects_decisions(self, mock_storage):
        """Test that configuration changes affect health decisions."""
        source = {
            "source_id": "source_1",
            "source_type": "newsletter",
            "consecutive_failures": 3,
            "last_error": "Error",
            "last_error_at": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
            "last_collected_at": datetime.utcnow().isoformat(),
            "last_success": (datetime.utcnow() - timedelta(days=1)).isoformat(),
        }

        # With threshold=5, source with 3 failures is healthy
        health1 = SourceHealth(storage=mock_storage, failure_threshold=5)
        assert health1.is_healthy(source) is True

        # With threshold=2, same source is unhealthy
        health2 = SourceHealth(storage=mock_storage, failure_threshold=2)
        assert health2.is_healthy(source) is False


class TestSourceHealthLogging:
    """Test logging integration."""

    def test_is_healthy_logs_warning(self, source_health, unhealthy_source, caplog):
        """Test that unhealthy status is logged."""
        with caplog.at_level(logging.DEBUG):
            source_health.is_healthy(unhealthy_source)

        assert len(caplog.records) > 0

    def test_check_all_sources_logs_summary(self, source_health, mock_storage, healthy_source, caplog):
        """Test that check_all_sources logs summary."""
        mock_storage.get_all_sources.return_value = [healthy_source]

        with caplog.at_level(logging.INFO):
            source_health.check_all_sources()

        assert any("Source health check complete" in record.message for record in caplog.records)

    def test_update_threshold_logs_info(self, source_health, caplog):
        """Test that configuration updates are logged."""
        with caplog.at_level(logging.INFO):
            source_health.update_failure_threshold(10)

        assert any("Updated failure threshold" in record.message for record in caplog.records)
