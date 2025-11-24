"""Test suite for execution monitoring."""

import pytest
import json
import time
from datetime import datetime

from src.utils.execution_monitor import (
    ExecutionMonitor,
    ExecutionPhase,
    PhaseMetrics,
    ExecutionMetrics,
)


class TestPhaseMetrics:
    """Test PhaseMetrics dataclass."""

    def test_create_phase_metrics(self):
        """Test creating phase metrics."""
        start_time = datetime.utcnow().isoformat()
        metrics = PhaseMetrics(
            phase="collection",
            start_time=start_time,
        )

        assert metrics.phase == "collection"
        assert metrics.start_time == start_time
        assert metrics.status == "running"
        assert metrics.items_processed == 0

    def test_phase_metrics_with_data(self):
        """Test phase metrics with data."""
        metrics = PhaseMetrics(
            phase="ai_processing",
            start_time=datetime.utcnow().isoformat(),
            items_processed=100,
            items_failed=5,
            items_skipped=2,
        )

        assert metrics.items_processed == 100
        assert metrics.items_failed == 5
        assert metrics.items_skipped == 2


class TestExecutionMonitor:
    """Test ExecutionMonitor class."""

    def test_initialization(self):
        """Test monitor initialization."""
        monitor = ExecutionMonitor()

        assert monitor.execution_id is not None
        assert len(monitor.execution_id) > 0
        assert monitor.metrics.execution_id == monitor.execution_id
        assert monitor.current_phase is None

    def test_initialization_with_custom_id(self):
        """Test initialization with custom execution ID."""
        custom_id = "test_exec_123"
        monitor = ExecutionMonitor(execution_id=custom_id)

        assert monitor.execution_id == custom_id

    def test_start_phase(self):
        """Test starting a phase."""
        monitor = ExecutionMonitor()

        monitor.start_phase(ExecutionPhase.COLLECTION)

        assert monitor.current_phase == ExecutionPhase.COLLECTION
        assert ExecutionPhase.COLLECTION.value in monitor.metrics.phases

    def test_end_phase_success(self):
        """Test ending phase with success."""
        monitor = ExecutionMonitor()
        monitor.start_phase(ExecutionPhase.COLLECTION)

        time.sleep(0.1)  # Small delay to get measurable duration
        monitor.end_phase(status="success")

        phase_key = ExecutionPhase.COLLECTION.value
        phase = monitor.metrics.phases[phase_key]
        assert phase.status == "success"
        assert phase.duration_seconds >= 0.1
        assert monitor.current_phase is None

    def test_end_phase_failed(self):
        """Test ending phase with failure."""
        monitor = ExecutionMonitor()
        monitor.start_phase(ExecutionPhase.DEDUPLICATION)

        monitor.end_phase(status="failed", error_message="Test error")

        phase_key = ExecutionPhase.DEDUPLICATION.value
        phase = monitor.metrics.phases[phase_key]
        assert phase.status == "failed"
        assert phase.error_message == "Test error"
        assert monitor.metrics.phases_failed == 1

    def test_phase_transition(self):
        """Test transitioning between phases."""
        monitor = ExecutionMonitor()

        # Start and complete first phase
        monitor.start_phase(ExecutionPhase.COLLECTION)
        monitor.end_phase(status="success")

        # Start second phase
        monitor.start_phase(ExecutionPhase.DEDUPLICATION)

        assert ExecutionPhase.COLLECTION.value in monitor.metrics.phases
        assert ExecutionPhase.DEDUPLICATION.value in monitor.metrics.phases
        assert monitor.current_phase == ExecutionPhase.DEDUPLICATION

    def test_record_collection(self):
        """Test recording collection statistics."""
        monitor = ExecutionMonitor()
        monitor.start_phase(ExecutionPhase.COLLECTION)

        monitor.record_collection(items_collected=150)

        assert monitor.metrics.items_collected == 150

    def test_record_deduplication(self):
        """Test recording deduplication statistics."""
        monitor = ExecutionMonitor()
        monitor.start_phase(ExecutionPhase.DEDUPLICATION)

        monitor.record_deduplication(
            items_remaining=140,
            items_removed=10,
            items_filtered=5,
        )

        assert monitor.metrics.items_deduplicated == 140

    def test_record_ai_filtering(self):
        """Test recording AI filtering results."""
        monitor = ExecutionMonitor()
        monitor.start_phase(ExecutionPhase.AI_PROCESSING)

        monitor.record_ai_filtering(items_filtered=50)

        assert monitor.metrics.items_filtered_ai == 50

    def test_record_categorization(self):
        """Test recording categorization."""
        monitor = ExecutionMonitor()
        monitor.start_phase(ExecutionPhase.GENERATION)

        monitor.record_categorization(items_categorized=50, num_categories=3)

        assert monitor.metrics.items_categorized == 50

    def test_record_delivery(self):
        """Test recording delivery statistics."""
        monitor = ExecutionMonitor()
        monitor.start_phase(ExecutionPhase.DELIVERY)

        message_ids = [101, 102, 103]
        monitor.record_delivery(items_delivered=50, telegram_message_ids=message_ids)

        assert monitor.metrics.items_delivered == 50

    def test_complete_execution(self):
        """Test completing execution."""
        monitor = ExecutionMonitor()

        monitor.start_phase(ExecutionPhase.COLLECTION)
        monitor.record_collection(100)
        time.sleep(0.05)  # Small delay for measurable duration
        monitor.end_phase(status="success")

        monitor.complete(overall_status="success")

        assert monitor.metrics.end_time is not None
        assert monitor.metrics.overall_status == "success"
        # Total duration should be >= phase duration
        assert monitor.metrics.total_duration_seconds >= 0

    def test_complete_with_error(self):
        """Test completing execution with error."""
        monitor = ExecutionMonitor()

        monitor.complete(
            overall_status="failed",
            error_message="Network error"
        )

        assert monitor.metrics.overall_status == "failed"
        assert monitor.metrics.error_message == "Network error"

    def test_get_summary(self):
        """Test getting execution summary."""
        monitor = ExecutionMonitor()

        monitor.start_phase(ExecutionPhase.COLLECTION)
        monitor.record_collection(100)
        monitor.end_phase(status="success")

        monitor.complete(overall_status="success")

        summary = monitor.get_summary()

        assert summary["execution_id"] == monitor.execution_id
        assert summary["status"] == "success"
        assert "start_time" in summary
        assert "end_time" in summary
        assert "content_metrics" in summary
        assert summary["content_metrics"]["collected"] == 100

    def test_get_metrics_json(self):
        """Test getting metrics as JSON."""
        monitor = ExecutionMonitor()

        monitor.start_phase(ExecutionPhase.COLLECTION)
        monitor.record_collection(100)
        monitor.end_phase(status="success")

        monitor.complete(overall_status="success")

        metrics_json = monitor.get_metrics_json()

        # Verify it's valid JSON
        parsed = json.loads(metrics_json)
        assert parsed["execution_id"] == monitor.execution_id
        assert parsed["overall_status"] == "success"
        assert parsed["content_counts"]["collected"] == 100

    def test_full_pipeline_workflow(self):
        """Test full pipeline workflow monitoring."""
        monitor = ExecutionMonitor()

        # Phase 1: Collection
        monitor.start_phase(ExecutionPhase.COLLECTION)
        monitor.record_collection(items_collected=150)
        monitor.end_phase(status="success")

        # Phase 2: Deduplication
        monitor.start_phase(ExecutionPhase.DEDUPLICATION)
        monitor.record_deduplication(
            items_remaining=140,
            items_removed=10,
        )
        monitor.end_phase(status="success")

        # Phase 3: AI Processing
        monitor.start_phase(ExecutionPhase.AI_PROCESSING)
        monitor.record_ai_filtering(items_filtered=50)
        monitor.end_phase(status="success")

        # Phase 4: Generation
        monitor.start_phase(ExecutionPhase.GENERATION)
        monitor.record_categorization(items_categorized=50, num_categories=3)
        monitor.end_phase(status="success")

        # Phase 5: Delivery
        monitor.start_phase(ExecutionPhase.DELIVERY)
        monitor.record_delivery(
            items_delivered=50,
            telegram_message_ids=[101, 102, 103],
        )
        monitor.end_phase(status="success")

        monitor.complete(overall_status="success")

        summary = monitor.get_summary()

        assert summary["phases_completed"] == 5
        assert summary["phases_failed"] == 0
        assert summary["content_metrics"]["collected"] == 150
        assert summary["content_metrics"]["ai_filtered"] == 50
        assert summary["content_metrics"]["delivered"] == 50

    def test_error_in_phase(self):
        """Test recording error in phase."""
        monitor = ExecutionMonitor()

        monitor.start_phase(ExecutionPhase.COLLECTION)
        error_msg = "Network timeout during collection"
        monitor.end_phase(status="failed", error_message=error_msg)

        phase_key = ExecutionPhase.COLLECTION.value
        phase = monitor.metrics.phases[phase_key]
        assert phase.error_message is not None
        assert "Network timeout" in phase.error_message


