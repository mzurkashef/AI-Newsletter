"""
Database storage layer for AI Newsletter system.

Handles SQLite database connection management, schema initialization,
and CRUD operations for all data models.
"""

import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Dict, Any, List

from .models import (
    DatabaseSchema,
    SCHEMA_VERSION,
    RawContent,
    ProcessedContent,
    DeliveryHistory,
    SourceStatus,
)

logger = logging.getLogger(__name__)


class DatabaseStorage:
    """SQLite database storage layer."""

    def __init__(self, db_path: str = "data/newsletter.db"):
        """
        Initialize database storage.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_db_directory()
        logger.info(f"Initializing database storage at {db_path}")

    def _ensure_db_directory(self) -> None:
        """Ensure database directory exists."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Database directory ready: {db_dir}")

    @contextmanager
    def _get_connection(self):
        """
        Get a database connection with proper resource cleanup.

        Yields:
            sqlite3.Connection: Database connection
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            conn.close()

    def initialize_schema(self) -> None:
        """
        Create database tables and indexes if they don't exist.

        This method is idempotent - safe to call multiple times.
        """
        logger.info("Initializing database schema")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create all tables
            for statement in DatabaseSchema.get_all_create_statements():
                cursor.execute(statement)
                logger.debug("Table creation statement executed")

            # Create indexes
            for statement in DatabaseSchema.get_all_index_statements():
                cursor.execute(statement)
                logger.debug("Index creation statement executed")

            # Initialize schema version
            cursor.execute(
                "INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, ?)",
                (SCHEMA_VERSION,),
            )

        logger.info("Database schema initialized successfully")

    def store_raw_content(self, content: RawContent) -> int:
        """
        Store raw content and return its ID.

        Args:
            content: RawContent object to store

        Returns:
            int: ID of the stored content
        """
        data = content.to_dict()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO raw_content
                (source_type, source_url, content_text, content_url, title,
                 published_at, collected_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["source_type"],
                    data["source_url"],
                    data["content_text"],
                    data["content_url"],
                    data["title"],
                    data["published_at"],
                    data["collected_at"],
                    data["metadata"],
                ),
            )
            content_id = cursor.lastrowid

        logger.debug(f"Stored raw content with ID {content_id}")
        return content_id

    def get_raw_content(self, content_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve raw content by ID.

        Args:
            content_id: ID of the content to retrieve

        Returns:
            Dict with content data or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM raw_content WHERE id = ?", (content_id,))
            row = cursor.fetchone()

        if row is None:
            logger.debug(f"Raw content with ID {content_id} not found")
            return None

        return dict(row)

    def get_raw_content_by_source(
        self, source_url: str, source_type: str
    ) -> List[Dict[str, Any]]:
        """
        Retrieve raw content by source URL and type.

        Args:
            source_url: Source URL
            source_type: Source type ('newsletter' or 'youtube')

        Returns:
            List of content dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM raw_content WHERE source_url = ? AND source_type = ? ORDER BY collected_at DESC",
                (source_url, source_type),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def store_processed_content(self, content: ProcessedContent) -> int:
        """
        Store processed content and return its ID.

        Args:
            content: ProcessedContent object to store

        Returns:
            int: ID of the stored processed content
        """
        data = content.to_dict()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO processed_content
                (raw_content_id, summary, category, importance_score, processed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    data["raw_content_id"],
                    data["summary"],
                    data["category"],
                    data["importance_score"],
                    data["processed_at"],
                ),
            )
            processed_id = cursor.lastrowid

        logger.debug(f"Stored processed content with ID {processed_id}")
        return processed_id

    def get_processed_content(self, content_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve processed content by ID.

        Args:
            content_id: ID of the processed content to retrieve

        Returns:
            Dict with processed content data or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM processed_content WHERE id = ?", (content_id,))
            row = cursor.fetchone()

        if row is None:
            logger.debug(f"Processed content with ID {content_id} not found")
            return None

        return dict(row)

    def get_processed_content_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Retrieve processed content by category.

        Args:
            category: Category name

        Returns:
            List of processed content dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM processed_content WHERE category = ? ORDER BY processed_at DESC",
                (category,),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def store_delivery_history(self, delivery: DeliveryHistory) -> int:
        """
        Store delivery history and return its ID.

        Args:
            delivery: DeliveryHistory object to store

        Returns:
            int: ID of the stored delivery history
        """
        data = delivery.to_dict()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO delivery_history
                (newsletter_content, delivered_at, delivery_status,
                 telegram_message_id, error_message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    data["newsletter_content"],
                    data["delivered_at"],
                    data["delivery_status"],
                    data["telegram_message_id"],
                    data["error_message"],
                ),
            )
            delivery_id = cursor.lastrowid

        logger.debug(f"Stored delivery history with ID {delivery_id}")
        return delivery_id

    def get_delivery_history(self, delivery_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve delivery history by ID.

        Args:
            delivery_id: ID of the delivery history to retrieve

        Returns:
            Dict with delivery history data or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM delivery_history WHERE id = ?", (delivery_id,))
            row = cursor.fetchone()

        if row is None:
            logger.debug(f"Delivery history with ID {delivery_id} not found")
            return None

        return dict(row)

    def get_delivery_history_by_status(self, status: str) -> List[Dict[str, Any]]:
        """
        Retrieve delivery history by delivery status.

        Args:
            status: Delivery status ('success', 'failure', or 'partial')

        Returns:
            List of delivery history dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM delivery_history WHERE delivery_status = ? ORDER BY delivered_at DESC",
                (status,),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def update_source_status(self, status: SourceStatus) -> None:
        """
        Update source status (insert or update).

        Args:
            status: SourceStatus object to store/update
        """
        data = status.to_dict()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO source_status
                (source_id, source_type, last_collected_at, last_success,
                 last_error, consecutive_failures)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    source_type = excluded.source_type,
                    last_collected_at = excluded.last_collected_at,
                    last_success = excluded.last_success,
                    last_error = excluded.last_error,
                    consecutive_failures = excluded.consecutive_failures,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    data["source_id"],
                    data["source_type"],
                    data["last_collected_at"],
                    data["last_success"],
                    data["last_error"],
                    data["consecutive_failures"],
                ),
            )

        logger.debug(f"Updated source status for {status.source_id}")

    def get_source_status(self, source_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve source status by ID.

        Args:
            source_id: Source identifier

        Returns:
            Dict with source status data or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM source_status WHERE source_id = ?", (source_id,))
            row = cursor.fetchone()

        if row is None:
            logger.debug(f"Source status for {source_id} not found")
            return None

        return dict(row)

    def get_all_sources(self) -> List[Dict[str, Any]]:
        """
        Retrieve all source statuses.

        Returns:
            List of source status dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM source_status ORDER BY source_type, source_id")
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_sources_by_type(self, source_type: str) -> List[Dict[str, Any]]:
        """
        Retrieve sources by type.

        Args:
            source_type: Source type ('newsletter' or 'youtube')

        Returns:
            List of source status dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM source_status WHERE source_type = ? ORDER BY source_id",
                (source_type,),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def delete_raw_content(self, content_id: int) -> bool:
        """
        Delete raw content by ID.

        Args:
            content_id: ID of the content to delete

        Returns:
            bool: True if deleted, False if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM raw_content WHERE id = ?", (content_id,))
            deleted = cursor.rowcount > 0

        if deleted:
            logger.debug(f"Deleted raw content with ID {content_id}")
        else:
            logger.debug(f"Raw content with ID {content_id} not found for deletion")

        return deleted

    def get_unprocessed_content(self) -> List[Dict[str, Any]]:
        """
        Retrieve raw content that hasn't been processed yet.

        Returns:
            List of raw content dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT rc.* FROM raw_content rc
                LEFT JOIN processed_content pc ON rc.id = pc.raw_content_id
                WHERE pc.id IS NULL
                ORDER BY rc.collected_at DESC
                """
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_delivery_stats(self) -> Dict[str, int]:
        """
        Get delivery statistics.

        Returns:
            Dict with counts by delivery status
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT delivery_status, COUNT(*) as count
                FROM delivery_history
                GROUP BY delivery_status
                """
            )
            rows = cursor.fetchall()

        stats = {row["delivery_status"]: row["count"] for row in rows}
        return stats
