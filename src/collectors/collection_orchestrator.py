"""
Content Collection Orchestration Module

Coordinates all content collection operations from multiple sources.
Orchestrates newsletter scraping, YouTube extraction, and content filtering.
Manages source health and provides collection summary statistics.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

from src.database import DatabaseStorage
from src.config.config_manager import Config
from src.utils.logging_setup import get_logger

from .newsletter_scraper import NewsletterScraper
from .youtube_extractor import YouTubeExtractor
from .content_filter import ContentFilter
from .source_health import SourceHealth

logger = get_logger(__name__)


class CollectionOrchestratorError(Exception):
    """Base exception for orchestration errors."""

    pass


class CollectionOrchestrator:
    """
    Orchestrates all content collection operations.

    Features:
    - Load sources from configuration
    - Coordinate newsletter and YouTube collection
    - Apply time window filtering
    - Track source health
    - Provide comprehensive collection summary
    - Detailed operation logging
    """

    def __init__(
        self,
        storage: DatabaseStorage,
        config: Optional[Config] = None,
        failure_threshold: int = 5,
        recovery_hours: int = 24,
        window_days: int = 7,
    ):
        """
        Initialize collection orchestrator.

        Args:
            storage: DatabaseStorage instance
            config: Config instance (loads from default if None)
            failure_threshold: Source failure threshold (default: 5)
            recovery_hours: Source recovery period (default: 24 hours)
            window_days: Content time window (default: 7 days)
        """
        self.storage = storage
        self.config = config or Config()
        self.logger = get_logger(__name__)

        # Initialize collection components
        self.scraper = NewsletterScraper(storage=storage)
        self.extractor = YouTubeExtractor(storage=storage)
        self.filter = ContentFilter(
            storage=storage,
            window_days=window_days,
            min_confidence=0.0,
        )
        self.health = SourceHealth(
            storage=storage,
            failure_threshold=failure_threshold,
            recovery_hours=recovery_hours,
        )

    def collect_all(self) -> Dict[str, Any]:
        """
        Execute complete content collection workflow.

        Returns:
            {
                'success': bool,
                'total_collected': int,
                'total_failed': int,
                'by_source_type': {'newsletter': int, 'youtube': int},
                'duration_seconds': float,
                'sources_checked': int,
                'sources_collectable': int,
                'sources_skipped': int,
                'errors': List[str]
            }
        """
        start_time = time.time()
        self.logger.info("Starting content collection workflow")

        collected = 0
        failed = 0
        errors = []
        by_source_type = {"newsletter": 0, "youtube": 0}

        try:
            # Step 1: Check source health
            self.logger.info("Step 1: Checking source health")
            health_check = self.health.check_all_sources()
            sources_checked = health_check["total"]
            sources_collectable = health_check["collectable"]
            sources_skipped = health_check["total"] - sources_collectable

            self.logger.info(
                f"Source health: {sources_checked} total, "
                f"{sources_collectable} collectable, {sources_skipped} skipped"
            )

            # Step 2: Get collectable sources
            self.logger.info("Step 2: Getting collectable sources")
            collectable = self.health.get_collectable_sources()
            collectable_sources = collectable["sources"]

            if not collectable_sources:
                self.logger.warning("No collectable sources available")
                return {
                    "success": True,
                    "total_collected": 0,
                    "total_failed": 0,
                    "by_source_type": by_source_type,
                    "duration_seconds": time.time() - start_time,
                    "sources_checked": sources_checked,
                    "sources_collectable": sources_collectable,
                    "sources_skipped": sources_skipped,
                    "errors": errors,
                }

            # Step 3: Collect from newsletters
            self.logger.info("Step 3: Collecting from newsletter sources")
            newsletter_result = self._collect_newsletters(collectable_sources)
            collected += newsletter_result["collected"]
            failed += newsletter_result["failed"]
            by_source_type["newsletter"] = newsletter_result["collected"]
            errors.extend(newsletter_result["errors"])

            # Step 4: Collect from YouTube
            self.logger.info("Step 4: Collecting from YouTube sources")
            youtube_result = self._collect_youtube(collectable_sources)
            collected += youtube_result["collected"]
            failed += youtube_result["failed"]
            by_source_type["youtube"] = youtube_result["collected"]
            errors.extend(youtube_result["errors"])

            # Step 5: Apply time window filter
            self.logger.info("Step 5: Applying time window filtering")
            filter_result = self.filter.filter_recent_content()
            filtered_content = filter_result["included"]

            self.logger.info(
                f"Filtering complete: {filtered_content} items within "
                f"{self.filter.window_days}-day window"
            )

            # Step 6: Log summary
            duration = time.time() - start_time
            self.logger.info(
                f"Collection workflow complete: {collected} collected, "
                f"{failed} failed, {filtered_content} filtered, "
                f"{duration:.1f}s elapsed"
            )

            return {
                "success": True,
                "total_collected": collected,
                "total_failed": failed,
                "by_source_type": by_source_type,
                "duration_seconds": duration,
                "sources_checked": sources_checked,
                "sources_collectable": sources_collectable,
                "sources_skipped": sources_skipped,
                "filtered_content": filtered_content,
                "errors": errors,
            }

        except Exception as e:
            self.logger.error(
                f"Error during collection workflow: {e}", exc_info=True
            )
            duration = time.time() - start_time
            errors.append(str(e))

            return {
                "success": False,
                "total_collected": collected,
                "total_failed": failed,
                "by_source_type": by_source_type,
                "duration_seconds": duration,
                "sources_checked": 0,
                "sources_collectable": 0,
                "sources_skipped": 0,
                "errors": errors,
            }

    def _collect_newsletters(
        self, collectable_sources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Collect content from newsletter sources.

        Args:
            collectable_sources: List of collectable sources from database

        Returns:
            {
                'collected': int,
                'failed': int,
                'errors': List[str]
            }
        """
        collected = 0
        failed = 0
        errors = []

        # Filter for newsletter sources only
        newsletter_sources = [
            s for s in collectable_sources
            if s.get("source_type") == "newsletter"
        ]

        self.logger.debug(
            f"Found {len(newsletter_sources)} collectable newsletter sources"
        )

        for source in newsletter_sources:
            try:
                source_id = source.get("source_id")
                source_url = source.get("source_id")  # Using source_id as URL placeholder

                # Create newsletter config from source
                newsletter_config = {
                    "name": source_id,
                    "url": source_url,
                }

                # Scrape newsletter
                self.logger.debug(f"Scraping newsletter source: {source_id}")
                result = self.scraper.scrape_newsletter(newsletter_config)

                if result.get("success"):
                    collected += 1
                    self.health.mark_success(source_id)
                    self.logger.info(
                        f"Successfully collected from newsletter: {source_id}"
                    )
                else:
                    failed += 1
                    error = result.get("error", "Unknown error")
                    self.health.mark_failure(source_id, error)
                    errors.append(f"Newsletter {source_id}: {error}")
                    self.logger.warning(
                        f"Failed to collect from newsletter {source_id}: {error}"
                    )

            except Exception as e:
                failed += 1
                source_id = source.get("source_id", "unknown")
                self.health.mark_failure(source_id, str(e))
                errors.append(f"Newsletter {source_id}: {str(e)}")
                self.logger.error(
                    f"Error collecting from newsletter {source_id}: {e}",
                    exc_info=True,
                )

        return {
            "collected": collected,
            "failed": failed,
            "errors": errors,
        }

    def _collect_youtube(
        self, collectable_sources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Collect content from YouTube sources.

        Args:
            collectable_sources: List of collectable sources from database

        Returns:
            {
                'collected': int,
                'failed': int,
                'errors': List[str]
            }
        """
        collected = 0
        failed = 0
        errors = []

        # Filter for YouTube sources only
        youtube_sources = [
            s for s in collectable_sources
            if s.get("source_type") == "youtube"
        ]

        self.logger.debug(
            f"Found {len(youtube_sources)} collectable YouTube sources"
        )

        for source in youtube_sources:
            try:
                source_id = source.get("source_id")
                video_url = source.get("source_id")  # Using source_id as URL placeholder

                # Extract from YouTube
                self.logger.debug(f"Extracting from YouTube source: {source_id}")
                result = self.extractor.extract_youtube_video_to_db(video_url)

                if result.get("success"):
                    collected += 1
                    self.health.mark_success(source_id)
                    self.logger.info(
                        f"Successfully extracted from YouTube: {source_id}"
                    )
                else:
                    failed += 1
                    error = result.get("error", "Unknown error")
                    self.health.mark_failure(source_id, error)
                    errors.append(f"YouTube {source_id}: {error}")
                    self.logger.warning(
                        f"Failed to extract from YouTube {source_id}: {error}"
                    )

            except Exception as e:
                failed += 1
                source_id = source.get("source_id", "unknown")
                self.health.mark_failure(source_id, str(e))
                errors.append(f"YouTube {source_id}: {str(e)}")
                self.logger.error(
                    f"Error extracting from YouTube {source_id}: {e}",
                    exc_info=True,
                )

        return {
            "collected": collected,
            "failed": failed,
            "errors": errors,
        }

    def get_collection_status(self) -> Dict[str, Any]:
        """
        Get current collection status across all sources.

        Returns:
            {
                'healthy_sources': int,
                'unhealthy_sources': int,
                'in_recovery_sources': int,
                'collectable_sources': int,
                'total_sources': int,
                'by_source_type': {source_type: count}
            }
        """
        try:
            health = self.health.check_all_sources()

            # Count by source type
            by_type = {}
            for source_detail in health.get("sources", []):
                source_type = source_detail.get("source_type", "unknown")
                by_type[source_type] = by_type.get(source_type, 0) + 1

            return {
                "healthy_sources": health.get("healthy", 0),
                "unhealthy_sources": health.get("unhealthy", 0),
                "in_recovery_sources": health.get("in_recovery", 0),
                "collectable_sources": health.get("collectable", 0),
                "total_sources": health.get("total", 0),
                "by_source_type": by_type,
            }

        except Exception as e:
            self.logger.error(f"Error getting collection status: {e}", exc_info=True)
            return {
                "healthy_sources": 0,
                "unhealthy_sources": 0,
                "in_recovery_sources": 0,
                "collectable_sources": 0,
                "total_sources": 0,
                "by_source_type": {},
                "error": str(e),
            }

    def reset_all_source_health(self) -> Dict[str, int]:
        """
        Reset all source failure counters.

        Used for bulk recovery or maintenance.

        Returns:
            {
                'total': int,
                'reset': int
            }
        """
        try:
            result = self.health.reset_all_failures()
            self.logger.info(
                f"Reset failure counters for {result.get('reset')} sources"
            )
            return result

        except Exception as e:
            self.logger.error(f"Error resetting source health: {e}", exc_info=True)
            return {
                "total": 0,
                "reset": 0,
                "error": str(e),
            }

    def update_collection_window(self, window_days: int) -> None:
        """
        Update the content collection time window.

        Args:
            window_days: New window duration in days

        Raises:
            CollectionOrchestratorError: If window_days is invalid
        """
        try:
            self.filter.update_window_days(window_days)
            self.logger.info(f"Updated collection window to {window_days} days")

        except Exception as e:
            self.logger.error(f"Error updating collection window: {e}")
            raise CollectionOrchestratorError(str(e))

    def update_source_failure_threshold(self, threshold: int) -> None:
        """
        Update the source failure threshold.

        Args:
            threshold: New failure threshold

        Raises:
            CollectionOrchestratorError: If threshold is invalid
        """
        try:
            self.health.update_failure_threshold(threshold)
            self.logger.info(f"Updated source failure threshold to {threshold}")

        except Exception as e:
            self.logger.error(f"Error updating failure threshold: {e}")
            raise CollectionOrchestratorError(str(e))

    def update_source_recovery_period(self, hours: int) -> None:
        """
        Update the source recovery period duration.

        Args:
            hours: New recovery duration in hours

        Raises:
            CollectionOrchestratorError: If hours is invalid
        """
        try:
            self.health.update_recovery_hours(hours)
            self.logger.info(f"Updated source recovery period to {hours} hours")

        except Exception as e:
            self.logger.error(f"Error updating recovery period: {e}")
            raise CollectionOrchestratorError(str(e))
