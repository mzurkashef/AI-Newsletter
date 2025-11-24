"""
Execution monitoring and metrics tracking for newsletter pipeline.

Tracks execution phases, timing, content counts, and generates execution summaries.
Provides detailed metrics for performance analysis and troubleshooting.
"""

import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum

from src.utils.logging_setup import get_logger

logger = get_logger(__name__)


class ExecutionPhase(str, Enum):
    """Pipeline execution phases."""
    INITIALIZATION = "initialization"
    COLLECTION = "collection"
    DEDUPLICATION = "deduplication"
    AI_PROCESSING = "ai_processing"
    GENERATION = "generation"
    DELIVERY = "delivery"
    COMPLETION = "completion"


@dataclass
class PhaseMetrics:
    """Metrics for a single execution phase."""
    phase: str
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: float = 0.0
    status: str = "running"  # running, success, failed
    error_message: Optional[str] = None

    # Phase-specific metrics
    items_processed: int = 0
    items_failed: int = 0
    items_skipped: int = 0

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionMetrics:
    """Complete execution metrics for a pipeline run."""
    execution_id: str
    start_time: str
    end_time: Optional[str] = None
    total_duration_seconds: float = 0.0
    overall_status: str = "running"  # running, success, partial_failure, failed
    error_message: Optional[str] = None

    # Phase tracking
    phases: Dict[str, PhaseMetrics] = field(default_factory=dict)

    # Content counts
    items_collected: int = 0
    items_deduplicated: int = 0
    items_filtered_ai: int = 0
    items_categorized: int = 0
    items_delivered: int = 0

    # Tracking
    phases_completed: int = 0
    phases_failed: int = 0