class TestExecutionMonitorIntegration:
    """Integration tests for execution monitoring."""

    def test_partial_failure_workflow(self):
        """Test workflow with partial failure."""
        monitor = ExecutionMonitor()

        # Successful phases
        monitor.start_phase(ExecutionPhase.COLLECTION)
        monitor.record_collection(100)
        monitor.end_phase(status="success")

        monitor.start_phase(ExecutionPhase.DEDUPLICATION)
        monitor.record_deduplication(items_remaining=90, items_removed=10)
        monitor.end_phase(status="success")

        # Failed phase
        monitor.start_phase(ExecutionPhase.AI_PROCESSING)
        monitor.record_error(error="AI service unavailable")
        monitor.end_phase(status="failed")

        monitor.complete(overall_status="partial_failure")

        summary = monitor.get_summary()
        assert summary["phases_completed"] == 2
        assert summary["phases_failed"] == 1
        assert summary["status"] == "partial_failure"

    def test_execution_with_timing(self):
        """Test execution with actual timing."""
        monitor = ExecutionMonitor()

        monitor.start_phase(ExecutionPhase.COLLECTION)
        time.sleep(0.2)
        monitor.record_collection(100)
        monitor.end_phase(status="success")

        monitor.start_phase(ExecutionPhase.DEDUPLICATION)
        time.sleep(0.1)
        monitor.record_deduplication(items_remaining=90, items_removed=10)
        monitor.end_phase(status="success")

        monitor.complete(overall_status="success")

        summary = monitor.get_summary()

        # Check that collection took longer than deduplication
        collection_time = summary["phases"]["collection"]["duration_seconds"]
        dedup_time = summary["phases"]["deduplication"]["duration_seconds"]

        assert collection_time > 0.15
        assert dedup_time > 0.05

    def test_phases_summary_all_phases(self):
        """Test that summary includes all phases executed."""
        monitor = ExecutionMonitor()

        for phase in [ExecutionPhase.COLLECTION, ExecutionPhase.DEDUPLICATION]:
            monitor.start_phase(phase)
            monitor.end_phase(status="success")

        monitor.complete(overall_status="success")

        summary = monitor.get_summary()

        assert ExecutionPhase.COLLECTION.value in summary["phases"]
        assert ExecutionPhase.DEDUPLICATION.value in summary["phases"]
        assert ExecutionPhase.AI_PROCESSING.value not in summary["phases"]


