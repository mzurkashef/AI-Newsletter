"""Content summarization and formatting for AI Newsletter system."""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from src.database.storage import DatabaseStorage
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)


class ContentSummarizationError(Exception):
    """Exception raised for content summarization errors."""

    pass


@dataclass
class SummaryFormat:
    """Format configuration for content summaries."""

    min_length: int = 50
    max_length: int = 200
    include_source: bool = True
    include_categories: bool = True
    include_summary_type: bool = True


class ContentSummarizer:
    """Summarize and format content for newsletter inclusion.

    Implements abstractive summarization using sentence extraction and
    formatting tailored for newsletter consumption. Supports configurable
    summary length and markdown formatting.
    """

    def __init__(
        self,
        storage: DatabaseStorage,
        summary_format: Optional[SummaryFormat] = None,
    ) -> None:
        """Initialize summarizer with storage and format configuration.

        Args:
            storage: DatabaseStorage instance for content retrieval
            summary_format: SummaryFormat configuration for summaries

        Raises:
            ContentSummarizationError: If storage is invalid
        """
        if not isinstance(storage, DatabaseStorage):
            raise ContentSummarizationError("Invalid storage instance")

        self.storage = storage
        self.summary_format = summary_format or SummaryFormat()

        if not (self.summary_format.min_length > 0):
            raise ContentSummarizationError("min_length must be > 0")
        if not (self.summary_format.max_length >= self.summary_format.min_length):
            raise ContentSummarizationError(
                "max_length must be >= min_length"
            )

        logger.info(
            f"Initialized ContentSummarizer with min_length="
            f"{self.summary_format.min_length}, "
            f"max_length={self.summary_format.max_length}"
        )

    def _extract_key_sentences(self, content: str, num_sentences: int = 3) -> List[str]:
        """Extract key sentences from content using simple heuristics.

        Selects sentences based on:
        - Position (first and last sentences often important)
        - Length (avoid very short sentences)
        - Keyword presence (sentences with topic keywords)

        Args:
            content: Text content to extract from
            num_sentences: Target number of sentences to extract

        Returns:
            List of extracted key sentences
        """
        sentences = [s.strip() for s in content.split(".") if s.strip()]

        if not sentences:
            return []

        if len(sentences) <= num_sentences:
            return sentences

        # Score sentences
        scored_sentences = []
        for i, sentence in enumerate(sentences):
            score = 0.0

            # Position scoring: first and last are important
            if i == 0:
                score += 2.0
            elif i == len(sentences) - 1:
                score += 1.5
            elif i < 3:
                score += 1.0

            # Length scoring: avoid very short or very long
            words = sentence.split()
            if 5 <= len(words) <= 30:
                score += 1.0

            # Keyword presence: sentences with numbers/entities
            if any(c.isdigit() for c in sentence):
                score += 1.0

            scored_sentences.append((sentence, score, i))

        # Select top sentences and sort by original position
        top_sentences = sorted(scored_sentences, key=lambda x: x[1], reverse=True)[
            :num_sentences
        ]
        top_sentences.sort(key=lambda x: x[2])

        return [s[0] for s in top_sentences]

    def _create_formatted_summary(
        self, content: Dict[str, Any], summary_text: str
    ) -> str:
        """Create formatted summary with metadata.

        Formats summary as markdown with title, summary, and metadata.

        Args:
            content: Content dictionary with metadata
            summary_text: The summary text

        Returns:
            Formatted summary string
        """
        lines = []

        # Title
        title = content.get("title", "Untitled")
        lines.append(f"**{title}**\n")

        # Summary
        lines.append(summary_text)

        # Metadata
        if self.summary_format.include_source:
            source = content.get("source", "Unknown source")
            lines.append(f"\n_Source: {source}_")

        if self.summary_format.include_categories:
            categories = content.get("categories", [])
            if categories:
                cat_str = ", ".join(categories)
                lines.append(f"_Categories: {cat_str}_")

        if self.summary_format.include_summary_type:
            summary_type = content.get("summary_type", "extractive")
            lines.append(f"_Type: {summary_type}_")

        return "\n".join(lines)

    def summarize_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize a single content item.

        Extracts key sentences and creates a formatted summary that
        fits within the configured length constraints.

        Args:
            content: Content dictionary with 'title' and 'content' keys

        Returns:
            Dictionary with:
                - summary: Formatted summary string
                - summary_type: 'extractive'
                - original_length: Word count of original
                - summary_length: Word count of summary
                - compression_ratio: Original length / summary length
                - sentences_extracted: Number of extracted sentences

        Raises:
            ContentSummarizationError: If content is invalid or missing required fields
        """
        if not isinstance(content, dict):
            raise ContentSummarizationError("Content must be a dictionary")

        if "content" not in content or not content["content"]:
            raise ContentSummarizationError("Content missing 'content' field")

        original_text = str(content.get("content", ""))
        original_words = len(original_text.split())

        if original_words == 0:
            raise ContentSummarizationError("Content text is empty")

        # Extract key sentences
        num_sentences = 3
        if original_words < 100:
            num_sentences = 1
        elif original_words < 200:
            num_sentences = 2

        key_sentences = self._extract_key_sentences(original_text, num_sentences)

        if not key_sentences:
            summary_text = original_text[: self.summary_format.max_length]
        else:
            summary_text = ". ".join(key_sentences)
            if not summary_text.endswith("."):
                summary_text += "."

        # Ensure summary meets length constraints
        summary_words = len(summary_text.split())

        if summary_words < self.summary_format.min_length:
            # Too short, include more content
            summary_text = original_text[: self.summary_format.max_length * 3]
            summary_words = len(summary_text.split())

        if summary_words > self.summary_format.max_length:
            # Too long, truncate
            words = summary_text.split()
            summary_text = " ".join(words[: self.summary_format.max_length])
            if not summary_text.endswith("."):
                summary_text += "."
            summary_words = len(summary_text.split())

        # Create formatted summary
        formatted = self._create_formatted_summary(content, summary_text)

        compression_ratio = (
            original_words / summary_words if summary_words > 0 else 1.0
        )

        logger.info(
            f"Summarized content: original={original_words}w, "
            f"summary={summary_words}w, ratio={compression_ratio:.2f}"
        )

        return {
            "summary": formatted,
            "summary_text": summary_text,
            "summary_type": "extractive",
            "original_length": original_words,
            "summary_length": summary_words,
            "compression_ratio": compression_ratio,
            "sentences_extracted": len(key_sentences),
        }

    def summarize_content_list(
        self, content_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Batch summarize multiple content items.

        Args:
            content_list: List of content dictionaries

        Returns:
            Dictionary with:
                - total: Total items processed
                - successful: Successfully summarized items
                - failed: Failed items
                - content: List of summarized items with metadata
                - stats: Summary statistics

        Raises:
            ContentSummarizationError: If content_list is invalid
        """
        if not isinstance(content_list, list):
            raise ContentSummarizationError("Content list must be a list")

        logger.info(f"Starting batch summarization of {len(content_list)} items")

        successful = 0
        failed = 0
        summarized_items = []
        summary_lengths = []
        compression_ratios = []

        for i, content in enumerate(content_list):
            try:
                result = self.summarize_content(content)
                summarized_items.append(
                    {
                        **content,
                        "summary": result["summary"],
                        "summary_text": result["summary_text"],
                        "summary_type": result["summary_type"],
                        "compression_ratio": result["compression_ratio"],
                    }
                )
                summary_lengths.append(result["summary_length"])
                compression_ratios.append(result["compression_ratio"])
                successful += 1
            except ContentSummarizationError as e:
                logger.warning(f"Failed to summarize item {i}: {str(e)}")
                failed += 1

        avg_summary_length = (
            sum(summary_lengths) / len(summary_lengths)
            if summary_lengths
            else 0
        )
        avg_compression_ratio = (
            sum(compression_ratios) / len(compression_ratios)
            if compression_ratios
            else 1.0
        )

        logger.info(
            f"Batch summarization complete: {successful} successful, "
            f"{failed} failed, avg_length={avg_summary_length:.0f}, "
            f"avg_ratio={avg_compression_ratio:.2f}"
        )

        return {
            "total": len(content_list),
            "successful": successful,
            "failed": failed,
            "content": summarized_items,
            "stats": {
                "average_summary_length": avg_summary_length,
                "average_compression_ratio": avg_compression_ratio,
                "success_rate": (successful / len(content_list) * 100)
                if content_list
                else 0,
                "total_summary_length": sum(summary_lengths),
            },
        }

    def summarize_database_content(
        self, source_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Summarize content from database.

        Retrieves unprocessed content from database and creates summaries.

        Args:
            source_type: Optional filter by source type

        Returns:
            Dictionary with:
                - total: Total items processed
                - successful: Successfully summarized
                - failed: Failed items
                - updates: Number of database updates
                - stats: Summary statistics

        Raises:
            ContentSummarizationError: If database operation fails
        """
        try:
            logger.info(f"Retrieving unprocessed content from database")
            content_list = self.storage.get_processed_content(
                status="categorized"
            )

            if not content_list:
                logger.info("No unprocessed content found")
                return {
                    "total": 0,
                    "successful": 0,
                    "failed": 0,
                    "updates": 0,
                    "stats": {},
                }

            if source_type:
                content_list = [
                    c for c in content_list if c.get("source") == source_type
                ]
                logger.info(f"Filtered to {len(content_list)} items from {source_type}")

            # Summarize
            summary_result = self.summarize_content_list(content_list)

            # Update database
            updates = 0
            for item in summary_result["content"]:
                try:
                    self.storage.update_content_status(
                        item.get("id"),
                        "summarized",
                        metadata={
                            "summary": item.get("summary"),
                            "summary_text": item.get("summary_text"),
                            "compression_ratio": item.get("compression_ratio"),
                        },
                    )
                    updates += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to update database for item {item.get('id')}: "
                        f"{str(e)}"
                    )

            logger.info(
                f"Database summarization complete: {updates} items updated"
            )

            return {
                **summary_result,
                "updates": updates,
            }

        except Exception as e:
            logger.error(f"Database summarization failed: {str(e)}")
            raise ContentSummarizationError(
                f"Failed to summarize database content: {str(e)}"
            )

    def update_summary_format(self, summary_format: SummaryFormat) -> None:
        """Update summary format configuration.

        Args:
            summary_format: New SummaryFormat configuration

        Raises:
            ContentSummarizationError: If configuration is invalid
        """
        if not isinstance(summary_format, SummaryFormat):
            raise ContentSummarizationError(
                "summary_format must be a SummaryFormat instance"
            )

        if not (summary_format.min_length > 0):
            raise ContentSummarizationError("min_length must be > 0")

        if not (summary_format.max_length >= summary_format.min_length):
            raise ContentSummarizationError(
                "max_length must be >= min_length"
            )

        self.summary_format = summary_format
        logger.info(
            f"Updated summary format: min={summary_format.min_length}, "
            f"max={summary_format.max_length}"
        )

    def get_summarization_statistics(
        self, content_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate summarization statistics for content batch.

        Args:
            content_list: List of summarized content items

        Returns:
            Dictionary with:
                - total: Total items
                - avg_original_length: Average original word count
                - avg_summary_length: Average summary word count
                - avg_compression_ratio: Average compression ratio
                - min_compression: Minimum compression ratio
                - max_compression: Maximum compression ratio
                - total_compression: Total words reduced
        """
        if not content_list:
            return {
                "total": 0,
                "avg_original_length": 0,
                "avg_summary_length": 0,
                "avg_compression_ratio": 1.0,
                "min_compression": 1.0,
                "max_compression": 1.0,
                "total_compression": 0,
            }

        original_lengths = []
        summary_lengths = []
        compression_ratios = []

        for content in content_list:
            try:
                result = self.summarize_content(content)
                original_lengths.append(result["original_length"])
                summary_lengths.append(result["summary_length"])
                compression_ratios.append(result["compression_ratio"])
            except ContentSummarizationError:
                pass

        if not compression_ratios:
            return {
                "total": len(content_list),
                "avg_original_length": 0,
                "avg_summary_length": 0,
                "avg_compression_ratio": 1.0,
                "min_compression": 1.0,
                "max_compression": 1.0,
                "total_compression": 0,
            }

        total_original = sum(original_lengths)
        total_summary = sum(summary_lengths)

        return {
            "total": len(content_list),
            "avg_original_length": sum(original_lengths) / len(original_lengths),
            "avg_summary_length": sum(summary_lengths) / len(summary_lengths),
            "avg_compression_ratio": sum(compression_ratios) / len(compression_ratios),
            "min_compression": min(compression_ratios),
            "max_compression": max(compression_ratios),
            "total_compression": total_original - total_summary,
        }

    def find_long_summaries(
        self, content_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find items with summaries exceeding max_length.

        Args:
            content_list: List of content items (should be pre-summarized)

        Returns:
            List of items with oversized summaries
        """
        long_summaries = []

        for content in content_list:
            if "summary_text" in content:
                summary_length = len(content["summary_text"].split())
                if summary_length > self.summary_format.max_length:
                    long_summaries.append(
                        {
                            **content,
                            "actual_length": summary_length,
                            "max_allowed": self.summary_format.max_length,
                            "excess": summary_length
                            - self.summary_format.max_length,
                        }
                    )

        logger.info(f"Found {len(long_summaries)} items with oversized summaries")

        return long_summaries
