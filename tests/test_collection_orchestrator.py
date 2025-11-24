"""
Tests for content collection orchestration module.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import logging
import time

from src.collectors.collection_orchestrator import (
    CollectionOrchestrator,
    CollectionOrchestratorError,
)


@pytest.fixture
def mock_storage():
    """Mock database storage."""
    storage = Mock()
    storage.get_source_status = Mock(return_value={
        "source_id": "test_source",
        "source_type": "newsletter",
        "consecutive_failures": 0,
    })
    storage.update_source_status = Mock()
    storage.get_all_sources = Mock(return_value=[])
    storage.store_raw_content = Mock(return_value=1)
    return storage


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = Mock()
    config.newsletter_sources = []
    config.youtube_channels = []
    return config


@pytest.fixture
def orchestrator(mock_storage, mock_config):
    """Create orchestrator with mocked dependencies."""
    with patch("src.collectors.collection_orchestrator.NewsletterScraper"), \
         patch("src.collectors.collection_orchestrator.YouTubeExtractor"), \
         patch("src.collectors.collection_orchestrator.ContentFilter"), \
         patch("src.collectors.collection_orchestrator.SourceHealth"):
        return CollectionOrchestrator(
            storage=mock_storage,
            config=mock_config,
            failure_threshold=5,
            recovery_hours=24,
            window_days=7,
        )


class TestCollectionOrchestratorInitialization:
    """Test orchestrator initialization."""

    def test_initialization_with_storage(self, mock_storage):
        """Test initialization with storage."""
        with patch("src.collectors.collection_orchestrator.Config"), \
             patch("src.collectors.collection_orchestrator.NewsletterScraper"), \
             patch("src.collectors.collection_orchestrator.YouTubeExtractor"), \
             patch("src.collectors.collection_orchestrator.ContentFilter"), \
             patch("src.collectors.collection_orchestrator.SourceHealth"):
            orchestrator = CollectionOrchestrator(storage=mock_storage)

            assert orchestrator.storage == mock_storage
            assert orchestrator.scraper is not None
            assert orchestrator.extractor is not None
            assert orchestrator.filter is not None
            assert orchestrator.health is not None

    def test_initialization_with_config(self, mock_storage, mock_config):
        """Test initialization with config."""
        with patch("src.collectors.collection_orchestrator.NewsletterScraper"), \
             patch("src.collectors.collection_orchestrator.YouTubeExtractor"), \
             patch("src.collectors.collection_orchestrator.ContentFilter"), \
             patch("src.collectors.collection_orchestrator.SourceHealth"):
            orchestrator = CollectionOrchestrator(
                storage=mock_storage,
                config=mock_config,
            )

            assert orchestrator.config == mock_config

    def test_initialization_default_config(self, mock_storage):
        """Test that config is loaded if not provided."""
        with patch("src.collectors.collection_orchestrator.Config") as mock_cfg, \
             patch("src.collectors.collection_orchestrator.NewsletterScraper"), \
             patch("src.collectors.collection_orchestrator.YouTubeExtractor"), \
             patch("src.collectors.collection_orchestrator.ContentFilter"), \
             patch("src.collectors.collection_orchestrator.SourceHealth"):
            orchestrator = CollectionOrchestrator(storage=mock_storage)

            assert mock_cfg.called


class TestCollectionOrchestratorCollectAll:
    """Test main collection workflow."""

    def test_collect_all_no_sources(self, orchestrator, mock_storage):
        """Test collection when no sources available."""
        mock_storage.get_all_sources.return_value = []

        orchestrator.health.check_all_sources = Mock(return_value={
            "total": 0,
            "healthy": 0,
            "unhealthy": 0,
            "in_recovery": 0,
            "collectable": 0,
            "sources": [],
        })
        orchestrator.health.get_collectable_sources = Mock(return_value={
            "total": 0,
            "collectable": 0,
            "skipped": 0,
            "sources": [],
        })

        result = orchestrator.collect_all()

        assert result["success"] is True
        assert result["total_collected"] == 0
        assert result["total_failed"] == 0
        assert result["sources_checked"] == 0

    def test_collect_all_structure(self, orchestrator, mock_storage):
        """Test that collect_all returns expected structure."""
        orchestrator.health.check_all_sources = Mock(return_value={
            "total": 0,
            "healthy": 0,
            "collectable": 0,
            "sources": [],
        })
        orchestrator.health.get_collectable_sources = Mock(return_value={
            "sources": [],
        })

        result = orchestrator.collect_all()

        assert "success" in result
        assert "total_collected" in result
        assert "total_failed" in result
        assert "by_source_type" in result
        assert "duration_seconds" in result
        assert "sources_checked" in result
        assert "sources_collectable" in result
        assert "sources_skipped" in result
        assert "errors" in result

    def test_collect_all_error_handling(self, orchestrator, mock_storage):
        """Test error handling during collection."""
        orchestrator.health.check_all_sources = Mock(
            side_effect=Exception("Database error")
        )

        result = orchestrator.collect_all()

        assert result["success"] is False
        assert result["total_collected"] == 0
        assert len(result["errors"]) > 0


class TestCollectionOrchestratorCollectNewsletters:
    """Test newsletter collection."""

    def test_collect_newsletters_empty(self, orchestrator):
        """Test newsletter collection with no sources."""
        result = orchestrator._collect_newsletters([])

        assert result["collected"] == 0
        assert result["failed"] == 0
        assert result["errors"] == []

    def test_collect_newsletters_filters_type(self, orchestrator):
        """Test that only newsletter sources are collected."""
        sources = [
            {"source_id": "yt_1", "source_type": "youtube"},
            {"source_id": "nl_1", "source_type": "newsletter"},
        ]

        orchestrator.scraper.scrape_newsletter = Mock(
            return_value={"success": True}
        )

        result = orchestrator._collect_newsletters(sources)

        # Should only call scraper once (for newsletter)
        assert orchestrator.scraper.scrape_newsletter.call_count == 1

    def test_collect_newsletters_success(self, orchestrator):
        """Test successful newsletter collection."""
        sources = [
            {"source_id": "nl_1", "source_type": "newsletter"},
        ]

        orchestrator.scraper.scrape_newsletter = Mock(
            return_value={"success": True}
        )
        orchestrator.health.mark_success = Mock()

        result = orchestrator._collect_newsletters(sources)

        assert result["collected"] == 1
        assert result["failed"] == 0
        assert orchestrator.health.mark_success.called

    def test_collect_newsletters_failure(self, orchestrator):
        """Test failed newsletter collection."""
        sources = [
            {"source_id": "nl_1", "source_type": "newsletter"},
        ]

        orchestrator.scraper.scrape_newsletter = Mock(
            return_value={"success": False, "error": "Connection failed"}
        )
        orchestrator.health.mark_failure = Mock()

        result = orchestrator._collect_newsletters(sources)

        assert result["collected"] == 0
        assert result["failed"] == 1
        assert orchestrator.health.mark_failure.called


class TestCollectionOrchestratorCollectYouTube:
    """Test YouTube collection."""

    def test_collect_youtube_empty(self, orchestrator):
        """Test YouTube collection with no sources."""
        result = orchestrator._collect_youtube([])

        assert result["collected"] == 0
        assert result["failed"] == 0
        assert result["errors"] == []

    def test_collect_youtube_filters_type(self, orchestrator):
        """Test that only YouTube sources are collected."""
        sources = [
            {"source_id": "nl_1", "source_type": "newsletter"},
            {"source_id": "yt_1", "source_type": "youtube"},
        ]

        orchestrator.extractor.extract_youtube_video_to_db = Mock(
            return_value={"success": True}
        )

        result = orchestrator._collect_youtube(sources)

        # Should only call extractor once (for youtube)
        assert orchestrator.extractor.extract_youtube_video_to_db.call_count == 1

    def test_collect_youtube_success(self, orchestrator):
        """Test successful YouTube collection."""
        sources = [
            {"source_id": "yt_1", "source_type": "youtube"},
        ]

        orchestrator.extractor.extract_youtube_video_to_db = Mock(
            return_value={"success": True}
        )
        orchestrator.health.mark_success = Mock()

        result = orchestrator._collect_youtube(sources)

        assert result["collected"] == 1
        assert result["failed"] == 0
        assert orchestrator.health.mark_success.called

    def test_collect_youtube_failure(self, orchestrator):
        """Test failed YouTube collection."""
        sources = [
            {"source_id": "yt_1", "source_type": "youtube"},
        ]

        orchestrator.extractor.extract_youtube_video_to_db = Mock(
            return_value={"success": False, "error": "Video not found"}
        )
        orchestrator.health.mark_failure = Mock()

        result = orchestrator._collect_youtube(sources)

        assert result["collected"] == 0
        assert result["failed"] == 1
        assert orchestrator.health.mark_failure.called


class TestCollectionOrchestratorStatus:
    """Test status and monitoring methods."""

    def test_get_collection_status_empty(self, orchestrator):
        """Test status with no sources."""
        orchestrator.health.check_all_sources = Mock(return_value={
            "healthy": 0,
            "unhealthy": 0,
            "in_recovery": 0,
            "collectable": 0,
            "total": 0,
            "sources": [],
        })

        status = orchestrator.get_collection_status()

        assert status["total_sources"] == 0
        assert status["healthy_sources"] == 0

    def test_get_collection_status_mixed(self, orchestrator):
        """Test status with multiple source types."""
        orchestrator.health.check_all_sources = Mock(return_value={
            "healthy": 3,
            "unhealthy": 1,
            "in_recovery": 1,
            "collectable": 3,
            "total": 4,
            "sources": [
                {"source_type": "newsletter", "is_healthy": True},
                {"source_type": "newsletter", "is_healthy": True},
                {"source_type": "youtube", "is_healthy": True},
                {"source_type": "youtube", "is_healthy": False},
            ],
        })

        status = orchestrator.get_collection_status()

        assert status["total_sources"] == 4
        assert status["healthy_sources"] == 3
        assert status["collectable_sources"] == 3

    def test_get_collection_status_error(self, orchestrator):
        """Test status error handling."""
        orchestrator.health.check_all_sources = Mock(
            side_effect=Exception("Database error")
        )

        status = orchestrator.get_collection_status()

        assert "error" in status
        assert status["total_sources"] == 0


class TestCollectionOrchestratorReset:
    """Test reset functionality."""

    def test_reset_all_source_health(self, orchestrator):
        """Test resetting all source health."""
        orchestrator.health.reset_all_failures = Mock(return_value={
            "total": 5,
            "reset": 3,
        })

        result = orchestrator.reset_all_source_health()

        assert result["reset"] == 3
        assert orchestrator.health.reset_all_failures.called

    def test_reset_all_source_health_error(self, orchestrator):
        """Test reset error handling."""
        orchestrator.health.reset_all_failures = Mock(
            side_effect=Exception("Database error")
        )

        result = orchestrator.reset_all_source_health()

        assert "error" in result


class TestCollectionOrchestratorConfiguration:
    """Test configuration update methods."""

    def test_update_collection_window(self, orchestrator):
        """Test updating collection window."""
        orchestrator.filter.update_window_days = Mock()

        orchestrator.update_collection_window(14)

        assert orchestrator.filter.update_window_days.called

    def test_update_collection_window_error(self, orchestrator):
        """Test update window error handling."""
        orchestrator.filter.update_window_days = Mock(
            side_effect=Exception("Invalid window")
        )

        with pytest.raises(CollectionOrchestratorError):
            orchestrator.update_collection_window(0)

    def test_update_source_failure_threshold(self, orchestrator):
        """Test updating failure threshold."""
        orchestrator.health.update_failure_threshold = Mock()

        orchestrator.update_source_failure_threshold(10)

        assert orchestrator.health.update_failure_threshold.called

    def test_update_source_failure_threshold_error(self, orchestrator):
        """Test update threshold error handling."""
        orchestrator.health.update_failure_threshold = Mock(
            side_effect=Exception("Invalid threshold")
        )

        with pytest.raises(CollectionOrchestratorError):
            orchestrator.update_source_failure_threshold(0)

    def test_update_source_recovery_period(self, orchestrator):
        """Test updating recovery period."""
        orchestrator.health.update_recovery_hours = Mock()

        orchestrator.update_source_recovery_period(48)

        assert orchestrator.health.update_recovery_hours.called

    def test_update_source_recovery_period_error(self, orchestrator):
        """Test update recovery error handling."""
        orchestrator.health.update_recovery_hours = Mock(
            side_effect=Exception("Invalid hours")
        )

        with pytest.raises(CollectionOrchestratorError):
            orchestrator.update_source_recovery_period(0)


class TestCollectionOrchestratorIntegration:
    """Integration tests."""

    def test_collect_all_timing(self, orchestrator):
        """Test that collection tracks timing."""
        orchestrator.health.check_all_sources = Mock(return_value={
            "total": 0,
            "collectable": 0,
            "sources": [],
        })
        orchestrator.health.get_collectable_sources = Mock(return_value={
            "sources": [],
        })

        result = orchestrator.collect_all()

        assert result["duration_seconds"] >= 0

    def test_collect_all_by_source_type(self, orchestrator):
        """Test source type tracking."""
        orchestrator.health.check_all_sources = Mock(return_value={
            "total": 0,
            "collectable": 0,
            "sources": [],
        })
        orchestrator.health.get_collectable_sources = Mock(return_value={
            "sources": [],
        })

        result = orchestrator.collect_all()

        assert "by_source_type" in result
        assert "newsletter" in result["by_source_type"]
        assert "youtube" in result["by_source_type"]

    def test_collect_all_error_accumulation(self, orchestrator):
        """Test that errors are accumulated."""
        orchestrator.health.check_all_sources = Mock(return_value={
            "total": 2,
            "collectable": 2,
            "sources": [
                {"source_id": "nl_1", "source_type": "newsletter"},
                {"source_id": "yt_1", "source_type": "youtube"},
            ],
        })
        orchestrator.health.get_collectable_sources = Mock(return_value={
            "sources": [
                {"source_id": "nl_1", "source_type": "newsletter"},
                {"source_id": "yt_1", "source_type": "youtube"},
            ],
        })
        orchestrator.filter.filter_recent_content = Mock(return_value={
            "included": 0,
        })

        # Make both fail
        orchestrator.scraper.scrape_newsletter = Mock(
            return_value={"success": False, "error": "Error 1"}
        )
        orchestrator.extractor.extract_youtube_video_to_db = Mock(
            return_value={"success": False, "error": "Error 2"}
        )
        orchestrator.health.mark_failure = Mock()

        result = orchestrator.collect_all()

        assert result["total_failed"] == 2
        assert len(result["errors"]) == 2


class TestCollectionOrchestratorLogging:
    """Test logging integration."""

    def test_collect_all_logs_workflow(self, orchestrator, caplog):
        """Test that collection workflow is logged."""
        orchestrator.health.check_all_sources = Mock(return_value={
            "total": 0,
            "collectable": 0,
            "sources": [],
        })
        orchestrator.health.get_collectable_sources = Mock(return_value={
            "sources": [],
        })

        with caplog.at_level(logging.INFO):
            orchestrator.collect_all()

        assert any("Starting content collection workflow" in record.message
                   for record in caplog.records)

    def test_collection_status_logs_summary(self, orchestrator, caplog):
        """Test that status checks are logged."""
        orchestrator.health.check_all_sources = Mock(return_value={
            "total": 5,
            "collectable": 3,
            "sources": [],
        })

        with caplog.at_level(logging.INFO):
            orchestrator.collect_all()

        assert any("Source health:" in record.message
                   for record in caplog.records)

    def test_configuration_updates_logged(self, orchestrator, caplog):
        """Test that configuration changes are logged."""
        orchestrator.filter.update_window_days = Mock()

        with caplog.at_level(logging.INFO):
            orchestrator.update_collection_window(14)

        assert any("Updated collection window" in record.message
                   for record in caplog.records)