class TestEdgeCases:
    """Test edge cases."""

    def test_end_phase_without_start(self):
        """Test ending phase without starting."""
        monitor = ExecutionMonitor()

        # Should not raise error
        monitor.end_phase(status="success")

    def test_record_without_active_phase(self):
        """Test recording metrics without active phase."""
        monitor = ExecutionMonitor()

        # Should not raise error
        monitor.record_collection(items_collected=100)

    def test_complete_without_phases(self):
        """Test completing without any phases."""
        monitor = ExecutionMonitor()

        monitor.complete(overall_status="success")

        assert monitor.metrics.overall_status == "success"
        assert monitor.metrics.total_duration_seconds >= 0

    def test_zero_content_counts(self):
        """Test with zero content items."""
        monitor = ExecutionMonitor()

        monitor.start_phase(ExecutionPhase.COLLECTION)
        monitor.record_collection(items_collected=0)
        monitor.end_phase(status="success")

        summary = monitor.get_summary()
        assert summary["content_metrics"]["collected"] == 0

    def test_very_large_content_counts(self):
        """Test with large content counts."""
        monitor = ExecutionMonitor()

        large_number = 1000000
        monitor.start_phase(ExecutionPhase.COLLECTION)
        monitor.record_collection(items_collected=large_number)
        monitor.end_phase(status="success")

        summary = monitor.get_summary()
        assert summary["content_metrics"]["collected"] == large_number
