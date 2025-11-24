"""
Newsletter Website Scraper

Fetches and extracts content from newsletter websites.
Handles network failures with retry logic and comprehensive logging.
"""

import logging
from datetime import datetime
from typing import Dict, Optional, List, Any
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from src.database.models import RawContent, SourceStatus
from src.database import DatabaseStorage
from src.utils.error_handling import (
    with_retries_and_logging,
    NetworkError,
    ValidationError,
    is_retryable_error,
)
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)


class NewsletterScraperError(Exception):
    """Base exception for newsletter scraper errors."""

    pass


class NewsletterScraper:
    """
    Scrapes content from newsletter websites.

    Features:
    - Fetches HTML content with automatic retry on network errors
    - Extracts title, content, and metadata from HTML
    - Handles various HTML structures and edge cases
    - Updates source health status in database
    - Comprehensive logging of all operations
    """

    def __init__(self, storage: DatabaseStorage, timeout: int = 10):
        """
        Initialize newsletter scraper.

        Args:
            storage: DatabaseStorage instance for persistence
            timeout: Request timeout in seconds (default: 10)
        """
        self.storage = storage
        self.timeout = timeout
        self.logger = get_logger(__name__)

    @with_retries_and_logging(max_attempts=3, backoff_min=1.0, backoff_max=4.0, operation_name="newsletter fetch")
    def fetch_newsletter(self, url: str) -> str:
        """
        Fetch HTML content from a newsletter URL.

        Automatically retries on network errors with exponential backoff.
        Non-network errors (invalid URL, 404, etc.) fail immediately.

        Args:
            url: Newsletter URL to fetch

        Returns:
            HTML content as string

        Raises:
            NetworkError: On network/timeout errors (retried automatically)
            ValidationError: On invalid URL or permanent HTTP errors
            requests.RequestException: On other request errors

        Note:
            This method is decorated with @with_retries_and_logging which
            automatically logs retry attempts and failures.
        """
        # Validate URL format
        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                raise ValidationError(f"Invalid URL format: {url}")
        except Exception as e:
            raise ValidationError(f"Invalid URL: {url}") from e

        # Fetch URL with requests
        try:
            response = requests.get(
                url,
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )

            # Classify HTTP errors
            if response.status_code == 404:
                raise ValidationError(f"Newsletter not found (404): {url}")
            elif response.status_code in [401, 403]:
                raise ValidationError(f"Access denied ({response.status_code}): {url}")
            elif response.status_code in [429, 503, 504]:
                # These are retryable
                raise NetworkError(f"Service unavailable ({response.status_code}): {url}")
            elif response.status_code >= 400:
                # Other 4xx/5xx are permanent
                raise ValidationError(f"HTTP {response.status_code}: {url}")

            response.raise_for_status()
            return response.text

        except requests.exceptions.Timeout as e:
            raise NetworkError(f"Request timeout ({self.timeout}s): {url}") from e
        except requests.exceptions.ConnectionError as e:
            raise NetworkError(f"Connection error: {url}") from e
        except requests.exceptions.RequestException as e:
            # Check if it's a timeout or connection error
            if "timeout" in str(e).lower() or "connection" in str(e).lower():
                raise NetworkError(f"Network error: {str(e)}") from e
            # Other request errors are permanent
            raise ValidationError(f"Request failed: {str(e)}") from e

    def extract_content(self, html: str, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract structured content from HTML.

        Attempts multiple extraction strategies:
        1. Look for article/main content tags
        2. Extract from common div/section structures
        3. Fallback to all paragraph text if above fails
        4. Always extract title and metadata

        Args:
            html: HTML content as string
            url: Original URL (for metadata)

        Returns:
            Dictionary with extracted content:
            {
                'title': str,
                'content': str,
                'published_at': datetime,
                'metadata': {
                    'source_url': str,
                    'extraction_method': str,
                    'confidence': float (0.0-1.0),
                    'content_size': int,
                    'extracted_size': int
                }
            }

        Returns None if extraction fails completely.
        """
        try:
            # Try lxml parser first, fallback to html.parser
            try:
                soup = BeautifulSoup(html, "lxml")
            except Exception:
                # Fallback to html.parser if lxml not available
                soup = BeautifulSoup(html, "html.parser")

            # Extract title
            title = self._extract_title(soup, url)
            if not title:
                self.logger.warning(f"Could not extract title from {url}")
                return None

            # Extract publication date
            published_at = self._extract_publish_date(soup)
            if not published_at:
                self.logger.warning(
                    f"Could not extract publish date from {url}, using current time"
                )
                published_at = datetime.utcnow()

            # Extract content
            content = self._extract_content_text(soup)
            if not content or len(content.strip()) < 100:
                self.logger.warning(
                    f"Extracted content too short ({len(content) if content else 0} chars) from {url}"
                )
                return None

            # Determine extraction confidence
            confidence = self._calculate_confidence(html, content, title)

            return {
                "title": title,
                "content": content,
                "published_at": published_at,
                "metadata": {
                    "source_url": url,
                    "extraction_method": self._extraction_method,
                    "confidence": confidence,
                    "html_size": len(html),
                    "extracted_size": len(content),
                },
            }

        except Exception as e:
            self.logger.error(f"Error extracting content from {url}: {e}", exc_info=True)
            return None

    def _extract_title(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """
        Extract title from HTML.

        Tries multiple sources:
        1. <title> tag
        2. og:title meta tag
        3. h1 tag
        4. h2 tag
        """
        # Try <title> tag first
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            if title and len(title) > 5:  # Title too short is probably boilerplate
                self._extraction_method = "title_tag"
                return title

        # Try og:title meta tag
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title.get("content").strip()
            if title:
                self._extraction_method = "og_title"
                return title

        # Try h1 tag
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)
            if title and len(title) > 5:
                self._extraction_method = "h1_tag"
                return title

        # Try h2 tag
        h2 = soup.find("h2")
        if h2 and h2.get_text(strip=True):
            title = h2.get_text(strip=True)
            if title and len(title) > 5:
                self._extraction_method = "h2_tag"
                return title

        return None

    def _extract_publish_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """
        Extract publication date from HTML.

        Tries multiple sources:
        1. og:publish_date meta tag
        2. article:published_time meta tag
        3. Various date patterns in HTML
        """
        from dateutil import parser as date_parser

        # Try og:publish_date
        og_date = soup.find("meta", property="og:publish_date")
        if og_date and og_date.get("content"):
            try:
                return date_parser.parse(og_date.get("content"))
            except Exception:
                pass

        # Try article:published_time
        pub_time = soup.find("meta", property="article:published_time")
        if pub_time and pub_time.get("content"):
            try:
                return date_parser.parse(pub_time.get("content"))
            except Exception:
                pass

        # Try other common date meta tags
        for attr in ["datePublished", "date", "Date"]:
            date_tag = soup.find("meta", attrs={"name": attr})
            if date_tag and date_tag.get("content"):
                try:
                    return date_parser.parse(date_tag.get("content"))
                except Exception:
                    pass

        return None

    def _extract_content_text(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract main content text from HTML.

        Tries multiple strategies:
        1. Extract from <article> tags
        2. Extract from common content div/section structures
        3. Extract from all <p> tags
        4. Fallback to body text
        """
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Try article tag first
        article = soup.find("article")
        if article:
            text = self._get_clean_text(article)
            if text and len(text.strip()) > 100:
                self._extraction_method = "article_tag"
                return text

        # Try common content div structures
        for selector in ["div.content", "div.post-content", "div.entry-content", "main"]:
            # BeautifulSoup doesn't support CSS selectors directly without css_select
            # so we'll search by class/id
            if selector.startswith("div."):
                class_name = selector.split(".")[1]
                content_div = soup.find("div", class_=class_name)
                if content_div:
                    text = self._get_clean_text(content_div)
                    if text and len(text.strip()) > 100:
                        self._extraction_method = f"div_class_{class_name}"
                        return text

        # Try main tag
        main = soup.find("main")
        if main:
            text = self._get_clean_text(main)
            if text and len(text.strip()) > 100:
                self._extraction_method = "main_tag"
                return text

        # Extract all paragraphs
        paragraphs = soup.find_all("p")
        if paragraphs:
            texts = [p.get_text(strip=True) for p in paragraphs]
            text = "\n\n".join(texts)
            if text and len(text.strip()) > 100:
                self._extraction_method = "paragraph_tags"
                return text

        # Fallback: get all body text
        body = soup.find("body")
        if body:
            text = self._get_clean_text(body)
            if text and len(text.strip()) > 100:
                self._extraction_method = "body_fallback"
                return text

        return None

    def _get_clean_text(self, element) -> str:
        """
        Get clean text from BeautifulSoup element.

        Removes extra whitespace and formatting.
        """
        text = element.get_text(separator="\n", strip=True)
        # Clean up multiple newlines
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)

    def _calculate_confidence(self, html: str, content: str, title: str) -> float:
        """
        Calculate extraction confidence score (0.0 to 1.0).

        Higher scores indicate more reliable extraction:
        - Explicit extraction methods (og tags, article tag): 0.9-1.0
        - Structured methods (h1, main): 0.7-0.9
        - Heuristic methods (paragraphs): 0.5-0.7
        - Fallback methods: 0.3-0.5

        Also considers content quality:
        - Sufficient content length
        - Reasonable title length
        - Content/HTML ratio
        """
        # Base confidence from extraction method
        if self._extraction_method in ["og_title", "article_tag"]:
            confidence = 0.95
        elif self._extraction_method in ["title_tag", "main_tag", "div_class_content"]:
            confidence = 0.85
        elif self._extraction_method in ["h1_tag", "h2_tag", "paragraph_tags"]:
            confidence = 0.70
        else:
            confidence = 0.50

        # Adjust based on content quality
        content_length = len(content)
        title_length = len(title)

        # Content too short
        if content_length < 500:
            confidence *= 0.8

        # Content very short
        if content_length < 200:
            confidence *= 0.6

        # Title too long (probably extracted metadata)
        if title_length > 200:
            confidence *= 0.9

        # Content/HTML ratio
        html_length = len(html)
        if html_length > 0:
            ratio = content_length / html_length
            # Expect 5-50% of HTML to be actual content
            if ratio < 0.05 or ratio > 0.50:
                confidence *= 0.9

        return min(1.0, max(0.0, confidence))

    def scrape_newsletter(
        self, newsletter: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Scrape a single newsletter.

        Args:
            newsletter: Dict with 'name' and 'url' keys

        Returns:
            Dictionary with scraping result:
            {
                'success': bool,
                'url': str,
                'name': str,
                'content_id': int (if successful),
                'error': str (if failed),
                'error_type': str (retryable/permanent),
            }
        """
        name = newsletter.get("name", "Unknown")
        url = newsletter.get("url")

        if not url:
            self.logger.warning(f"Newsletter {name} has no URL configured")
            return {
                "success": False,
                "name": name,
                "url": url,
                "error": "No URL configured",
                "error_type": "configuration",
            }

        self.logger.info(f"Scraping newsletter: {name} from {url}")

        try:
            # Fetch HTML
            html = self.fetch_newsletter(url)
            self.logger.debug(f"Fetched {len(html)} bytes from {url}")

            # Extract content
            extracted = self.extract_content(html, url)
            if not extracted:
                self.logger.warning(f"Failed to extract content from {url}")
                return {
                    "success": False,
                    "name": name,
                    "url": url,
                    "error": "Content extraction failed",
                    "error_type": "extraction",
                }

            # Store in database
            now = datetime.utcnow()
            raw_content = RawContent(
                source_type="newsletter",
                source_url=url,
                collected_at=now.isoformat(),
                content_text=extracted["content"],
                title=extracted["title"],
                published_at=extracted["published_at"].isoformat() if isinstance(extracted["published_at"], datetime) else extracted["published_at"],
                metadata=extracted["metadata"],
            )

            content_id = self.storage.store_raw_content(raw_content)
            self.logger.info(
                f"Stored newsletter content (ID: {content_id}) from {url} "
                f"[confidence: {extracted['metadata']['confidence']:.2f}]"
            )

            # Update source status
            source_status = SourceStatus(
                source_id=url,
                source_type="newsletter",
                last_collected_at=datetime.utcnow(),
                last_success=datetime.utcnow(),
                last_error=None,
                consecutive_failures=0,
            )
            self.storage.update_source_status(source_status)

            return {
                "success": True,
                "name": name,
                "url": url,
                "content_id": content_id,
                "confidence": extracted["metadata"]["confidence"],
            }

        except ValidationError as e:
            self.logger.warning(f"Validation error scraping {name}: {e}")
            # Update source status with error
            source_status = SourceStatus(
                source_id=url,
                source_type="newsletter",
                last_collected_at=datetime.utcnow(),
                last_success=None,
                last_error=str(e),
                consecutive_failures=1,
            )
            self.storage.update_source_status(source_status)

            return {
                "success": False,
                "name": name,
                "url": url,
                "error": str(e),
                "error_type": "permanent",
            }

        except NetworkError as e:
            self.logger.warning(f"Network error scraping {name} (will retry): {e}")
            return {
                "success": False,
                "name": name,
                "url": url,
                "error": str(e),
                "error_type": "retryable",
            }

        except Exception as e:
            self.logger.error(f"Unexpected error scraping {name}: {e}", exc_info=True)
            return {
                "success": False,
                "name": name,
                "url": url,
                "error": str(e),
                "error_type": "unknown",
            }

    def scrape_all_newsletters(self, newsletters: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Scrape all configured newsletters.

        Args:
            newsletters: List of newsletter dicts with 'name' and 'url' keys

        Returns:
            Summary dictionary:
            {
                'total': int,
                'success': int,
                'failed': int,
                'results': [
                    {
                        'success': bool,
                        'name': str,
                        'url': str,
                        'content_id': int (if successful),
                        'error': str (if failed),
                        'error_type': str,
                    },
                    ...
                ]
            }
        """
        self.logger.info(f"Starting collection of {len(newsletters)} newsletters")

        results = []
        for newsletter in newsletters:
            result = self.scrape_newsletter(newsletter)
            results.append(result)

        # Count results
        successful = sum(1 for r in results if r["success"])
        failed = sum(1 for r in results if not r["success"])

        self.logger.info(
            f"Newsletter collection complete: {successful} successful, {failed} failed"
        )

        return {
            "total": len(newsletters),
            "success": successful,
            "failed": failed,
            "results": results,
        }
