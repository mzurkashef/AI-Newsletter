"""
Tests for newsletter website scraper.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import logging

from src.collectors.newsletter_scraper import (
    NewsletterScraper,
    NewsletterScraperError,
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
def scraper(mock_storage):
    """Create scraper instance with mock storage."""
    return NewsletterScraper(storage=mock_storage, timeout=10)


@pytest.fixture
def sample_html():
    """Sample HTML for testing extraction."""
    return """
    <html>
    <head>
        <title>Sample Newsletter Article</title>
        <meta property="og:title" content="Sample Newsletter Article">
        <meta property="og:publish_date" content="2025-11-20T10:00:00Z">
    </head>
    <body>
        <article>
            <h1>Sample Newsletter Article</h1>
            <p>This is the first paragraph of content.</p>
            <p>This is the second paragraph with more details.</p>
            <p>This is the third paragraph with even more information about the topic.</p>
            <p>Final paragraph with conclusion.</p>
        </article>
    </body>
    </html>
    """


@pytest.fixture
def sample_newsletter():
    """Sample newsletter configuration."""
    return {
        "name": "Test Newsletter",
        "url": "https://example.com/newsletter"
    }


class TestNewsletterScraperFetch:
    """Test fetch functionality."""

    def test_fetch_success(self, scraper):
        """Test successful fetch."""
        expected_html = "<html><body>Test content</body></html>"

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.text = expected_html
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            html = scraper.fetch_newsletter("https://example.com/newsletter")
            assert html == expected_html
            mock_get.assert_called_once()

    def test_fetch_invalid_url(self, scraper):
        """Test fetch with invalid URL format."""
        with pytest.raises(ValidationError):
            scraper.fetch_newsletter("not-a-url")

    def test_fetch_missing_scheme(self, scraper):
        """Test fetch with URL missing scheme."""
        with pytest.raises(ValidationError):
            scraper.fetch_newsletter("example.com/newsletter")

    def test_fetch_http_404(self, scraper):
        """Test fetch with 404 Not Found."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            with pytest.raises(ValidationError):
                scraper.fetch_newsletter("https://example.com/not-found")

    def test_fetch_http_403(self, scraper):
        """Test fetch with 403 Forbidden."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 403
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            with pytest.raises(ValidationError):
                scraper.fetch_newsletter("https://example.com/forbidden")

    def test_fetch_http_429_retryable(self, scraper):
        """Test that HTTP 429 (rate limit) is retryable."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            with pytest.raises(NetworkError):
                scraper.fetch_newsletter("https://example.com/rate-limited")

    def test_fetch_http_503_retryable(self, scraper):
        """Test that HTTP 503 (Service Unavailable) is retryable."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 503
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            with pytest.raises(NetworkError):
                scraper.fetch_newsletter("https://example.com/unavailable")

    def test_fetch_timeout(self, scraper):
        """Test fetch with timeout."""
        import requests

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout("Connection timeout")

            with pytest.raises(NetworkError):
                scraper.fetch_newsletter("https://example.com/slow")

    def test_fetch_connection_error(self, scraper):
        """Test fetch with connection error."""
        import requests

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

            with pytest.raises(NetworkError):
                scraper.fetch_newsletter("https://example.com/unreachable")

    def test_fetch_user_agent(self, scraper):
        """Test that User-Agent header is set."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.text = "<html></html>"
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            scraper.fetch_newsletter("https://example.com/newsletter")

            # Check User-Agent was set
            call_args = mock_get.call_args
            assert "User-Agent" in call_args[1]["headers"]
            assert "Mozilla" in call_args[1]["headers"]["User-Agent"]

    def test_fetch_timeout_parameter(self, scraper):
        """Test that timeout parameter is passed."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.text = "<html></html>"
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            scraper.fetch_newsletter("https://example.com/newsletter")

            # Check timeout was set
            call_args = mock_get.call_args
            assert call_args[1]["timeout"] == 10


class TestNewsletterScraperExtraction:
    """Test content extraction."""

    def test_extract_title_from_title_tag(self, scraper, sample_html):
        """Test extracting title from <title> tag."""
        extracted = scraper.extract_content(sample_html, "https://example.com")

        assert extracted is not None
        assert extracted["title"] == "Sample Newsletter Article"

    def test_extract_content_from_article(self, scraper, sample_html):
        """Test extracting content from <article> tag."""
        extracted = scraper.extract_content(sample_html, "https://example.com")

        assert extracted is not None
        assert "first paragraph" in extracted["content"]
        assert "second paragraph" in extracted["content"]

    def test_extract_publish_date(self, scraper, sample_html):
        """Test extracting publish date."""
        extracted = scraper.extract_content(sample_html, "https://example.com")

        assert extracted is not None
        assert extracted["published_at"] is not None
        assert isinstance(extracted["published_at"], datetime)

    def test_extract_metadata_structure(self, scraper, sample_html):
        """Test metadata structure."""
        extracted = scraper.extract_content(sample_html, "https://example.com")

        assert extracted is not None
        metadata = extracted["metadata"]
        assert "source_url" in metadata
        assert "extraction_method" in metadata
        assert "confidence" in metadata
        assert "html_size" in metadata
        assert "extracted_size" in metadata

    def test_extract_confidence_score(self, scraper, sample_html):
        """Test confidence score calculation."""
        extracted = scraper.extract_content(sample_html, "https://example.com")

        assert extracted is not None
        confidence = extracted["metadata"]["confidence"]
        assert 0.0 <= confidence <= 1.0

    def test_extract_empty_html(self, scraper):
        """Test extraction from empty HTML."""
        html = "<html><body></body></html>"
        extracted = scraper.extract_content(html, "https://example.com")

        assert extracted is None

    def test_extract_short_content(self, scraper):
        """Test extraction with content too short."""
        html = "<html><body><p>Too short</p></body></html>"
        extracted = scraper.extract_content(html, "https://example.com")

        assert extracted is None

    def test_extract_malformed_html(self, scraper):
        """Test extraction from malformed HTML (should still work with lxml)."""
        html = "<html><body><p>Content paragraph one<p>Content paragraph two"
        extracted = scraper.extract_content(html, "https://example.com")

        # Should handle malformed HTML gracefully
        assert extracted is None or extracted["content"] is not None

    def test_extract_no_title(self, scraper):
        """Test extraction when title is missing."""
        html = "<html><body><article><p>Content about the topic.</p></article></body></html>"
        extracted = scraper.extract_content(html, "https://example.com")

        # Should return None if title is missing
        assert extracted is None

    def test_extract_with_fallback_date(self, scraper):
        """Test extraction with no date (should use current time)."""
        html = """
        <html>
        <head><title>Article Title</title></head>
        <body>
            <article>
                <p>Content paragraph one with meaningful text that provides information.</p>
                <p>Content paragraph two with more meaningful content and details.</p>
                <p>Content paragraph three with even more information and context about the topic. This ensures we have enough text.</p>
                <p>Additional paragraph to ensure we meet minimum content requirements for extraction to be successful and useful.</p>
            </article>
        </body>
        </html>
        """
        extracted = scraper.extract_content(html, "https://example.com")

        assert extracted is not None
        # Should use fallback date
        assert extracted["published_at"] is not None
        assert isinstance(extracted["published_at"], datetime)

    def test_extract_content_size_calculation(self, scraper, sample_html):
        """Test that content size is calculated correctly."""
        extracted = scraper.extract_content(sample_html, "https://example.com")

        assert extracted is not None
        assert extracted["metadata"]["extracted_size"] == len(extracted["content"])
        assert extracted["metadata"]["extracted_size"] > 0


class TestNewsletterScraperScrapeNewsletter:
    """Test single newsletter scraping."""

    def test_scrape_newsletter_success(self, scraper, mock_storage, sample_html, sample_newsletter):
        """Test successful newsletter scraping."""
        with patch.object(scraper, "fetch_newsletter", return_value=sample_html):
            result = scraper.scrape_newsletter(sample_newsletter)

            assert result["success"] is True
            assert result["name"] == "Test Newsletter"
            assert result["url"] == "https://example.com/newsletter"
            assert "content_id" in result
            assert result["content_id"] == 1

    def test_scrape_newsletter_missing_url(self, scraper, mock_storage):
        """Test scraping newsletter with missing URL."""
        newsletter = {"name": "Test Newsletter"}

        result = scraper.scrape_newsletter(newsletter)

        assert result["success"] is False
        assert result["error"] == "No URL configured"
        assert result["error_type"] == "configuration"

    def test_scrape_newsletter_fetch_error(self, scraper, mock_storage, sample_newsletter):
        """Test scraping with network error."""
        with patch.object(scraper, "fetch_newsletter", side_effect=NetworkError("Timeout")):
            result = scraper.scrape_newsletter(sample_newsletter)

            assert result["success"] is False
            assert result["error_type"] == "retryable"

    def test_scrape_newsletter_extraction_error(self, scraper, mock_storage, sample_newsletter):
        """Test scraping with extraction error."""
        with patch.object(scraper, "fetch_newsletter", return_value="<html></html>"):
            result = scraper.scrape_newsletter(sample_newsletter)

            assert result["success"] is False
            assert result["error_type"] == "extraction"

    def test_scrape_newsletter_database_storage(self, scraper, mock_storage, sample_html, sample_newsletter):
        """Test that content is stored in database."""
        with patch.object(scraper, "fetch_newsletter", return_value=sample_html):
            result = scraper.scrape_newsletter(sample_newsletter)

            # Verify storage was called
            mock_storage.store_raw_content.assert_called_once()
            call_args = mock_storage.store_raw_content.call_args[0][0]
            assert isinstance(call_args, RawContent)
            assert call_args.source_type == "newsletter"
            assert call_args.source_url == sample_newsletter["url"]

    def test_scrape_newsletter_source_status_update(self, scraper, mock_storage, sample_html, sample_newsletter):
        """Test that source status is updated."""
        with patch.object(scraper, "fetch_newsletter", return_value=sample_html):
            scraper.scrape_newsletter(sample_newsletter)

            # Verify source status was updated
            mock_storage.update_source_status.assert_called_once()
            call_args = mock_storage.update_source_status.call_args[0][0]
            assert isinstance(call_args, SourceStatus)
            assert call_args.source_id == sample_newsletter["url"]
            assert call_args.consecutive_failures == 0
            assert call_args.last_success is not None

    def test_scrape_newsletter_validation_error(self, scraper, mock_storage, sample_newsletter):
        """Test scraping with validation error."""
        with patch.object(scraper, "fetch_newsletter", side_effect=ValidationError("Invalid URL")):
            result = scraper.scrape_newsletter(sample_newsletter)

            assert result["success"] is False
            assert result["error_type"] == "permanent"

    def test_scrape_newsletter_unexpected_error(self, scraper, mock_storage, sample_newsletter):
        """Test scraping with unexpected error."""
        with patch.object(scraper, "fetch_newsletter", side_effect=Exception("Unexpected")):
            result = scraper.scrape_newsletter(sample_newsletter)

            assert result["success"] is False
            assert result["error_type"] == "unknown"

    def test_scrape_newsletter_confidence_score(self, scraper, mock_storage, sample_html, sample_newsletter):
        """Test that confidence score is included in result."""
        with patch.object(scraper, "fetch_newsletter", return_value=sample_html):
            result = scraper.scrape_newsletter(sample_newsletter)

            assert result["success"] is True
            assert "confidence" in result
            assert 0.0 <= result["confidence"] <= 1.0


class TestNewsletterScraperScrapeAll:
    """Test multiple newsletter scraping."""

    def test_scrape_all_newsletters_success(self, scraper, mock_storage, sample_html):
        """Test scraping all newsletters successfully."""
        newsletters = [
            {"name": "Newsletter 1", "url": "https://example.com/1"},
            {"name": "Newsletter 2", "url": "https://example.com/2"},
            {"name": "Newsletter 3", "url": "https://example.com/3"},
        ]

        with patch.object(scraper, "fetch_newsletter", return_value=sample_html):
            result = scraper.scrape_all_newsletters(newsletters)

            assert result["total"] == 3
            assert result["success"] == 3
            assert result["failed"] == 0
            assert len(result["results"]) == 3

    def test_scrape_all_newsletters_partial_failure(self, scraper, mock_storage, sample_html):
        """Test scraping with some failures."""
        newsletters = [
            {"name": "Newsletter 1", "url": "https://example.com/1"},
            {"name": "Newsletter 2", "url": "https://example.com/2"},
            {"name": "Newsletter 3", "url": "https://example.com/3"},
        ]

        call_count = [0]

        def fetch_side_effect(url):
            call_count[0] += 1
            if call_count[0] == 2:
                raise NetworkError("Network error")
            return sample_html

        with patch.object(scraper, "fetch_newsletter", side_effect=fetch_side_effect):
            result = scraper.scrape_all_newsletters(newsletters)

            assert result["total"] == 3
            assert result["success"] == 2
            assert result["failed"] == 1

    def test_scrape_all_newsletters_all_fail(self, scraper, mock_storage):
        """Test scraping when all newsletters fail."""
        newsletters = [
            {"name": "Newsletter 1", "url": "https://example.com/1"},
            {"name": "Newsletter 2", "url": "https://example.com/2"},
        ]

        with patch.object(scraper, "fetch_newsletter", side_effect=NetworkError("Network error")):
            result = scraper.scrape_all_newsletters(newsletters)

            assert result["total"] == 2
            assert result["success"] == 0
            assert result["failed"] == 2

    def test_scrape_all_newsletters_empty(self, scraper, mock_storage):
        """Test scraping with empty newsletter list."""
        result = scraper.scrape_all_newsletters([])

        assert result["total"] == 0
        assert result["success"] == 0
        assert result["failed"] == 0
        assert result["results"] == []

    def test_scrape_all_newsletters_results_structure(self, scraper, mock_storage, sample_html):
        """Test structure of results."""
        newsletters = [
            {"name": "Newsletter 1", "url": "https://example.com/1"},
        ]

        with patch.object(scraper, "fetch_newsletter", return_value=sample_html):
            result = scraper.scrape_all_newsletters(newsletters)

            assert len(result["results"]) == 1
            item = result["results"][0]
            assert "success" in item
            assert "name" in item
            assert "url" in item


class TestNewsletterScraperIntegration:
    """Integration tests."""

    def test_full_pipeline_success(self, mock_storage, sample_html):
        """Test full scraping pipeline."""
        scraper = NewsletterScraper(storage=mock_storage, timeout=10)
        newsletters = [
            {"name": "Newsletter A", "url": "https://example.com/a"},
            {"name": "Newsletter B", "url": "https://example.com/b"},
        ]

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.text = sample_html
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = scraper.scrape_all_newsletters(newsletters)

            assert result["success"] == 2
            assert result["failed"] == 0
            assert mock_storage.store_raw_content.call_count == 2
            assert mock_storage.update_source_status.call_count == 2

    def test_logging_calls(self, scraper, mock_storage, sample_html, sample_newsletter, caplog):
        """Test that operations are logged."""
        with patch.object(scraper, "fetch_newsletter", return_value=sample_html):
            with caplog.at_level(logging.INFO):
                result = scraper.scrape_newsletter(sample_newsletter)

            assert result["success"] is True
            # Check that something was logged
            assert len(caplog.records) > 0

    def test_multiple_scrape_calls(self, scraper, mock_storage, sample_html):
        """Test multiple sequential scrape calls."""
        newsletter1 = {"name": "Newsletter 1", "url": "https://example.com/1"}
        newsletter2 = {"name": "Newsletter 2", "url": "https://example.com/2"}

        mock_storage.store_raw_content.side_effect = [1, 2]

        with patch.object(scraper, "fetch_newsletter", return_value=sample_html):
            result1 = scraper.scrape_newsletter(newsletter1)
            result2 = scraper.scrape_newsletter(newsletter2)

            assert result1["success"] is True
            assert result2["success"] is True
            assert result1["content_id"] == 1
            assert result2["content_id"] == 2

    def test_timeout_configuration(self):
        """Test timeout configuration."""
        storage = Mock()
        scraper_default = NewsletterScraper(storage=storage)
        scraper_custom = NewsletterScraper(storage=storage, timeout=20)

        assert scraper_default.timeout == 10
        assert scraper_custom.timeout == 20
