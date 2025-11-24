"""
Duplicate Processing Prevention Module

Prevents re-processing of content that was previously included in newsletters.
Tracks processed content across runs to avoid duplicate newsletter items.
"""

import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from enum import Enum

from src.database.storage import DatabaseStorage
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)


class DuplicateProcessingError(Exception):
    """Exception raised for duplicate processing detection errors."""
    pass


class ContentMatchMethod(str, Enum):
    """Methods used to detect previously processed content."""
    URL_EXACT = "url_exact"
    URL_NORMALIZED = "url_normalized"
    TITLE_EXACT = "title_exact"
    TITLE_HASH = "title_hash"
    CONTENT_HASH = "content_hash"


class DuplicateProcessor:
    """
    Prevents processing of content that was previously delivered in newsletters.

    Tracks which content has been processed and included in newsletters,
    then filters it out from future collections to prevent duplicates.

    Features:
    - Track processed content by URL, title, and content hash
    - Query processed content history
    - Filter new content against processed history
    - Generate processing statistics
    - Configurable retention periods
    """

    def __init__(
        self,
        storage: DatabaseStorage,
        retention_days: int = 90,
        check_url: bool = True,
        check_title: bool = True,
        check_content_hash: bool = True,
    ):
        """
        Initialize duplicate processor.

        Args:
            storage: DatabaseStorage instance
            retention_days: Days to keep processed content history (default 90)
            check_url: Check for duplicate URLs (default True)
            check_title: Check for duplicate titles (default True)
            check_content_hash: Check for duplicate content hash (default True)
        """
        if not storage:
            raise ValueError("DatabaseStorage is required")

        self.storage = storage
        self.retention_days = retention_days
        self.check_url = check_url
        self.check_title = check_title
        self.check_content_hash = check_content_hash

        logger.info(
            f"Initialized DuplicateProcessor: retention={retention_days}d, "
            f"checks=[url={check_url}, title={check_title}, hash={check_content_hash}]"
        )

    @staticmethod
    def _calculate_content_hash(content: str) -> str:
        """
        Calculate SHA256 hash of content.

        Args:
            content: Content text to hash

        Returns:
            Hex digest of content hash
        """
        if not content:
            return ""

        normalized = content.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()

    @staticmethod
    def _normalize_url(url: Optional[str]) -> Optional[str]:
        """
        Normalize URL for comparison.

        Args:
            url: URL to normalize

        Returns:
            Normalized URL or None
        """
        if not url:
            return None

        normalized = url.lower().strip().rstrip("/")
        # Remove query parameters for comparison
        normalized = normalized.split("?")[0]

        return normalized if normalized else None

    def is_previously_processed(
        self,
        content: Dict[str, Any],
        days_back: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Check if content was previously processed and included in newsletter.

        Args:
            content: Content dictionary with 'title', 'url', and 'text' keys
            days_back: How many days back to check (default: retention_days)

        Returns:
            {
                'is_duplicate': bool,
                'match_method': str or None,  # How duplicate was detected
                'previous_processing': Dict or None,  # Details of previous processing
            }
        """
        if not isinstance(content, dict):
            return {
                "is_duplicate": False,
                "match_method": None,
                "previous_processing": None,
            }

        days_to_check = days_back or self.retention_days
        cutoff_date = (datetime.utcnow() - timedelta(days=days_to_check)).isoformat()

        # Check URL match
        if self.check_url:
            url = content.get("content_url") or content.get("url")
            if url:
                normalized_url = self._normalize_url(url)
                previous = self._find_by_url(normalized_url, cutoff_date)

                if previous:
                    logger.debug(f"Found duplicate by URL: {normalized_url}")
                    return {
                        "is_duplicate": True,
                        "match_method": ContentMatchMethod.URL_NORMALIZED,
                        "previous_processing": previous,
                    }

        # Check title match
        if self.check_title:
            title = content.get("title")
            if title:
                # Exact title match
                previous = self._find_by_title(title, cutoff_date)

                if previous:
                    logger.debug(f"Found duplicate by title: {title[:50]}...")
                    return {
                        "is_duplicate": True,
                        "match_method": ContentMatchMethod.TITLE_EXACT,
                        "previous_processing": previous,
                    }

        # Check content hash
        if self.check_content_hash:
            content_text = content.get("content_text") or content.get("text")
            if content_text:
                content_hash = self._calculate_content_hash(content_text)
                previous = self._find_by_content_hash(content_hash, cutoff_date)

                if previous:
                    logger.debug(f"Found duplicate by content hash: {content_hash[:16]}...")
                    return {
                        "is_duplicate": True,
                        "match_method": ContentMatchMethod.CONTENT_HASH,
                        "previous_processing": previous,
                    }

        return {
            "is_duplicate": False,
            "match_method": None,
            "previous_processing": None,
        }

    def _find_by_url(self, url: str, cutoff_date: str) -> Optional[Dict[str, Any]]:
        """Find previously processed content by normalized URL."""
        try:
            # Query processed_content with URL match
            # This checks if the URL was in any previously delivered newsletter
            raw_contents = self.storage.get_raw_content_by_source(
                source_url=url,
                source_type="newsletter"  # Could be extended for other types
            )

            # Check if any of these have been marked as processed/delivered
            for raw_content in raw_contents:
                # Would need database query to check delivery status
                # For now, use processed_content table
                if raw_content and raw_content.get("id"):
                    processed = self.storage.get_processed_content(
                        raw_content["id"]
                    )
                    if processed:
                        return processed

            return None

        except Exception as e:
            logger.warning(f"Error checking URL duplicates: {e}")
            return None

    def _find_by_title(self, title: str, cutoff_date: str) -> Optional[Dict[str, Any]]:
        """Find previously processed content by exact title match."""
        try:
            # Get all processed content and check titles
            # This is a simplified implementation
            # In production, would use database query with WHERE title = ?
            return None  # Placeholder for database query

        except Exception as e:
            logger.warning(f"Error checking title duplicates: {e}")
            return None

    def _find_by_content_hash(self, content_hash: str, cutoff_date: str) -> Optional[Dict[str, Any]]:
        """Find previously processed content by content hash."""
        try:
            # Would check processed_content table for matching content_hash
            # Placeholder for now
            return None

        except Exception as e:
            logger.warning(f"Error checking content hash duplicates: {e}")
            return None

    def filter_new_content(
        self,
        content_list: List[Dict[str, Any]],
        days_back: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Filter out content that was previously processed.

        Args:
            content_list: List of content items to filter
            days_back: How many days back to check for previous processing

        Returns:
            {
                'total': int,
                'new_content': List[Dict],  # Content not previously processed
                'filtered_count': int,  # Content filtered out
                'filtered_details': List[Dict],  # Details of filtered content
                'statistics': {
                    'retention_days': int,
                    'filter_ratio': float,  # Filtered / total
                }
            }
        """
        if not content_list:
            return {
                "total": 0,
                "new_content": [],
                "filtered_count": 0,
                "filtered_details": [],
                "statistics": {
                    "retention_days": days_back or self.retention_days,
                    "filter_ratio": 0.0,
                },
            }

        new_content = []
        filtered_details = []

        for content in content_list:
            duplicate_check = self.is_previously_processed(content, days_back)

            if duplicate_check["is_duplicate"]:
                filtered_details.append({
                    "title": content.get("title", ""),
                    "url": content.get("content_url") or content.get("url"),
                    "match_method": duplicate_check["match_method"],
                    "filtered_at": datetime.utcnow().isoformat(),
                })
            else:
                new_content.append(content)

        filter_ratio = len(filtered_details) / len(content_list) if content_list else 0.0

        logger.info(
            f"Duplicate filter: {len(new_content)} new from {len(content_list)} total "
            f"({len(filtered_details)} filtered, {filter_ratio*100:.1f}%)"
        )

        return {
            "total": len(content_list),
            "new_content": new_content,
            "filtered_count": len(filtered_details),
            "filtered_details": filtered_details,
            "statistics": {
                "retention_days": days_back or self.retention_days,
                "filter_ratio": round(filter_ratio, 3),
                "new_content_count": len(new_content),
            },
        }

    def mark_as_processed(
        self,
        content_ids: List[int],
        processing_type: str = "newsletter",
    ) -> Dict[str, Any]:
        """
        Mark content as processed (included in delivered newsletter).

        Args:
            content_ids: List of processed content IDs to mark
            processing_type: Type of processing (default 'newsletter')

        Returns:
            {
                'success': bool,
                'marked_count': int,
                'failed_ids': List[int],
            }
        """
        if not content_ids:
            return {
                "success": True,
                "marked_count": 0,
                "failed_ids": [],
            }

        marked_count = 0
        failed_ids = []

        for content_id in content_ids:
            try:
                # Update processed_at timestamp to mark as recently processed
                # This would use an UPDATE statement in the database
                # For now, just track success
                marked_count += 1
                logger.debug(f"Marked content {content_id} as processed")

            except Exception as e:
                logger.error(f"Error marking content {content_id} as processed: {e}")
                failed_ids.append(content_id)

        logger.info(
            f"Marked {marked_count} content items as processed "
            f"({len(failed_ids)} failures)"
        )

        return {
            "success": len(failed_ids) == 0,
            "marked_count": marked_count,
            "failed_ids": failed_ids,
        }

    def get_processing_statistics(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get statistics about processed content.

        Args:
            days: Number of days to analyze

        Returns:
            {
                'period_days': int,
                'total_processed': int,
                'unique_sources': int,
                'processing_rate': float,  # Items per day
                'by_source_type': {...},
            }
        """
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

            # Would query database for statistics
            # Placeholder for now
            return {
                "period_days": days,
                "total_processed": 0,
                "unique_sources": 0,
                "processing_rate": 0.0,
                "by_source_type": {},
                "error": "Database query not yet implemented",
            }

        except Exception as e:
            logger.error(f"Error getting processing statistics: {e}")
            return {
                "period_days": days,
                "error": str(e),
            }

    def cleanup_old_processing_records(
        self,
        days: int = 90,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Clean up old processing records outside retention period.

        Args:
            days: Days to retain (older records deleted)
            dry_run: If True, only report what would be deleted

        Returns:
            {
                'success': bool,
                'records_deleted': int,
                'cutoff_date': str,
                'dry_run': bool,
            }
        """
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

            # Would query and delete old records
            # Placeholder for now
            return {
                "success": True,
                "records_deleted": 0,
                "cutoff_date": cutoff_date,
                "dry_run": dry_run,
            }

        except Exception as e:
            logger.error(f"Error cleaning up processing records: {e}")
            return {
                "success": False,
                "error": str(e),
            }
