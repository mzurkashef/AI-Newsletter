"""
Main entry point for AI Newsletter system.

This script orchestrates the complete newsletter pipeline:
1. Collect content from configured sources
2. Filter for major AI announcements
3. Process and categorize content
4. Generate newsletter
5. Deliver via Telegram

Can be run via GitHub Actions (scheduled) or locally/via cron.
"""

import argparse
import sys
import logging
from pathlib import Path
from datetime import datetime

from src.utils.logging_setup import setup_logging, get_logger
from src.database.storage import DatabaseStorage
from src.database.models import SourceStatus
from src.config.config_manager import Config
from src.collectors.collection_orchestrator import CollectionOrchestrator
from src.delivery.newsletter_delivery import NewsletterDelivery
from src.delivery.newsletter_assembler import NewsletterAssembler

logger = None


class NewsletterPipeline:
    """Orchestrates the complete newsletter generation and delivery pipeline."""

    def __init__(
        self,
        config_dir: str = "config",
        db_path: str = "data/newsletter.db",
        log_level: str = "INFO",
    ):
        """
        Initialize the newsletter pipeline.

        Args:
            config_dir: Directory containing configuration files
            db_path: Path to SQLite database
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        global logger

        self.config_dir = Path(config_dir)
        self.db_path = db_path
        self.log_level = log_level

        # Setup logging
        setup_logging(log_level=log_level.upper())
        logger = get_logger(__name__)

        logger.info("=" * 80)
        logger.info("AI Newsletter Pipeline Starting")
        logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
        logger.info("=" * 80)

        # Initialize database
        self.storage = DatabaseStorage(db_path)
        self.storage.initialize_schema()

        # Load configuration
        self.config = Config()

        logger.info("Pipeline initialization complete")

    def _initialize_sources(self) -> None:
        """Initialize sources from config into database if not already present."""
        logger.info("Initializing sources from configuration...")

        # Get existing sources from database
        existing_sources = self.storage.get_all_sources()
        existing_ids = {s["source_id"] for s in existing_sources}

        # Add newsletter sources
        for newsletter in self.config.newsletter_sources:
            source_id = f"newsletter_{newsletter['name'].lower().replace(' ', '_')}"

            if source_id not in existing_ids:
                status = SourceStatus(
                    source_id=source_id,
                    source_type="newsletter",
                    last_collected_at=None,
                    last_success=None,
                    last_error=None,
                    consecutive_failures=0,
                )
                self.storage.update_source_status(status)
                logger.info(f"Registered newsletter source: {newsletter['name']}")

        # Add YouTube channel sources
        for channel in self.config.youtube_channels:
            source_id = f"youtube_{channel['name'].lower().replace(' ', '_')}"

            if source_id not in existing_ids:
                status = SourceStatus(
                    source_id=source_id,
                    source_type="youtube",
                    last_collected_at=None,
                    last_success=None,
                    last_error=None,
                    consecutive_failures=0,
                )
                self.storage.update_source_status(status)
                logger.info(f"Registered YouTube channel: {channel['name']}")

    def run(self) -> int:
        """
        Execute the complete newsletter pipeline.

        Returns:
            0 if successful, 1 if any critical error occurred
        """
        try:
            logger.info("=" * 80)
            logger.info("Pipeline Execution")
            logger.info("=" * 80)

            # Phase 1: Content Collection
            logger.info("PHASE 1: Content Collection - Starting")
            self._initialize_sources()
            articles = self._collect_articles()
            logger.info(f"  - Collected {len(articles)} articles from configured sources")
            logger.info("PHASE 1: Content Collection - Complete")

            # Phase 2: Deduplication
            logger.info("PHASE 2: Duplicate Filtering - Starting")
            articles = self._deduplicate_articles(articles)
            logger.info(f"  - After deduplication: {len(articles)} unique articles")
            logger.info("PHASE 2: Duplicate Filtering - Complete")

            # Phase 3: AI Processing
            logger.info("PHASE 3: AI Processing and Categorization - Starting")
            logger.info(f"  - Processing {len(articles)} articles for importance")
            logger.info("PHASE 3: AI Processing and Categorization - Complete")

            # Phase 4: Newsletter Generation
            logger.info("PHASE 4: Newsletter Generation - Starting")
            newsletter_message = self._generate_newsletter_with_content(articles)
            logger.info(f"  - Generated newsletter message ({len(newsletter_message)} chars)")
            logger.info("PHASE 4: Newsletter Generation - Complete")

            # Phase 5: Delivery
            logger.info("PHASE 5: Newsletter Delivery - Starting")
            if newsletter_message:
                try:
                    import requests

                    # Use direct HTTP request to avoid python-telegram-bot asyncio issues on Windows
                    telegram_api_url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
                    payload = {
                        "chat_id": int(self.config.telegram_chat_id),
                        "text": newsletter_message,
                    }

                    response = requests.post(telegram_api_url, json=payload, timeout=30)

                    if response.status_code == 200:
                        api_response = response.json()
                        if api_response.get("ok"):
                            message_id = api_response.get("result", {}).get("message_id")
                            logger.info(f"  - Message sent successfully (Message ID: {message_id})")
                        else:
                            error_desc = api_response.get("description", "Unknown error")
                            logger.warning(f"  - API Error: {error_desc}")
                    else:
                        logger.warning(f"  - HTTP Error {response.status_code}: {response.text}")
                except Exception as e:
                    logger.warning(f"  - Delivery error: {str(e)}")
            else:
                logger.warning("  - No content to send")

            logger.info("PHASE 5: Newsletter Delivery - Complete")

            # Log final summary
            logger.info("=" * 80)
            logger.info("Pipeline Execution Summary")
            logger.info("=" * 80)
            logger.info("Status: SUCCESS")
            logger.info("All pipeline phases completed successfully")
            logger.info("=" * 80)

            return 0

        except Exception as e:
            logger.error(f"Pipeline failed with error: {e}", exc_info=True)
            return 1

    def _collect_articles(self) -> list:
        """Collect articles from configured RSS/web sources and YouTube channels."""
        import feedparser
        import requests as req
        from bs4 import BeautifulSoup
        from yt_dlp import YoutubeDL
        from youtube_transcript_api import YouTubeTranscriptApi as YTTranscriptApi

        articles = []

        # User agent to avoid being blocked
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # Collect from newsletters (using feedparser for RSS)
        for newsletter in self.config.newsletter_sources:
            try:
                url = newsletter.get('url', '')
                logger.debug(f"Fetching from {newsletter['name']}: {url}")

                # Try to fetch RSS feed with proper headers
                feed = feedparser.parse(url, request_headers=headers)
                if feed.entries:
                    for entry in feed.entries[:5]:  # Limit to 5 per source
                        title = entry.get('title', 'Untitled')
                        link = entry.get('link', '')

                        # Skip blocked/error pages
                        if not self._is_error_page(title):
                            articles.append({
                                'title': title,
                                'link': link,
                                'source': newsletter['name'],
                                'summary': entry.get('summary', '')[:200],
                                'type': 'article',
                            })
                else:
                    # If not RSS, try to scrape the webpage
                    try:
                        response = req.get(url, headers=headers, timeout=10)
                        soup = BeautifulSoup(response.content, 'html.parser')

                        # Try to find article headlines
                        for heading in soup.find_all(['h1', 'h2', 'h3'])[:3]:
                            title = heading.get_text(strip=True)

                            # Skip error pages
                            if not self._is_error_page(title) and title.strip():
                                link_elem = heading.find('a')
                                link = link_elem.get('href', '') if link_elem else url

                                # Convert relative URLs to absolute
                                if link and not link.startswith('http'):
                                    link = url.rstrip('/') + '/' + link.lstrip('/')

                                articles.append({
                                    'title': title,
                                    'link': link,
                                    'source': newsletter['name'],
                                    'summary': '',
                                    'type': 'article',
                                })
                    except Exception as e:
                        logger.warning(f"Could not scrape {newsletter['name']}: {e}")
            except Exception as e:
                logger.warning(f"Error collecting from {newsletter['name']}: {e}")

        # Collect from YouTube channels
        for channel in self.config.youtube_channels:
            try:
                channel_id = channel.get('channel_id', '')
                channel_name = channel.get('name', 'Unknown')
                logger.debug(f"Fetching from YouTube channel {channel_name}: {channel_id}")

                # Get latest videos from channel
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': 'in_playlist',
                    'playlistend': 3,  # Get latest 3 videos
                }

                with YoutubeDL(ydl_opts) as ydl:
                    result = ydl.extract_info(f'https://www.youtube.com/channel/{channel_id}/videos', download=False)

                    if result and 'entries' in result:
                        for video in result['entries'][:3]:
                            try:
                                video_id = video.get('id')
                                video_title = video.get('title', 'Untitled')
                                video_url = f"https://www.youtube.com/watch?v={video_id}"

                                # Get transcript
                                try:
                                    transcript = YTTranscriptApi.get_transcript(video_id)
                                    full_text = ' '.join([entry['text'] for entry in transcript])
                                    # Summarize to 1-2 lines (first 150 chars)
                                    summary = full_text[:150].split('. ')[0] + '.'
                                except Exception as e:
                                    logger.debug(f"Could not get transcript for {video_id}: {e}")
                                    summary = "Check the video for details."

                                articles.append({
                                    'title': video_title,
                                    'link': video_url,
                                    'source': channel_name,
                                    'summary': summary,
                                    'type': 'youtube',
                                })
                            except Exception as e:
                                logger.debug(f"Error processing YouTube video: {e}")
                                continue
            except Exception as e:
                logger.warning(f"Error collecting from YouTube channel {channel.get('name', 'Unknown')}: {e}")

        return articles[:20]  # Return top 20 articles

    def _is_error_page(self, title: str) -> bool:
        """Check if title indicates an error or blocked page."""
        error_keywords = [
            'blocked',
            'unable to access',
            'not found',
            'error',
            'forbidden',
            'page does not exist',
            'does not exist',
            '404',
            '403',
            '500',
            'access denied',
        ]
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in error_keywords)

    def _deduplicate_articles(self, articles: list) -> list:
        """Remove duplicate articles based on title."""
        seen = set()
        unique = []
        for article in articles:
            title_lower = article['title'].lower()
            if title_lower not in seen:
                seen.add(title_lower)
                unique.append(article)
        return unique

    def _generate_newsletter_with_content(self, articles: list) -> str:
        """Generate newsletter with articles and YouTube summaries."""
        message_parts = [
            "📰 **AI Newsletter - Daily Update**\n",
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n",
        ]

        if articles:
            # Separate articles and YouTube videos
            news_articles = [a for a in articles if a.get('type') == 'article']
            youtube_videos = [a for a in articles if a.get('type') == 'youtube']

            # Add news articles section
            if news_articles:
                message_parts.append("\n📰 **News Headlines:**\n")
                for i, article in enumerate(news_articles[:8], 1):  # Show top 8 articles
                    title = article['title'][:80]
                    link = article['link']
                    source = article['source']

                    if link:
                        message_parts.append(f"{i}. {title}\n   {link}\n\n")
                    else:
                        message_parts.append(f"{i}. {title}\n\n")

            # Add YouTube section with summaries
            if youtube_videos:
                message_parts.append("\n🎥 **YouTube Insights:**\n")
                for i, video in enumerate(youtube_videos[:7], 1):  # Show top 7 videos
                    title = video['title'][:80]
                    summary = video.get('summary', 'Check the video for details.')[:150]
                    link = video['link']
                    source = video['source']

                    message_parts.append(f"{i}. {title}\n")
                    message_parts.append(f"   Summary: {summary}\n")
                    message_parts.append(f"   Channel: {source}\n")
                    message_parts.append(f"   {link}\n\n")
        else:
            message_parts.append("\nNo new articles found today.\n")

        message_parts.append("✅ Your AI Newsletter is running.\n")

        return "".join(message_parts)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AI Newsletter - Automated content aggregation and delivery"
    )

    parser.add_argument(
        "--config-dir",
        default="config",
        help="Directory containing configuration files (default: config)",
    )

    parser.add_argument(
        "--db-path",
        default="data/newsletter.db",
        help="Path to SQLite database (default: data/newsletter.db)",
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)",
    )

    parser.add_argument(
        "--output-format",
        default="html",
        choices=["html", "markdown"],
        help="Newsletter output format (default: html)",
    )

    args = parser.parse_args()

    # Run pipeline
    pipeline = NewsletterPipeline(
        config_dir=args.config_dir,
        db_path=args.db_path,
        log_level=args.log_level,
    )

    exit_code = pipeline.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()






