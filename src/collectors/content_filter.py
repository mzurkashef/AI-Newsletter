"""
Content Filtering Module

Filters collected content by time window and other criteria.
Ensures only content within the specified time period is processed.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from src.database import DatabaseStorage
from src.database.models import RawContent
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)


class ContentFilterError(Exception):
    """Base exception for content filter errors."""

    pass


class ContentFilter:
    """
    Filters content by time window and other criteria.

    Features:
    - Filter content by publication date (7-day window by default)
    - Filter by source type (newsletter, youtube, etc.)
    - Filter by confidence score (optional)
    - Batch filtering with statistics
    - Comprehensive logging
    """

    def __init__(
        self,
        storage: DatabaseStorage,
        window_days: int = 7,
        min_confidence: float = 0.0,
    ):
        """
        Initialize content filter.

        Args:
            storage: DatabaseStorage instance for reading content
            window_days: Number of days back to include (default: 7)
            min_confidence: Minimum confidence score to include (default: 0.0)
        """
        self.storage = storage
        self.window_days = window_days
        self.min_confidence = min_confidence
        self.logger = get_logger(__name__)

    def is_within_window(self, published_at: datetime, cutoff_date: Optional[datetime] = None) -> bool:
        """
        Check if a date is within the time window.

        Args:
            published_at: Publication date to check
            cutoff_date: Cutoff date (default: now - window_days)

        Returns:
            True if date is within window, False otherwise
        """
        if not isinstance(published_at, datetime):
            self.logger.warning(f"Invalid published_at type: {type(published_at)}")
            return False

        if cutoff_date is None:
            cutoff_date = datetime.utcnow() - timedelta(days=self.window_days)

        return published_at >= cutoff_date

    def should_include_content(
        self,
        published_at: datetime,
        confidence: float = 1.0,
        source_type: Optional[str] = None,
    ) -> bool:
        """
        Determine if content should be included based on all criteria.

        Args:
            published_at: Publication date
            confidence: Confidence score (0.0-1.0)
            source_type: Source type (newsletter, youtube, etc.)

        Returns:
            True if content meets all criteria, False otherwise
        """
        # Check time window
        if not self.is_within_window(published_at):
            return False

        # Check confidence score
        if confidence < self.min_confidence:
            return False

        return True

    def filter_content_list(
        self, content_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Filter a list of content items by all criteria.

        Args:
            content_list: List of raw content dictionaries

        Returns:
            {
                'total': int,
                'included': int,
                'excluded': int,
                'filtered': List[Dict],
                'exclusion_reasons': {
                    'outside_window': int,
                    'low_confidence': int,
                    'invalid_date': int,
                }
            }
        """
        filtered = []
        excluded_reasons = {
            "outside_window": 0,
            "low_confidence": 0,
            "invalid_date": 0,
        }

        for content in content_list:
            try:
                # Get published date
                published_str = content.get("published_at")
                if not published_str:
                    excluded_reasons["invalid_date"] += 1
                    continue

                # Parse date
                try:
                    if isinstance(published_str, datetime):
                        published_at = published_str
                    elif isinstance(published_str, str):
                        # Try ISO format parsing
                        try:
                            published_at = datetime.fromisoformat(published_str)
                        except ValueError:
                            # Try other common formats
                            for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"]:
                                try:
                                    published_at = datetime.strptime(published_str, fmt)
                                    break
                                except ValueError:
                                    continue
                            else:
                                excluded_reasons["invalid_date"] += 1
                                continue
                    else:
                        excluded_reasons["invalid_date"] += 1
                        continue
                except Exception as e:
                    self.logger.debug(f"Error parsing date {published_str}: {e}")
                    excluded_reasons["invalid_date"] += 1
                    continue

                # Get confidence
                confidence = content.get("confidence", 1.0)
                if isinstance(confidence, str):
                    try:
                        confidence = float(confidence)
                    except ValueError:
                        confidence = 1.0

                # Check criteria
                if not self.is_within_window(published_at):
                    excluded_reasons["outside_window"] += 1
                    continue

                if confidence < self.min_confidence:
                    excluded_reasons["low_confidence"] += 1
                    continue

                # Include content
                filtered.append(content)

            except Exception as e:
                self.logger.warning(f"Error filtering content: {e}")
                excluded_reasons["invalid_date"] += 1
                continue

        self.logger.info(
            f"Filtered {len(content_list)} items: {len(filtered)} included, "
            f"{len(content_list) - len(filtered)} excluded"
        )

        return {
            "total": len(content_list),
            "included": len(filtered),
            "excluded": len(content_list) - len(filtered),
            "filtered": filtered,
            "exclusion_reasons": excluded_reasons,
        }

    def filter_recent_content(
        self, source_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Filter all recent content from database.

        Args:
            source_type: Optional source type to filter (newsletter, youtube)

        Returns:
            {
                'total': int,
                'included': int,
                'excluded': int,
                'content_ids': List[int],
                'exclusion_reasons': Dict
            }
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.window_days)
        self.logger.info(
            f"Filtering content from last {self.window_days} days (since {cutoff_date})"
        )

        try:
            # Get unprocessed content
            unprocessed = self.storage.get_unprocessed_content()
            self.logger.debug(f"Found {len(unprocessed)} unprocessed content items")

            # Filter by criteria
            filtered_items = []
            excluded_reasons = {
                "outside_window": 0,
                "low_confidence": 0,
                "invalid_date": 0,
                "wrong_source_type": 0,
            }

            for content in unprocessed:
                try:
                    # Filter by source type if specified
                    if source_type and content.get("source_type") != source_type:
                        excluded_reasons["wrong_source_type"] += 1
                        continue

                    # Get published date
                    published_str = content.get("published_at")
                    if not published_str:
                        excluded_reasons["invalid_date"] += 1
                        continue

                    # Parse date
                    try:
                        if isinstance(published_str, datetime):
                            published_at = published_str
                        elif isinstance(published_str, str):
                            published_at = datetime.fromisoformat(published_str)
                        else:
                            excluded_reasons["invalid_date"] += 1
                            continue
                    except Exception:
                        excluded_reasons["invalid_date"] += 1
                        continue

                    # Check time window
                    if not self.is_within_window(published_at, cutoff_date):
                        excluded_reasons["outside_window"] += 1
                        continue

                    # Check confidence
                    confidence = content.get("confidence", 1.0)
                    if confidence < self.min_confidence:
                        excluded_reasons["low_confidence"] += 1
                        continue

                    # Include content
                    filtered_items.append(content)

                except Exception as e:
                    self.logger.warning(f"Error filtering content item: {e}")
                    excluded_reasons["invalid_date"] += 1
                    continue

            content_ids = [c.get("id") for c in filtered_items if c.get("id")]

            self.logger.info(
                f"Database filter: {len(filtered_items)} included from "
                f"{len(unprocessed)} total (window: {self.window_days} days)"
            )

            return {
                "total": len(unprocessed),
                "included": len(filtered_items),
                "excluded": len(unprocessed) - len(filtered_items),
                "content_ids": content_ids,
                "exclusion_reasons": excluded_reasons,
            }

        except Exception as e:
            self.logger.error(f"Error filtering recent content: {e}", exc_info=True)
            return {
                "total": 0,
                "included": 0,
                "excluded": 0,
                "content_ids": [],
                "exclusion_reasons": {
                    "error": str(e),
                },
            }

    def get_window_dates(self) -> Dict[str, datetime]:
        """
        Get the cutoff and current dates for the time window.

        Returns:
            {
                'cutoff_date': datetime (window_days ago),
                'current_date': datetime (now)
            }
        """
        current = datetime.utcnow()
        cutoff = current - timedelta(days=self.window_days)

        return {
            "cutoff_date": cutoff,
            "current_date": current,
            "window_days": self.window_days,
        }

    def update_window_days(self, window_days: int) -> None:
        """
        Update the time window duration.

        Args:
            window_days: New window duration in days
        """
        if window_days < 1:
            raise ContentFilterError("Window days must be at least 1")

        old_window = self.window_days
        self.window_days = window_days
        self.logger.info(f"Updated time window from {old_window} to {window_days} days")

    def update_min_confidence(self, min_confidence: float) -> None:
        """
        Update the minimum confidence threshold.

        Args:
            min_confidence: New minimum confidence (0.0-1.0)
        """
        if not (0.0 <= min_confidence <= 1.0):
            raise ContentFilterError("Confidence must be between 0.0 and 1.0")

        old_threshold = self.min_confidence
        self.min_confidence = min_confidence
        self.logger.info(
            f"Updated minimum confidence from {old_threshold} to {min_confidence}"
        )