class ExecutionMonitor:
    """
    Monitors pipeline execution with timing and metrics collection.

    Features:
    - Track execution phases with timing
    - Count items at each stage
    - Collect error information
    - Generate execution summaries
    - Export metrics in JSON format
    """

    def __init__(self, execution_id: Optional[str] = None):
        """
        Initialize execution monitor.

        Args:
            execution_id: Unique identifier for this execution (auto-generated if None)
        """
        import uuid

        self.execution_id = execution_id or f"exec_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.metrics = ExecutionMetrics(
            execution_id=self.execution_id,
            start_time=datetime.utcnow().isoformat(),
        )
        self.current_phase: Optional[ExecutionPhase] = None
        self.phase_start_time: Optional[float] = None

        logger.info(f"Execution monitor initialized: {self.execution_id}")

    def start_phase(self, phase: ExecutionPhase) -> None:
        """
        Start a new execution phase.

        Args:
            phase: The phase to start
        """
        # End previous phase if any
        if self.current_phase:
            self.end_phase()

        self.current_phase = phase
        self.phase_start_time = time.time()

        phase_metrics = PhaseMetrics(
            phase=phase.value,
            start_time=datetime.utcnow().isoformat(),
        )
        self.metrics.phases[phase.value] = phase_metrics

        logger.info(f"Starting phase: {phase.value}")

    def end_phase(
        self,
        status: str = "success",
        error_message: Optional[str] = None,
        **metadata
    ) -> None:
        """
        End the current execution phase.

        Args:
            status: Phase status (success, failed, skipped)
            error_message: Error message if failed
            **metadata: Additional phase metadata
        """
        if not self.current_phase:
            logger.warning("end_phase called without active phase")
            return

        phase_key = self.current_phase.value
        if phase_key not in self.metrics.phases:
            return

        phase_metrics = self.metrics.phases[phase_key]
        phase_metrics.end_time = datetime.utcnow().isoformat()
        phase_metrics.status = status
        phase_metrics.error_message = error_message
        phase_metrics.metadata = dict(metadata)

        if self.phase_start_time:
            phase_metrics.duration_seconds = time.time() - self.phase_start_time

        if status == "success":
            self.metrics.phases_completed += 1
        elif status == "failed":
            self.metrics.phases_failed += 1

        logger.info(
            f"Completed phase: {phase_key} ({phase_metrics.duration_seconds:.2f}s, "
            f"status={status})"
        )

        self.current_phase = None
        self.phase_start_time = None

    def record_collection(self, items_collected: int) -> None:
        """Record items collected in collection phase."""
        self.metrics.items_collected = items_collected
        if self.current_phase == ExecutionPhase.COLLECTION:
            self.metrics.phases[ExecutionPhase.COLLECTION.value].items_processed = items_collected
        logger.info(f"Collected {items_collected} items")

    def record_deduplication(
        self,
        items_remaining: int,
        items_removed: int,
        items_filtered: int = 0,
    ) -> None:
        """Record deduplication statistics."""
        self.metrics.items_deduplicated = items_remaining
        if self.current_phase == ExecutionPhase.DEDUPLICATION:
            phase = self.metrics.phases[ExecutionPhase.DEDUPLICATION.value]
            phase.items_processed = items_remaining
            phase.items_removed = items_removed
            phase.items_skipped = items_filtered
        logger.info(
            f"Deduplication: {items_remaining} remaining, "
            f"{items_removed} removed, {items_filtered} filtered"
        )

    def record_ai_filtering(self, items_filtered: int) -> None:
        """Record AI filtering results."""
        self.metrics.items_filtered_ai = items_filtered
        if self.current_phase == ExecutionPhase.AI_PROCESSING:
            self.metrics.phases[ExecutionPhase.AI_PROCESSING.value].items_processed = items_filtered
        logger.info(f"AI filtered to {items_filtered} major announcements")

    def record_categorization(self, items_categorized: int, num_categories: int) -> None:
        """Record content categorization."""
        self.metrics.items_categorized = items_categorized
        if self.current_phase == ExecutionPhase.GENERATION:
            phase = self.metrics.phases[ExecutionPhase.GENERATION.value]
            phase.items_processed = items_categorized
            phase.metadata["num_categories"] = num_categories
        logger.info(f"Categorized {items_categorized} items into {num_categories} topics")

    def record_delivery(self, items_delivered: int, telegram_message_ids: List[int]) -> None:
        """Record delivery statistics."""
        self.metrics.items_delivered = items_delivered
        if self.current_phase == ExecutionPhase.DELIVERY:
            phase = self.metrics.phases[ExecutionPhase.DELIVERY.value]
            phase.items_processed = items_delivered
            phase.metadata["message_ids"] = telegram_message_ids
            phase.metadata["message_count"] = len(telegram_message_ids)
        logger.info(f"Delivered {items_delivered} items in {len(telegram_message_ids)} messages")

    def record_error(self, phase: Optional[ExecutionPhase] = None, error: str = "") -> None:
        """Record an error in the current or specified phase."""
        target_phase = phase or self.current_phase
        if target_phase:
            phase_key = target_phase.value
            if phase_key in self.metrics.phases:
                self.metrics.phases[phase_key].error_message = error

        logger.error(f"Error in {target_phase.value if target_phase else 'unknown'}: {error}")

    def complete(self, overall_status: str = "success", error_message: Optional[str] = None) -> None:
        """
        Complete the execution and finalize metrics.

        Args:
            overall_status: Overall execution status
            error_message: Error message if failed
        """
        # End any active phase
        if self.current_phase:
            status = "failed" if overall_status == "failed" else "success"
            self.end_phase(status=status, error_message=error_message)

        self.metrics.end_time = datetime.utcnow().isoformat()
        self.metrics.overall_status = overall_status
        self.metrics.error_message = error_message

        if self.metrics.start_time:
            start = datetime.fromisoformat(self.metrics.start_time)
            end = datetime.fromisoformat(self.metrics.end_time)
            self.metrics.total_duration_seconds = (end - start).total_seconds()

        logger.info(
            f"Execution completed: status={overall_status}, "
            f"duration={self.metrics.total_duration_seconds:.2f}s"
        )

    def get_summary(self) -> Dict[str, Any]:
        """
        Get execution summary.

        Returns:
            Dictionary with complete execution summary
        """
        return {
            "execution_id": self.metrics.execution_id,
            "status": self.metrics.overall_status,
            "start_time": self.metrics.start_time,
            "end_time": self.metrics.end_time,
            "total_duration_seconds": self.metrics.total_duration_seconds,
            "error": self.metrics.error_message,
            "phases_completed": self.metrics.phases_completed,
            "phases_failed": self.metrics.phases_failed,
            "content_metrics": {
                "collected": self.metrics.items_collected,
                "deduplicated": self.metrics.items_deduplicated,
                "ai_filtered": self.metrics.items_filtered_ai,
                "categorized": self.metrics.items_categorized,
                "delivered": self.metrics.items_delivered,
            },
            "phases": {
                phase_key: {
                    "duration_seconds": phase.duration_seconds,
                    "status": phase.status,
                    "items_processed": phase.items_processed,
                    "error": phase.error_message,
                }
                for phase_key, phase in self.metrics.phases.items()
            },
        }

    def get_metrics_json(self) -> str:
        """
        Get complete metrics as JSON string.

        Returns:
            JSON-formatted metrics
        """
        metrics_dict = {
            "execution_id": self.metrics.execution_id,
            "start_time": self.metrics.start_time,
            "end_time": self.metrics.end_time,
            "total_duration_seconds": self.metrics.total_duration_seconds,
            "overall_status": self.metrics.overall_status,
            "error_message": self.metrics.error_message,
            "phases_completed": self.metrics.phases_completed,
            "phases_failed": self.metrics.phases_failed,
            "content_counts": {
                "collected": self.metrics.items_collected,
                "deduplicated": self.metrics.items_deduplicated,
                "ai_filtered": self.metrics.items_filtered_ai,
                "categorized": self.metrics.items_categorized,
                "delivered": self.metrics.items_delivered,
            },
            "phases": {
                phase_key: asdict(phase)
                for phase_key, phase in self.metrics.phases.items()
            },
        }
        return json.dumps(metrics_dict, indent=2, default=str)

    def save_metrics(self, filepath: str) -> None:
        """
        Save metrics to JSON file.

        Args:
            filepath: Path to save metrics file
        """
        try:
            with open(filepath, 'w') as f:
                f.write(self.get_metrics_json())
            logger.info(f"Metrics saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save metrics to {filepath}: {e}")

    def log_summary(self) -> None:
        """Log execution summary to logger."""
        summary = self.get_summary()

        logger.info("=" * 80)
        logger.info("EXECUTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Execution ID: {summary['execution_id']}")
        logger.info(f"Status: {summary['status']}")
        logger.info(f"Duration: {summary['total_duration_seconds']:.2f} seconds")
        logger.info(f"Phases Completed: {summary['phases_completed']}")
        if summary['phases_failed'] > 0:
            logger.info(f"Phases Failed: {summary['phases_failed']}")

        logger.info("")
        logger.info("CONTENT METRICS:")
        metrics = summary['content_metrics']
        logger.info(f"  Collected: {metrics['collected']} items")
        logger.info(f"  Deduplicated: {metrics['deduplicated']} items")
        logger.info(f"  AI Filtered: {metrics['ai_filtered']} major announcements")
        logger.info(f"  Categorized: {metrics['categorized']} items")
        logger.info(f"  Delivered: {metrics['delivered']} items")

        logger.info("")
        logger.info("PHASE TIMINGS:")
        for phase_key, phase_info in summary['phases'].items():
            logger.info(f"  {phase_key}: {phase_info['duration_seconds']:.2f}s ({phase_info['status']})")

        if summary['error']:
            logger.info("")
            logger.info(f"ERROR: {summary['error']}")

        logger.info("=" * 80)
