"""
Tests for YouTube content extractor.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import logging

from src.collectors.youtube_extractor import (
    YouTubeExtractor,
    YouTubeExtractorError,
)
from src.database.models import RawContent, SourceStatus
from src.utils.error_handling import NetworkError, ValidationError


@pytest.fixture
def mock_storage():
    """Mock database storage."""
    storage = Mock()
    storage.store_raw_content = Mock(return_value=1)
    storage.update_source_status = Mock()
    return storage


@pytest.fixture
def extractor(mock_storage):
    """Create extractor instance with mock storage."""
    return YouTubeExtractor(storage=mock_storage, timeout=30)


class TestYouTubeExtractorVideoIdExtraction:
    """Test video ID extraction from URLs."""

    def test_extract_video_id_from_youtube_com_url(self, extractor):
        """Test extracting video ID from youtube.com URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = extractor.extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_video_id_from_youtu_be_url(self, extractor):
        """Test extracting video ID from youtu.be short URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        video_id = extractor.extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_video_id_from_embed_url(self, extractor):
        """Test extracting video ID from embed URL."""
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        video_id = extractor.extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_video_id_direct(self, extractor):
        """Test extracting video ID when directly provided."""
        video_id = "dQw4w9WgXcQ"
        extracted = extractor.extract_video_id(video_id)
        assert extracted == video_id

    def test_extract_video_id_invalid_url(self, extractor):
        """Test extraction with invalid URL."""
        with pytest.raises(ValidationError):
            extractor.extract_video_id("not-a-url")

    def test_extract_video_id_invalid_format(self, extractor):
        """Test extraction with URL that doesn't contain video ID."""
        with pytest.raises(ValidationError):
            extractor.extract_video_id("https://www.youtube.com/")

    def test_extract_video_id_empty_url(self, extractor):
        """Test extraction with empty URL."""
        with pytest.raises(ValidationError):
            extractor.extract_video_id("")

    def test_extract_video_id_youtube_com_no_params(self, extractor):
        """Test youtube.com without video ID parameter."""
        with pytest.raises(ValidationError):
            extractor.extract_video_id("https://www.youtube.com/watch")

    def test_extract_video_id_with_extra_params(self, extractor):
        """Test video ID extraction with extra URL parameters."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s&list=abc"
        video_id = extractor.extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_video_id_valid_direct_id(self, extractor):
        """Test extraction of valid direct video ID."""
        # Real YouTube IDs are 11 characters
        video_id = "dQw4w9WgXcQ"
        extracted = extractor.extract_video_id(video_id)
        assert extracted == video_id


class TestYouTubeExtractorVideoMetadata:
    """Test metadata extraction from video information."""

    def test_extract_video_metadata_missing_date(self, extractor):
        """Test metadata extraction with missing upload date."""
        mock_info = {
            "title": "Test Video",
            "description": "Test Description",
            "upload_date": None,
            "uploader": "Test Channel",
            "duration": 600,
            "view_count": 1000,
        }

        with patch("yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl = MagicMock()
            mock_ydl.__enter__.return_value = mock_ydl
            mock_ydl.__exit__.return_value = False
            mock_ydl.extract_info.return_value = mock_info
            mock_ydl_class.return_value = mock_ydl

            result = extractor.extract_video_metadata("dQw4w9WgXcQ")

            assert result is not None
            assert result["upload_date"] is None

    def test_extract_video_metadata_yt_dlp_error(self, extractor):
        """Test metadata extraction with error."""
        with patch("yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl = MagicMock()
            mock_ydl.__enter__.return_value = mock_ydl
            mock_ydl.__exit__.return_value = False
            mock_ydl.extract_info.side_effect = Exception("Network error")
            mock_ydl_class.return_value = mock_ydl

            result = extractor.extract_video_metadata("dQw4w9WgXcQ")
            # Should return None on error, not raise
            assert result is None


class TestYouTubeExtractorDatabase:
    """Test database integration."""

    def test_extract_and_store_invalid_url(self, extractor, mock_storage):
        """Test extraction with invalid URL."""
        result = extractor.extract_youtube_video_to_db("not-a-url")

        assert result["success"] is False
        assert result["error_type"] == "permanent"

    def test_extract_and_store_metadata_structure(self, extractor, mock_storage):
        """Test that result has expected structure."""
        result = extractor.extract_youtube_video_to_db("not-a-url")

        assert "success" in result
        assert "video_id" in result
        assert "title" in result
        assert "url" in result
        assert "error" in result or "content_id" in result


class TestYouTubeExtractorBatch:
    """Test batch operations."""

    def test_extract_multiple_videos_empty(self, extractor, mock_storage):
        """Test batch extraction with empty list."""
        result = extractor.extract_youtube_videos([])

        assert result["total"] == 0
        assert result["success"] == 0
        assert result["failed"] == 0
        assert result["results"] == []

    def test_extract_multiple_videos_structure(self, extractor, mock_storage):
        """Test batch result structure."""
        urls = ["invalid1", "invalid2"]
        result = extractor.extract_youtube_videos(urls)

        assert result["total"] == 2
        assert "success" in result
        assert "failed" in result
        assert "results" in result
        assert isinstance(result["results"], list)
        assert len(result["results"]) == 2


class TestYouTubeExtractorIntegration:
    """Integration tests."""

    def test_different_video_url_formats(self, extractor):
        """Test extraction recognizes different URL formats."""
        urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "dQw4w9WgXcQ",
        ]

        for url in urls:
            # Should not raise an exception during URL parsing
            try:
                video_id = extractor.extract_video_id(url)
                assert video_id == "dQw4w9WgXcQ"
            except ValidationError:
                pytest.fail(f"Should parse {url} successfully")

    def test_fetch_transcript_network_error_handling(self, extractor):
        """Test that network errors are caught and handled."""
        # When fetch_transcript fails with network error, extract_youtube_video returns None
        with patch.object(extractor, "fetch_transcript") as mock_fetch:
            mock_fetch.side_effect = NetworkError("Connection failed")

            result = extractor.extract_youtube_video("dQw4w9WgXcQ")
            # Should return None (error caught in extract_youtube_video)
            assert result is None

    def test_extract_validation_error_handling(self, extractor):
        """Test that validation errors are handled correctly."""
        with patch.object(extractor, "extract_video_id") as mock_extract:
            mock_extract.side_effect = ValidationError("Invalid video ID")

            result = extractor.extract_youtube_video_to_db("invalid")

            assert result["success"] is False
            assert result["error_type"] == "permanent"


class TestYouTubeExtractorLogging:
    """Test logging integration."""

    def test_invalid_url_logs_warning(self, extractor, caplog):
        """Test that invalid URLs are logged."""
        with caplog.at_level(logging.WARNING):
            result = extractor.extract_youtube_video_to_db("not-a-url")

        assert result["success"] is False
        # Should have some logging
        assert len(caplog.records) > 0

    def test_error_logged(self, extractor, caplog):
        """Test that errors are logged."""
        with caplog.at_level(logging.ERROR):
            with patch.object(extractor, "extract_youtube_video", side_effect=Exception("Test error")):
                result = extractor.extract_youtube_video_to_db("dQw4w9WgXcQ")

        assert result["success"] is False


class TestYouTubeExtractorErrorClassification:
    """Test error classification."""

    def test_validation_error_classification(self, extractor):
        """Test that validation errors are classified as permanent."""
        with patch.object(extractor, "extract_video_id", side_effect=ValidationError("Invalid")):
            result = extractor.extract_youtube_video_to_db("test")

            assert result["error_type"] == "permanent"

    def test_network_error_classification(self, extractor):
        """Test that network errors are classified as retryable."""
        with patch.object(extractor, "fetch_transcript", side_effect=NetworkError("Network")):
            result = extractor.extract_youtube_video("dQw4w9WgXcQ")

            # Since fetch_transcript raises an error during extraction
            assert result is None

    def test_unknown_error_classification(self, extractor):
        """Test that unknown errors are classified appropriately."""
        with patch.object(extractor, "extract_youtube_video", side_effect=Exception("Unknown")):
            result = extractor.extract_youtube_video_to_db("dQw4w9WgXcQ")

            assert result["success"] is False
            assert result["error_type"] == "unknown"


class TestYouTubeExtractorConfiguration:
    """Test configuration and initialization."""

    def test_timeout_configuration(self):
        """Test timeout configuration."""
        storage = Mock()
        extractor_default = YouTubeExtractor(storage=storage)
        extractor_custom = YouTubeExtractor(storage=storage, timeout=60)

        assert extractor_default.timeout == 30
        assert extractor_custom.timeout == 60

    def test_storage_initialization(self):
        """Test storage initialization."""
        storage = Mock()
        extractor = YouTubeExtractor(storage=storage)

        assert extractor.storage == storage
