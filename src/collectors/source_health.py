"""
Source Health Monitoring Module

Tracks source availability and health metrics.
Implements thresholds for skipping unhealthy sources.
Provides recovery mechanisms for temporarily unavailable sources.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from src.database import DatabaseStorage
from src.database.models import SourceStatus
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)


class SourceHealthError(Exception):
    """Base exception for source health errors."""

    pass


class SourceHealth:
    """
    Monitors and manages source health metrics.

    Features:
    - Track consecutive failures per source
    - Skip sources exceeding failure threshold
    - Mark sources as unhealthy/degraded
    - Provide recovery mechanisms
    - Batch health checks
    - Comprehensive logging
    """

    def __init__(
        self,
        storage: DatabaseStorage,
        failure_threshold: int = 5,
        recovery_hours: int = 24,
    ):
        """
        Initialize source health monitor.

        Args:
            storage: DatabaseStorage instance for reading/updating source status
            failure_threshold: Number of consecutive failures before marking unhealthy (default: 5)
            recovery_hours: Hours to wait before retrying unhealthy source (default: 24)
        """
        self.storage = storage
        self.failure_threshold = failure_threshold
        self.recovery_hours = recovery_hours
        self.logger = get_logger(__name__)

    def is_healthy(self, source_status: Dict[str, Any]) -> bool:
        """
        Check if a source is healthy based on consecutive failures.

        Args:
            source_status: Source status dict from database

        Returns:
            True if source is healthy (failures < threshold), False otherwise
        """
        if not isinstance(source_status, dict):
            self.logger.warning(f"Invalid source_status type: {type(source_status)}")
            return False

        consecutive_failures = source_status.get("consecutive_failures") or 0
        is_healthy = consecutive_failures < self.failure_threshold

        if not is_healthy:
            self.logger.debug(
                f"Source {source_status.get('source_id')} is unhealthy "
                f"({consecutive_failures}/{self.failure_threshold} failures)"
            )

        return is_healthy

    def is_in_recovery(self, source_status: Dict[str, Any]) -> bool:
        """
        Check if an unhealthy source is still in recovery period.

        Args:
            source_status: Source status dict from database

        Returns:
            True if source failed and is still within recovery window, False otherwise
        """
        if not source_status.get("last_error") or not source_status.get("last_error_at"):
            return False

        consecutive_failures = source_status.get("consecutive_failures") or 0
        if consecutive_failures < self.failure_threshold:
            return False

        # Check if within recovery window
        last_error_at = source_status.get("last_error_at")
        if isinstance(last_error_at, str):
            try:
                last_error_at = datetime.fromisoformat(last_error_at)
            except (ValueError, TypeError):
                return False

        recovery_until = last_error_at + timedelta(hours=self.recovery_hours)
        in_recovery = datetime.utcnow() < recovery_until

        if in_recovery:
            time_remaining = (recovery_until - datetime.utcnow()).total_seconds() / 3600
            self.logger.debug(
                f"Source {source_status.get('source_id')} in recovery "
                f"({time_remaining:.1f} hours remaining)"
            )

        return in_recovery

    def can_collect_from_source(self, source_status: Dict[str, Any]) -> bool:
        """
        Determine if we should attempt to collect from this source.

        Args:
            source_status: Source status dict from database

        Returns:
            True if source is healthy or recovery period has expired, False otherwise
        """
        # Healthy sources are always collectable
        if self.is_healthy(source_status):
            return True

        # Unhealthy but not in recovery - can try again
        if not self.is_in_recovery(source_status):
            self.logger.info(
                f"Source {source_status.get('source_id')} recovery period expired, "
                f"attempting collection again"
            )
            return True

        # In recovery period - skip
        return False

    def get_health_status(self, source_status: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get detailed health status of a source.

        Args:
            source_status: Source status dict from database

        Returns:
            {
                'is_healthy': bool,
                'is_in_recovery': bool,
                'can_collect': bool,
                'consecutive_failures': int,
                'failure_threshold': int,
                'last_error': str or None,
                'last_error_at': str or None,
                'recovery_until': str or None
            }
        """
        consecutive_failures = source_status.get("consecutive_failures") or 0
        is_healthy = self.is_healthy(source_status)
        is_in_recovery = self.is_in_recovery(source_status)
        can_collect = self.can_collect_from_source(source_status)

        recovery_until = None
        last_error_at = source_status.get("last_error_at")
        if is_in_recovery and last_error_at:
            if isinstance(last_error_at, str):
                try:
                    last_error_at = datetime.fromisoformat(last_error_at)
                except (ValueError, TypeError):
                    last_error_at = None

            if last_error_at:
                recovery_until = last_error_at + timedelta(hours=self.recovery_hours)

        return {
            "is_healthy": is_healthy,
            "is_in_recovery": is_in_recovery,
            "can_collect": can_collect,
            "consecutive_failures": consecutive_failures,
            "failure_threshold": self.failure_threshold,
            "last_error": source_status.get("last_error"),
            "last_error_at": source_status.get("last_error_at"),
            "recovery_until": recovery_until,
        }

    def mark_failure(self, source_id: str, error_message: str) -> Dict[str, Any]:
        """
        Mark a source as having failed.

        Args:
            source_id: ID of the source
            error_message: Description of the error

        Returns:
            Updated source health status
        """
        try:
            # Get current source status
            source_status = self.storage.get_source_status(source_id)
            if not source_status:
                self.logger.warning(f"Source {source_id} not found in database")
                return {"error": f"Source {source_id} not found"}

            # Increment failures
            new_failures = (source_status.get("consecutive_failures") or 0) + 1

            # Update in database
            updated_status = SourceStatus(
                source_id=source_id,
                source_type=source_status.get("source_type", "unknown"),
                consecutive_failures=new_failures,
                last_error=error_message,
                last_collected_at=datetime.utcnow().isoformat(),
                last_success=source_status.get("last_success"),
            )
            self.storage.update_source_status(updated_status)

            self.logger.warning(
                f"Source {source_id} marked as failed "
                f"({new_failures}/{self.failure_threshold}): {error_message}"
            )

            # Get updated status
            updated = self.storage.get_source_status(source_id)
            return self.get_health_status(updated) if updated else {"error": "Failed to update"}

        except Exception as e:
            self.logger.error(f"Error marking source {source_id} as failed: {e}", exc_info=True)
            return {"error": str(e)}

    def mark_success(self, source_id: str) -> Dict[str, Any]:
        """
        Mark a source as having succeeded.

        Args:
            source_id: ID of the source

        Returns:
            Updated source health status
        """
        try:
            # Get current source status
            source_status = self.storage.get_source_status(source_id)
            if not source_status:
                self.logger.warning(f"Source {source_id} not found in database")
                return {"error": f"Source {source_id} not found"}

            # Reset failures and update success timestamp
            updated_status = SourceStatus(
                source_id=source_id,
                source_type=source_status.get("source_type", "unknown"),
                consecutive_failures=0,
                last_error=None,
                last_collected_at=datetime.utcnow().isoformat(),
                last_success=datetime.utcnow().isoformat(),
            )
            self.storage.update_source_status(updated_status)

            self.logger.info(f"Source {source_id} marked as successful, failures reset")

            # Get updated status
            updated = self.storage.get_source_status(source_id)
            return self.get_health_status(updated) if updated else {"error": "Failed to update"}

        except Exception as e:
            self.logger.error(f"Error marking source {source_id} as successful: {e}", exc_info=True)
            return {"error": str(e)}

    def check_all_sources(self) -> Dict[str, Any]:
        """
        Check health of all sources in database.

        Returns:
            {
                'total': int,
                'healthy': int,
                'unhealthy': int,
                'in_recovery': int,
                'collectable': int,
                'sources': List[{source health details}]
            }
        """
        try:
            all_sources = self.storage.get_all_sources()
            self.logger.debug(f"Checking health of {len(all_sources)} sources")

            if not all_sources:
                return {
                    "total": 0,
                    "healthy": 0,
                    "unhealthy": 0,
                    "in_recovery": 0,
                    "collectable": 0,
                    "sources": [],
                }

            healthy = 0
            unhealthy = 0
            in_recovery = 0
            collectable = 0
            source_details = []

            for source_status in all_sources:
                is_healthy = self.is_healthy(source_status)
                is_in_recovery = self.is_in_recovery(source_status)
                can_collect = self.can_collect_from_source(source_status)

                health = self.get_health_status(source_status)
                health["source_id"] = source_status.get("source_id")
                health["source_type"] = source_status.get("source_type")
                source_details.append(health)

                if is_healthy:
                    healthy += 1
                else:
                    unhealthy += 1

                if is_in_recovery:
                    in_recovery += 1

                if can_collect:
                    collectable += 1

            self.logger.info(
                f"Source health check complete: "
                f"{healthy} healthy, {unhealthy} unhealthy, "
                f"{in_recovery} in recovery, {collectable} collectable"
            )

            return {
                "total": len(all_sources),
                "healthy": healthy,
                "unhealthy": unhealthy,
                "in_recovery": in_recovery,
                "collectable": collectable,
                "sources": source_details,
            }

        except Exception as e:
            self.logger.error(f"Error checking all sources: {e}", exc_info=True)
            return {
                "total": 0,
                "healthy": 0,
                "unhealthy": 0,
                "in_recovery": 0,
                "collectable": 0,
                "sources": [],
                "error": str(e),
            }

    def get_collectable_sources(self) -> Dict[str, Any]:
        """
        Get all sources that can currently be collected from.

        Returns:
            {
                'total': int,
                'collectable': int,
                'skipped': int,
                'sources': List[Dict]
            }
        """
        try:
            all_sources = self.storage.get_all_sources()
            collectable = []
            skipped = []

            for source_status in all_sources:
                if self.can_collect_from_source(source_status):
                    collectable.append(source_status)
                else:
                    skipped.append(source_status)

            self.logger.info(
                f"Source collection filter: {len(collectable)} collectable, "
                f"{len(skipped)} skipped (unhealthy or in recovery)"
            )

            return {
                "total": len(all_sources),
                "collectable": len(collectable),
                "skipped": len(skipped),
                "sources": collectable,
            }

        except Exception as e:
            self.logger.error(f"Error getting collectable sources: {e}", exc_info=True)
            return {
                "total": 0,
                "collectable": 0,
                "skipped": 0,
                "sources": [],
                "error": str(e),
            }

    def reset_all_failures(self) -> Dict[str, int]:
        """
        Reset failure counters for all sources.

        Used after successful collection cycle or manual recovery.

        Returns:
            {
                'total': int,
                'reset': int
            }
        """
        try:
            all_sources = self.storage.get_all_sources()
            reset_count = 0

            for source_status in all_sources:
                if (source_status.get("consecutive_failures") or 0) > 0:
                    updated = SourceStatus(
                        source_id=source_status.get("source_id"),
                        source_type=source_status.get("source_type", "unknown"),
                        consecutive_failures=0,
                        last_error=None,
                        last_collected_at=source_status.get("last_collected_at"),
                        last_success=source_status.get("last_success"),
                    )
                    self.storage.update_source_status(updated)
                    reset_count += 1

            self.logger.info(f"Reset failure counters for {reset_count} sources")

            return {
                "total": len(all_sources),
                "reset": reset_count,
            }

        except Exception as e:
            self.logger.error(f"Error resetting failures: {e}", exc_info=True)
            return {
                "total": 0,
                "reset": 0,
                "error": str(e),
            }

    def update_failure_threshold(self, threshold: int) -> None:
        """
        Update the failure threshold.

        Args:
            threshold: New failure threshold (minimum 1)

        Raises:
            SourceHealthError: If threshold is invalid
        """
        if threshold < 1:
            raise SourceHealthError("Failure threshold must be at least 1")

        old_threshold = self.failure_threshold
        self.failure_threshold = threshold
        self.logger.info(f"Updated failure threshold from {old_threshold} to {threshold}")

    def update_recovery_hours(self, hours: int) -> None:
        """
        Update the recovery period duration.

        Args:
            hours: New recovery period in hours (minimum 1)

        Raises:
            SourceHealthError: If hours is invalid
        """
        if hours < 1:
            raise SourceHealthError("Recovery hours must be at least 1")

        old_hours = self.recovery_hours
        self.recovery_hours = hours
        self.logger.info(f"Updated recovery period from {old_hours} to {hours} hours")
