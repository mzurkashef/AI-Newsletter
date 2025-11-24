"""Delivery status tracking and reporting for newsletters."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from src.database.storage import DatabaseStorage
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)


class DeliveryStatus(str, Enum):
    """Enumeration of delivery statuses."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


@dataclass
class DeliveryRecord:
    """Represents a delivery history record."""

    id: Optional[int] = None
    newsletter_content: str = ""
    delivered_at: str = ""
    delivery_status: str = DeliveryStatus.SUCCESS
    telegram_message_id: str = ""
    telegram_chat_id: int = 0
    error_message: Optional[str] = None
    message_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "newsletter_content": self.newsletter_content,
            "delivered_at": self.delivered_at,
            "delivery_status": self.delivery_status,
            "telegram_message_id": self.telegram_message_id,
            "telegram_chat_id": self.telegram_chat_id,
            "error_message": self.error_message,
        }


class DeliveryStatusTracker:
    """Tracks and queries newsletter delivery status.

    Manages delivery history storage and provides querying capabilities
    for monitoring delivery reliability and troubleshooting issues.
    """

    def __init__(self, storage: DatabaseStorage) -> None:
        """Initialize delivery status tracker.

        Args:
            storage: DatabaseStorage instance for accessing delivery_history table

        Raises:
            ValueError: If storage is None
        """
        if not storage:
            raise ValueError("DatabaseStorage is required for status tracking")

        self.storage = storage
        logger.info("Initialized DeliveryStatusTracker")

    def record_delivery(
        self,
        newsletter_content: str,
        chat_id: int,
        status: str,
        message_ids: Optional[List[int]] = None,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a delivery attempt in history.

        Args:
            newsletter_content: The newsletter content that was sent
            chat_id: Telegram chat ID where sent
            status: Delivery status (success, failure, partial)
            message_ids: List of Telegram message IDs if successful
            error_message: Error message if delivery failed

        Returns:
            Dictionary with:
                - success: Whether record was stored
                - record_id: Database record ID
                - timestamp: When delivery was recorded

        Raises:
            ValueError: If status is invalid or required fields missing
        """
        # Validate status
        valid_statuses = [DeliveryStatus.SUCCESS, DeliveryStatus.FAILURE, DeliveryStatus.PARTIAL]
        if status not in valid_statuses:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {valid_statuses}"
            )

        # Validate required fields
        if not newsletter_content:
            raise ValueError("newsletter_content cannot be empty")

        if not isinstance(chat_id, int):
            raise ValueError("chat_id must be an integer")

        try:
            # Format message IDs
            message_ids_str = (
                ",".join(str(mid) for mid in message_ids)
                if message_ids
                else ""
            )

            # Create record
            record = DeliveryRecord(
                newsletter_content=newsletter_content,
                delivered_at=datetime.utcnow().isoformat(),
                delivery_status=status,
                telegram_message_id=message_ids_str,
                telegram_chat_id=chat_id,
                error_message=error_message,
                message_count=len(message_ids) if message_ids else 0,
            )

            # Store in database
            self.storage.insert("delivery_history", record.to_dict())

            logger.info(
                f"Delivery recorded: status={status}, chat={chat_id}, "
                f"messages={record.message_count}"
            )

            return {
                "success": True,
                "timestamp": record.delivered_at,
                "status": status,
                "message_count": record.message_count,
            }

        except Exception as e:
            logger.error(f"Failed to record delivery: {e}")
            raise

    def get_delivery_history(
        self,
        chat_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Get delivery history with optional filtering.

        Args:
            chat_id: Optional chat ID to filter by
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            Dictionary with:
                - records: List of delivery records
                - total_count: Total matching records
                - limit: Limit used
                - offset: Offset used
        """
        try:
            # Build query
            query = "SELECT * FROM delivery_history"
            params = []

            if chat_id:
                query += " WHERE telegram_chat_id = ?"
                params.append(chat_id)

            # Order by timestamp descending (newest first)
            query += " ORDER BY delivered_at DESC"

            # Add limit and offset
            query += f" LIMIT {limit} OFFSET {offset}"

            # Execute query
            records = self.storage.query(query, params)

            # Get total count
            count_query = "SELECT COUNT(*) as count FROM delivery_history"
            if chat_id:
                count_query += " WHERE telegram_chat_id = ?"
                count_result = self.storage.query(count_query, [chat_id])
            else:
                count_result = self.storage.query(count_query)

            total_count = count_result[0]["count"] if count_result else 0

            logger.debug(
                f"Retrieved {len(records)} delivery records "
                f"(total: {total_count}, limit: {limit}, offset: {offset})"
            )

            return {
                "records": records,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
            }

        except Exception as e:
            logger.error(f"Failed to retrieve delivery history: {e}")
            raise

    def get_delivery_statistics(
        self, days: int = 30, chat_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get delivery statistics for a time period.

        Args:
            days: Number of days to include in statistics
            chat_id: Optional chat ID to filter by

        Returns:
            Dictionary with:
                - period_days: Days included
                - total_deliveries: Total delivery attempts
                - successful: Count of successful deliveries
                - partial: Count of partial deliveries
                - failures: Count of failed deliveries
                - success_rate: Percentage of successful deliveries
                - total_messages: Total messages sent
                - average_messages: Average messages per delivery
        """
        try:
            # Calculate start time
            start_time = (
                datetime.utcnow() - timedelta(days=days)
            ).isoformat()

            # Build query
            query = "SELECT delivery_status, COUNT(*) as count FROM delivery_history"
            query += " WHERE delivered_at >= ?"
            params = [start_time]

            if chat_id:
                query += " AND telegram_chat_id = ?"
                params.append(chat_id)

            query += " GROUP BY delivery_status"

            # Execute query
            results = self.storage.query(query, params)

            # Process results
            stats = {
                "period_days": days,
                "total_deliveries": 0,
                "successful": 0,
                "partial": 0,
                "failures": 0,
                "success_rate": 0.0,
                "total_messages": 0,
                "average_messages": 0.0,
            }

            for row in results:
                status = row.get("delivery_status", "")
                count = row.get("count", 0)

                stats["total_deliveries"] += count

                if status == DeliveryStatus.SUCCESS:
                    stats["successful"] += count
                elif status == DeliveryStatus.PARTIAL:
                    stats["partial"] += count
                elif status == DeliveryStatus.FAILURE:
                    stats["failures"] += count

            # Calculate success rate
            if stats["total_deliveries"] > 0:
                stats["success_rate"] = (
                    (
                        stats["successful"]
                        + stats["partial"] * 0.5
                    )
                    / stats["total_deliveries"]
                    * 100
                )

            # Get message counts
            msg_query = (
                "SELECT SUM(CASE WHEN telegram_message_id != '' "
                "THEN LENGTH(telegram_message_id) - LENGTH(REPLACE(telegram_message_id, ',', '')) + 1 "
                "ELSE 0 END) as total_messages FROM delivery_history"
            )
            msg_query += " WHERE delivered_at >= ?"
            msg_params = [start_time]

            if chat_id:
                msg_query += " AND telegram_chat_id = ?"
                msg_params.append(chat_id)

            msg_result = self.storage.query(msg_query, msg_params)
            if msg_result and msg_result[0].get("total_messages"):
                stats["total_messages"] = msg_result[0]["total_messages"]

                if stats["total_deliveries"] > 0:
                    stats["average_messages"] = (
                        stats["total_messages"] / stats["total_deliveries"]
                    )

            logger.info(
                f"Delivery statistics: {stats['total_deliveries']} deliveries, "
                f"success_rate={stats['success_rate']:.1f}%"
            )

            return stats

        except Exception as e:
            logger.error(f"Failed to calculate delivery statistics: {e}")
            raise

    def get_failures(
        self, limit: int = 50, days: int = 30
    ) -> Dict[str, Any]:
        """Get recent delivery failures for troubleshooting.

        Args:
            limit: Maximum number of failures to return
            days: Number of days to look back

        Returns:
            Dictionary with:
                - failures: List of failed deliveries
                - count: Number of failures
                - period_days: Days looked back
        """
        try:
            start_time = (
                datetime.utcnow() - timedelta(days=days)
            ).isoformat()

            query = (
                "SELECT * FROM delivery_history "
                "WHERE delivery_status = ? AND delivered_at >= ? "
                "ORDER BY delivered_at DESC LIMIT ?"
            )
            params = [DeliveryStatus.FAILURE, start_time, limit]

            failures = self.storage.query(query, params)

            logger.debug(
                f"Retrieved {len(failures)} delivery failures "
                f"from last {days} days"
            )

            return {
                "failures": failures,
                "count": len(failures),
                "period_days": days,
            }

        except Exception as e:
            logger.error(f"Failed to retrieve failures: {e}")
            raise

    def get_recent_status(
        self, chat_id: Optional[int] = None, limit: int = 10
    ) -> Dict[str, Any]:
        """Get most recent delivery status for quick monitoring.

        Args:
            chat_id: Optional chat ID to filter by
            limit: Number of recent deliveries to return

        Returns:
            Dictionary with:
                - recent: List of recent deliveries
                - latest_status: Most recent delivery status
                - latest_timestamp: Most recent delivery timestamp
        """
        try:
            query = "SELECT * FROM delivery_history"
            params = []

            if chat_id:
                query += " WHERE telegram_chat_id = ?"
                params.append(chat_id)

            query += " ORDER BY delivered_at DESC LIMIT ?"
            params.append(limit)

            recent = self.storage.query(query, params)

            latest_status = None
            latest_timestamp = None

            if recent:
                latest_status = recent[0].get("delivery_status")
                latest_timestamp = recent[0].get("delivered_at")

            logger.debug(
                f"Retrieved {len(recent)} recent deliveries, "
                f"latest_status={latest_status}"
            )

            return {
                "recent": recent,
                "latest_status": latest_status,
                "latest_timestamp": latest_timestamp,
                "count": len(recent),
            }

        except Exception as e:
            logger.error(f"Failed to retrieve recent status: {e}")
            raise

    def cleanup_old_records(
        self, days: int = 90, dry_run: bool = False
    ) -> Dict[str, Any]:
        """Clean up old delivery records based on retention policy.

        Args:
            days: Days of records to keep (older records deleted)
            dry_run: If True, only report what would be deleted

        Returns:
            Dictionary with:
                - success: Whether cleanup succeeded
                - records_deleted: Number of records deleted (or would delete)
                - cutoff_date: Date before which records are deleted
        """
        try:
            cutoff_date = (
                datetime.utcnow() - timedelta(days=days)
            ).isoformat()

            # Count records to be deleted
            count_query = (
                "SELECT COUNT(*) as count FROM delivery_history "
                "WHERE delivered_at < ?"
            )
            count_result = self.storage.query(count_query, [cutoff_date])
            records_to_delete = (
                count_result[0]["count"] if count_result else 0
            )

            if dry_run:
                logger.info(
                    f"Cleanup dry-run: would delete {records_to_delete} "
                    f"records older than {cutoff_date}"
                )

                return {
                    "success": True,
                    "records_deleted": records_to_delete,
                    "cutoff_date": cutoff_date,
                    "dry_run": True,
                }

            # Delete old records
            delete_query = (
                "DELETE FROM delivery_history WHERE delivered_at < ?"
            )
            self.storage.execute(delete_query, [cutoff_date])

            logger.info(
                f"Cleanup completed: deleted {records_to_delete} records "
                f"older than {cutoff_date}"
            )

            return {
                "success": True,
                "records_deleted": records_to_delete,
                "cutoff_date": cutoff_date,
                "dry_run": False,
            }

        except Exception as e:
            logger.error(f"Failed to cleanup old records: {e}")
            raise

    def get_chat_summary(
        self, chat_id: int, days: int = 30
    ) -> Dict[str, Any]:
        """Get delivery summary for a specific chat.

        Args:
            chat_id: Telegram chat ID
            days: Number of days to include

        Returns:
            Dictionary with:
                - chat_id: The chat ID
                - period_days: Days included
                - total_deliveries: Total delivery attempts
                - statistics: Detailed statistics
                - recent: Recent deliveries
                - failures: Recent failures
        """
        try:
            if not isinstance(chat_id, int):
                raise ValueError("chat_id must be an integer")

            stats = self.get_delivery_statistics(days=days, chat_id=chat_id)
            recent = self.get_recent_status(chat_id=chat_id, limit=10)
            failures = self.get_failures(limit=10, days=days)

            # Filter failures to this chat
            chat_failures = [
                f for f in failures.get("failures", [])
                if f.get("telegram_chat_id") == chat_id
            ]

            logger.info(
                f"Generated chat summary for chat {chat_id}: "
                f"{stats['total_deliveries']} deliveries, "
                f"success_rate={stats['success_rate']:.1f}%"
            )

            return {
                "chat_id": chat_id,
                "period_days": days,
                "total_deliveries": stats["total_deliveries"],
                "statistics": stats,
                "recent": recent["recent"],
                "failures": chat_failures,
            }

        except Exception as e:
            logger.error(f"Failed to generate chat summary: {e}")
            raise
