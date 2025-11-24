"""
YouTube Content Extractor

Extracts transcripts and metadata from YouTube videos.
Supports extracting content from YouTube channels and individual video URLs.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

from src.database.models import RawContent, SourceStatus
from src.database import DatabaseStorage
from src.utils.error_handling import (
    with_retries_and_logging,
    NetworkError,
    ValidationError,
)
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)


class YouTubeExtractorError(Exception):
    """Base exception for YouTube extractor errors."""

    pass


class YouTubeExtractor:
    """
    Extracts transcripts and metadata from YouTube videos.

    Features:
    - Extracts transcripts from individual YouTube videos
    - Retrieves video metadata (title, description, upload date, channel name)
    - Handles unavailable transcripts gracefully
    - Automatic retry on network errors
    - Stores extracted content in database
    """

    def __init__(self, storage: DatabaseStorage, timeout: int = 30):
        """
        Initialize YouTube extractor.

        Args:
            storage: DatabaseStorage instance for persistence
            timeout: Request timeout in seconds (default: 30)
        """
        self.storage = storage
        self.timeout = timeout
        self.logger = get_logger(__name__)
        self.formatter = TextFormatter()

    def extract_video_id(self, url: str) -> Optional[str]:
        """
        Extract video ID from various YouTube URL formats.

        Supports:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        - VIDEO_ID (direct)

        Args:
            url: YouTube URL or video ID

        Returns:
            Video ID string, or None if extraction fails

        Raises:
            ValidationError: If URL is invalid
        """
        if not url:
            raise ValidationError("URL cannot be empty")

        # Try direct video ID (just alphanumeric + hyphen/underscore)
        if len(url) == 11 and url.replace("-", "").replace("_", "").isalnum():
            return url

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValidationError(f"Invalid URL format: {url}") from e

        # Check for youtube.com
        if "youtube.com" in parsed.netloc:
            query = parse_qs(parsed.query)
            if "v" in query:
                video_id = query["v"][0]
                if len(video_id) == 11:
                    return video_id

        # Check for youtu.be
        if "youtu.be" in parsed.netloc:
            video_id = parsed.path.lstrip("/")
            if video_id and len(video_id) == 11:
                return video_id

        # Check for /embed/ URLs
        if "/embed/" in parsed.path:
            video_id = parsed.path.split("/embed/")[1].split("/")[0]
            if video_id and len(video_id) == 11:
                return video_id

        raise ValidationError(f"Could not extract video ID from: {url}")

    @with_retries_and_logging(
        max_attempts=3, backoff_min=1.0, backoff_max=4.0, operation_name="transcript fetch"
    )
    def fetch_transcript(self, video_id: str) -> str:
        """
        Fetch transcript for a YouTube video.

        Automatically retries on network errors with exponential backoff.

        Args:
            video_id: YouTube video ID

        Returns:
            Formatted transcript as plain text

        Raises:
            NetworkError: On network/timeout errors (retried automatically)
            ValidationError: On permanent errors (video not found, no transcript)
        """
        try:
            # Fetch transcript in English
            # Try English first, then any available language
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(
                    video_id, languages=["en"]
                )
            except Exception:
                # Fallback to first available language
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)

            if not transcript_list:
                raise ValidationError(f"No transcript available for video: {video_id}")

            # Format transcript as plain text
            formatted = self.formatter.format_transcript(transcript_list)
            return formatted

        except Exception as e:
            error_msg = str(e)

            # Network-related errors
            if any(
                x in error_msg.lower()
                for x in ["connection", "timeout", "network", "socket"]
            ):
                raise NetworkError(f"Network error fetching transcript: {error_msg}") from e

            # Video not found
            if "videoDetails" in error_msg or "not found" in error_msg.lower():
                raise ValidationError(f"Video not found: {video_id}") from e

            # No transcript available
            if "transcript" in error_msg.lower():
                raise ValidationError(
                    f"No transcript available for video: {video_id}"
                ) from e

            # Other errors - treat as permanent
            raise ValidationError(f"Error fetching transcript: {error_msg}") from e

    def extract_video_metadata(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from a YouTube video.

        Uses yt-dlp to extract video information.

        Args:
            video_id: YouTube video ID

        Returns:
            Dictionary with metadata:
            {
                'title': str,
                'description': str,
                'upload_date': datetime,
                'channel': str,
                'duration': int (seconds),
                'views': int,
            }

        Returns None if extraction fails.
        """
        try:
            import yt_dlp
        except ImportError:
            self.logger.warning("yt-dlp not installed, skipping metadata extraction")
            return None

        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": self.timeout,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)

            # Parse upload date
            upload_date_str = info.get("upload_date")
            if upload_date_str:
                try:
                    upload_date = datetime.strptime(upload_date_str, "%Y%m%d")
                except Exception:
                    upload_date = None
            else:
                upload_date = None

            return {
                "title": info.get("title", f"YouTube Video {video_id}"),
                "description": info.get("description", ""),
                "upload_date": upload_date,
                "channel": info.get("uploader", "Unknown"),
                "duration": info.get("duration", 0),
                "views": info.get("view_count", 0),
            }

        except Exception as e:
            self.logger.warning(f"Error extracting metadata for {video_id}: {e}")
            return None

    def extract_youtube_video(self, video_url: str) -> Optional[Dict[str, Any]]:
        """
        Extract transcript and metadata from a YouTube video.

        Args:
            video_url: YouTube URL or video ID

        Returns:
            Dictionary with extracted content:
            {
                'video_id': str,
                'title': str,
                'transcript': str,
                'published_at': datetime,
                'metadata': {
                    'source_url': str,
                    'channel': str,
                    'duration': int,
                    'views': int,
                    'description': str,
                }
            }

        Returns None if extraction fails.
        """
        try:
            # Extract video ID
            video_id = self.extract_video_id(video_url)
            self.logger.debug(f"Extracted video ID: {video_id}")

            # Fetch transcript
            transcript = self.fetch_transcript(video_id)
            if not transcript or len(transcript.strip()) < 50:
                self.logger.warning(f"Transcript too short for video {video_id}")
                return None

            # Extract metadata
            metadata_dict = self.extract_video_metadata(video_id)
            if not metadata_dict:
                # Create minimal metadata if extraction failed
                metadata_dict = {
                    "title": f"YouTube Video {video_id}",
                    "description": "",
                    "upload_date": datetime.utcnow(),
                    "channel": "Unknown",
                    "duration": 0,
                    "views": 0,
                }

            return {
                "video_id": video_id,
                "title": metadata_dict.get("title", f"YouTube Video {video_id}"),
                "transcript": transcript,
                "published_at": metadata_dict.get("upload_date") or datetime.utcnow(),
                "metadata": {
                    "source_url": f"https://www.youtube.com/watch?v={video_id}",
                    "channel": metadata_dict.get("channel", "Unknown"),
                    "duration": metadata_dict.get("duration", 0),
                    "views": metadata_dict.get("views", 0),
                    "description": metadata_dict.get("description", ""),
                    "extraction_method": "youtube_transcript_api",
                    "confidence": 0.95,  # Transcripts are usually reliable
                    "content_size": len(transcript),
                },
            }

        except ValidationError as e:
            self.logger.warning(f"Validation error extracting video: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error extracting video: {e}", exc_info=True)
            return None

    def extract_youtube_video_to_db(self, video_url: str) -> Dict[str, Any]:
        """
        Extract YouTube video and store in database.

        Args:
            video_url: YouTube URL or video ID

        Returns:
            Result dictionary:
            {
                'success': bool,
                'video_id': str,
                'title': str,
                'content_id': int (if successful),
                'error': str (if failed),
                'error_type': str,
            }
        """
        try:
            # Extract video ID first for logging
            try:
                video_id = self.extract_video_id(video_url)
            except ValidationError as e:
                self.logger.warning(f"Invalid video URL: {video_url}")
                return {
                    "success": False,
                    "video_id": None,
                    "title": None,
                    "url": video_url,
                    "error": str(e),
                    "error_type": "permanent",
                }

            self.logger.info(f"Extracting YouTube video: {video_id}")

            # Extract content
            extracted = self.extract_youtube_video(video_url)
            if not extracted:
                self.logger.warning(f"Failed to extract content from video {video_id}")
                return {
                    "success": False,
                    "video_id": video_id,
                    "title": None,
                    "url": video_url,
                    "error": "Content extraction failed",
                    "error_type": "extraction",
                }

            # Store in database
            now = datetime.utcnow()
            raw_content = RawContent(
                source_type="youtube",
                source_url=extracted["metadata"]["source_url"],
                collected_at=now.isoformat(),
                content_text=extracted["transcript"],
                title=extracted["title"],
                published_at=extracted["published_at"].isoformat()
                if isinstance(extracted["published_at"], datetime)
                else extracted["published_at"],
                metadata=extracted["metadata"],
            )

            content_id = self.storage.store_raw_content(raw_content)
            self.logger.info(
                f"Stored YouTube content (ID: {content_id}) from video {video_id}"
            )

            # Update source status
            source_status = SourceStatus(
                source_id=extracted["metadata"]["source_url"],
                source_type="youtube",
                last_collected_at=now,
                last_success=now,
                last_error=None,
                consecutive_failures=0,
            )
            self.storage.update_source_status(source_status)

            return {
                "success": True,
                "video_id": video_id,
                "title": extracted["title"],
                "url": video_url,
                "content_id": content_id,
                "channel": extracted["metadata"].get("channel", "Unknown"),
            }

        except ValidationError as e:
            self.logger.warning(f"Validation error: {e}")
            return {
                "success": False,
                "video_id": video_id if "video_id" in locals() else None,
                "title": None,
                "url": video_url,
                "error": str(e),
                "error_type": "permanent",
            }

        except Exception as e:
            self.logger.error(f"Unexpected error: {e}", exc_info=True)
            return {
                "success": False,
                "video_id": video_id if "video_id" in locals() else None,
                "title": None,
                "url": video_url,
                "error": str(e),
                "error_type": "unknown",
            }

    def extract_youtube_videos(self, video_urls: List[str]) -> Dict[str, Any]:
        """
        Extract multiple YouTube videos.

        Args:
            video_urls: List of YouTube URLs or video IDs

        Returns:
            Summary dictionary:
            {
                'total': int,
                'success': int,
                'failed': int,
                'results': [
                    {
                        'success': bool,
                        'video_id': str,
                        'title': str,
                        'content_id': int (if successful),
                        'error': str (if failed),
                        'error_type': str,
                    },
                    ...
                ]
            }
        """
        self.logger.info(f"Starting extraction of {len(video_urls)} YouTube videos")

        results = []
        for video_url in video_urls:
            result = self.extract_youtube_video_to_db(video_url)
            results.append(result)

        # Count results
        successful = sum(1 for r in results if r["success"])
        failed = sum(1 for r in results if not r["success"])

        self.logger.info(
            f"YouTube extraction complete: {successful} successful, {failed} failed"
        )

        return {
            "total": len(video_urls),
            "success": successful,
            "failed": failed,
            "results": results,
        }
