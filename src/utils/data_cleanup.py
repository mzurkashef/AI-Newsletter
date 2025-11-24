"""
Data cleanup and retention policy management.

Handles automatic cleanup of old data based on configurable retention policies.
Prevents database from growing unbounded while preserving important delivery history.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from src.database.storage import DatabaseStorage
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)


class RetentionPolicy:
    """Configuration for data retention policy."""

    def __init__(
        self,
        raw_content_days: int = 30,
        processed_content_days: int = 90,
        delivery_history_days: int = 365,
        source_status_days: int = 90,
    ):
        """
        Initialize retention policy.

        Args:
            raw_content_days: Days to retain raw collected content (default 30)
            processed_content_days: Days to retain processed/categorized content (default 90)
            delivery_history_days: Days to retain delivery history (default 365 = 1 year)
            source_status_days: Days to retain source status records (default 90)
        """
        self.raw_content_days = raw_content_days
        self.processed_content_days = processed_content_days
        self.delivery_history_days = delivery_history_days
        self.source_status_days = source_status_days

        logger.info(
            f"Retention policy: raw={raw_content_days}d, "
            f"processed={processed_content_days}d, delivery={delivery_history_days}d, "
            f"status={source_status_days}d"
        )


class DataCleanupManager:
    """
    Manages data cleanup operations based on retention policies.

    Features:
    - Automatic cleanup of old data
    - Dry-run capability for preview
    - Detailed cleanup statistics
    - Optional per-table cleanup
    - Logging of cleanup activities
    """

    def __init__(self, storage: DatabaseStorage):
        """
        Initialize data cleanup manager.

        Args:
            storage: DatabaseStorage instance
        """
        if not storage:
            raise ValueError("DatabaseStorage is required")

        self.storage = storage
        self.policy = RetentionPolicy()

        logger.info("Data cleanup manager initialized")

    def set_retention_policy(self, policy: RetentionPolicy) -> None:
        """
        Set custom retention policy.

        Args:
            policy: RetentionPolicy instance
        """
        self.policy = policy
        logger.info(f"Retention policy updated: {policy}")

    def cleanup_raw_content(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Clean up raw content older than retention period.

        Args:
            dry_run: If True, only report what would be deleted

        Returns:
            Cleanup statistics
        """
        return self._cleanup_table(
            table_name="raw_content",
            retention_days=self.policy.raw_content_days,
            date_column="collected_at",
            dry_run=dry_run,
        )

    def cleanup_processed_content(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Clean up processed content older than retention period.

        Args:
            dry_run: If True, only report what would be deleted

        Returns:
            Cleanup statistics
        """
        return self._cleanup_table(
            table_name="processed_content",
            retention_days=self.policy.processed_content_days,
            date_column="processed_at",
            dry_run=dry_run,
        )

    def cleanup_delivery_history(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Clean up delivery history older than retention period.

        Args:
            dry_run: If True, only report what would be deleted

        Returns:
            Cleanup statistics
        """
        # Note: Delivery history uses 'delivered_at' column
        # Placeholder for now - would need database schema verification
        return {
            "table": "delivery_history",
            "records_deleted": 0,
            "dry_run": dry_run,
            "message": "Not yet implemented - verify schema first",
        }

    def cleanup_source_status(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Clean up source status older than retention period.

        Args:
            dry_run: If True, only report what would be deleted

        Returns:
            Cleanup statistics
        """
        return self._cleanup_table(
            table_name="source_status",
            retention_days=self.policy.source_status_days,
            date_column="updated_at",
            dry_run=dry_run,
        )

    def _cleanup_table(
        self,
        table_name: str,
        retention_days: int,
        date_column: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Generic cleanup function for any table.

        Args:
            table_name: Name of table to clean
            retention_days: Days to retain
            date_column: Date column name for comparison
            dry_run: If True, only report what would be deleted

        Returns:
            Cleanup statistics
        """
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=retention_days)).isoformat()

            # Count records to be deleted
            count_query = f"SELECT COUNT(*) as count FROM {table_name} WHERE {date_column} < ?"
            result = self.storage.query(count_query, [cutoff_date])
            records_to_delete = result[0]["count"] if result else 0

            if dry_run:
                logger.info(
                    f"Cleanup dry-run for {table_name}: "
                    f"would delete {records_to_delete} records older than {cutoff_date}"
                )
                return {
                    "table": table_name,
                    "records_deleted": records_to_delete,
                    "cutoff_date": cutoff_date,
                    "dry_run": True,
                    "message": f"Dry-run: would delete {records_to_delete} records",
                }

            # Actually delete records
            if records_to_delete > 0:
                delete_query = f"DELETE FROM {table_name} WHERE {date_column} < ?"
                self.storage.execute(delete_query, [cutoff_date])

                logger.info(
                    f"Cleanup completed for {table_name}: "
                    f"deleted {records_to_delete} records older than {cutoff_date}"
                )

            return {
                "table": table_name,
                "records_deleted": records_to_delete,
                "cutoff_date": cutoff_date,
                "dry_run": False,
                "message": f"Deleted {records_to_delete} records",
            }

        except Exception as e:
            logger.error(f"Error cleaning up {table_name}: {e}")
            return {
                "table": table_name,
                "records_deleted": 0,
                "error": str(e),
                "dry_run": dry_run,
            }

    def cleanup_all(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Run cleanup on all tables.

        Args:
            dry_run: If True, only report what would be deleted

        Returns:
            Summary of cleanup operations
        """
        logger.info(f"Starting cleanup_all (dry_run={dry_run})")

        results = {
            "raw_content": self.cleanup_raw_content(dry_run=dry_run),
            "processed_content": self.cleanup_processed_content(dry_run=dry_run),
            "delivery_history": self.cleanup_delivery_history(dry_run=dry_run),
            "source_status": self.cleanup_source_status(dry_run=dry_run),
        }

        total_deleted = sum(
            r.get("records_deleted", 0) for r in results.values()
            if isinstance(r, dict)
        )

        logger.info(
            f"Cleanup_all completed: {total_deleted} total records deleted (dry_run={dry_run})"
        )

        return {
            "success": True,
            "dry_run": dry_run,
            "total_deleted": total_deleted,
            "by_table": results,
        }

    def get_database_statistics(self) -> Dict[str, Any]:
        """
        Get current database statistics.

        Returns:
            Database size and record counts
        """
        try:
            stats = {}

            # Count raw content
            result = self.storage.query("SELECT COUNT(*) as count FROM raw_content")
            stats["raw_content_count"] = result[0]["count"] if result else 0

            # Count processed content
            result = self.storage.query("SELECT COUNT(*) as count FROM processed_content")
            stats["processed_content_count"] = result[0]["count"] if result else 0

            # Count delivery history
            result = self.storage.query("SELECT COUNT(*) as count FROM delivery_history")
            stats["delivery_history_count"] = result[0]["count"] if result else 0

            # Count source status
            result = self.storage.query("SELECT COUNT(*) as count FROM source_status")
            stats["source_status_count"] = result[0]["count"] if result else 0

            total_records = sum(stats.values())
            stats["total_records"] = total_records

            logger.info(f"Database statistics: {total_records} total records")

            return stats

        except Exception as e:
            logger.error(f"Error getting database statistics: {e}")
            return {"error": str(e)}

    def cleanup_recommendation(self) -> Dict[str, Any]:
        """
        Get recommendations for cleanup.

        Returns:
            Cleanup recommendations based on current database state
        """
        try:
            stats = self.get_database_statistics()

            recommendations = {
                "should_cleanup": False,
                "reason": "Database size is normal",
                "actions": [],
            }

            total = stats.get("total_records", 0)

            # If more than 100k records, recommend cleanup
            if total > 100000:
                recommendations["should_cleanup"] = True
                recommendations["reason"] = f"Large database ({total} records)"
                recommendations["actions"].append("Run cleanup_all() to free space")

            # Specific recommendations by table
            if stats.get("raw_content_count", 0) > 50000:
                recommendations["actions"].append("Consider reducing raw_content retention")

            if stats.get("processed_content_count", 0) > 50000:
                recommendations["actions"].append("Consider reducing processed_content retention")

            logger.info(f"Cleanup recommendation: {recommendations['reason']}")

            return recommendations

        except Exception as e:
            logger.error(f"Error generating cleanup recommendations: {e}")
            return {"error": str(e)}
