"""Newsletter assembly module for AI Newsletter system."""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from src.database.storage import DatabaseStorage
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)


class NewsletterAssemblyError(Exception):
    """Exception raised for newsletter assembly errors."""

    pass


@dataclass
class TopicSection:
    """Represents a section in the newsletter for a topic."""

    topic_name: str
    content_items: List[Dict[str, Any]] = field(default_factory=list)
    item_count: int = 0

    def __post_init__(self):
        """Update item count after initialization."""
        self.item_count = len(self.content_items)


@dataclass
class NewsletterConfig:
    """Configuration for newsletter assembly."""

    include_date: bool = True
    include_footer: bool = True
    include_source_credits: bool = True
    week_identifier: Optional[str] = None
    header_format: str = "bold"  # "bold", "markdown", "text"
    skip_empty_categories: bool = True


class NewsletterAssembler:
    """Assemble topic-based newsletters from processed content.

    Creates structured newsletters organized by topic categories with proper
    formatting, headers, footers, and source credits. Handles empty categories,
    date headers, and maintains content organization throughout assembly.
    """

    def __init__(
        self,
        storage: DatabaseStorage,
        config: Optional[NewsletterConfig] = None,
    ) -> None:
        """Initialize newsletter assembler.

        Args:
            storage: DatabaseStorage instance
            config: NewsletterConfig for assembly configuration

        Raises:
            NewsletterAssemblyError: If storage is invalid
        """
        if not isinstance(storage, DatabaseStorage):
            raise NewsletterAssemblyError("Invalid storage instance")

        self.storage = storage
        self.config = config or NewsletterConfig()

        logger.info(
            f"Initialized NewsletterAssembler with "
            f"skip_empty={self.config.skip_empty_categories}, "
            f"include_date={self.config.include_date}"
        )

    def group_content_by_category(
        self, content_list: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group content items by their category.

        Args:
            content_list: List of content items with 'categories' or 'category' field

        Returns:
            Dictionary mapping category names to lists of content items

        Raises:
            NewsletterAssemblyError: If content_list is invalid
        """
        if not isinstance(content_list, list):
            raise NewsletterAssemblyError("Content list must be a list")

        grouped = {}

        for content in content_list:
            # Handle both 'category' (single) and 'categories' (multiple)
            categories = content.get("categories", [])
            if isinstance(categories, str):
                categories = [categories]

            # Fallback to 'category' field if 'categories' not found
            if not categories and "category" in content:
                category = content.get("category")
                if category:
                    categories = [category] if isinstance(category, str) else category

            # Add to each category
            for category in categories:
                if category not in grouped:
                    grouped[category] = []
                grouped[category].append(content)

        logger.info(
            f"Grouped {len(content_list)} items into {len(grouped)} categories"
        )

        return grouped

    def create_header(self) -> str:
        """Create newsletter header with date and title.

        Returns:
            Formatted header string
        """
        header_lines = []

        # Title
        if self.config.header_format == "bold":
            header_lines.append("=" * 50)
            header_lines.append("📰 AI NEWSLETTER")
            header_lines.append("=" * 50)
        elif self.config.header_format == "markdown":
            header_lines.append("# 📰 AI NEWSLETTER")
        else:
            header_lines.append("AI NEWSLETTER")

        # Date
        if self.config.include_date:
            if self.config.week_identifier:
                header_lines.append(f"\nWeek: {self.config.week_identifier}")
            else:
                # Default: current date or week
                today = datetime.now()
                week_start = today - timedelta(days=today.weekday())
                week_end = week_start + timedelta(days=6)
                date_str = (
                    f"Week of {week_start.strftime('%B %d')} - "
                    f"{week_end.strftime('%B %d, %Y')}"
                )
                header_lines.append(f"\n{date_str}")

        header_lines.append("")
        return "\n".join(header_lines)

    def create_footer(self) -> str:
        """Create newsletter footer with source credits.

        Returns:
            Formatted footer string
        """
        footer_lines = []

        footer_lines.append("")
        footer_lines.append("=" * 50)

        if self.config.include_source_credits:
            footer_lines.append(
                "📚 Sources: Newsletter websites and YouTube channels"
            )
            footer_lines.append("💡 AI-powered content filtering and categorization")

        footer_lines.append(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        footer_lines.append("=" * 50)

        return "\n".join(footer_lines)

    def create_topic_section(
        self, topic_name: str, content_items: List[Dict[str, Any]]
    ) -> str:
        """Create formatted section for a topic with its content items.

        Args:
            topic_name: Name of the topic
            content_items: List of content items for this topic

        Returns:
            Formatted topic section as string
        """
        section_lines = []

        # Topic header
        section_lines.append(f"\n🔹 {topic_name.upper()}")
        section_lines.append("-" * 40)

        # Content items
        for i, item in enumerate(content_items, 1):
            # Get summary
            summary = item.get("summary_text", item.get("content", ""))

            # Truncate if too long
            if len(summary) > 200:
                summary = summary[:197] + "..."

            # Get source
            source = item.get("source", "Unknown")

            # Get URL
            url = item.get("content_url", item.get("url", ""))

            # Format as bullet point
            item_text = f"{i}. {summary}"
            if url:
                item_text += f"\n   📌 {source}"

            section_lines.append(item_text)
            section_lines.append("")

        return "\n".join(section_lines)

    def assemble_newsletter(
        self, content_list: List[Dict[str, Any]], week_identifier: Optional[str] = None
    ) -> Dict[str, Any]:
        """Assemble complete newsletter from content items.

        Groups content by category, creates sections, and combines into
        complete newsletter with header and footer.

        Args:
            content_list: List of processed content items
            week_identifier: Optional identifier for the week (e.g., "Week 1, 2025")

        Returns:
            Dictionary with:
                - newsletter: Complete formatted newsletter text
                - topic_sections: List of TopicSection objects
                - total_items: Total content items included
                - total_topics: Number of topics included
                - metadata: Additional metadata

        Raises:
            NewsletterAssemblyError: If content_list is invalid
        """
        if not isinstance(content_list, list):
            raise NewsletterAssemblyError("Content list must be a list")

        if not content_list:
            raise NewsletterAssemblyError("Content list cannot be empty")

        logger.info(f"Assembling newsletter from {len(content_list)} items")

        # Set week identifier if provided
        if week_identifier:
            self.config.week_identifier = week_identifier

        # Group by category
        grouped = self.group_content_by_category(content_list)

        # Filter empty categories if configured
        if self.config.skip_empty_categories:
            grouped = {k: v for k, v in grouped.items() if v}

        if not grouped:
            raise NewsletterAssemblyError("No categories with content found")

        # Build newsletter
        newsletter_parts = []

        # Header
        newsletter_parts.append(self.create_header())

        # Topic sections
        topic_sections = []
        for topic_name, items in sorted(grouped.items()):
            section_text = self.create_topic_section(topic_name, items)
            newsletter_parts.append(section_text)

            topic_sections.append(
                TopicSection(topic_name=topic_name, content_items=items)
            )

        # Footer
        newsletter_parts.append(self.create_footer())

        # Combine
        newsletter_text = "\n".join(newsletter_parts)

        logger.info(
            f"Newsletter assembled: {len(topic_sections)} topics, "
            f"{len(content_list)} items, "
            f"{len(newsletter_text)} characters"
        )

        return {
            "newsletter": newsletter_text,
            "topic_sections": topic_sections,
            "total_items": len(content_list),
            "total_topics": len(topic_sections),
            "metadata": {
                "assembled_at": datetime.now().isoformat(),
                "character_count": len(newsletter_text),
                "line_count": newsletter_text.count("\n"),
                "week_identifier": self.config.week_identifier,
            },
        }

    def assemble_newsletter_from_database(
        self, week_identifier: Optional[str] = None, status: str = "weighted"
    ) -> Dict[str, Any]:
        """Assemble newsletter from content in database.

        Retrieves processed content from database and assembles newsletter.

        Args:
            week_identifier: Optional week identifier
            status: Content status filter (default "weighted")

        Returns:
            Newsletter assembly result

        Raises:
            NewsletterAssemblyError: If database operation fails
        """
        try:
            logger.info(f"Retrieving content from database with status={status}")
            content_list = self.storage.get_processed_content(status=status)

            if not content_list:
                logger.warning("No processed content found in database")
                raise NewsletterAssemblyError(
                    f"No content with status='{status}' found in database"
                )

            result = self.assemble_newsletter(content_list, week_identifier)

            # Store in database
            try:
                self.storage.insert_delivery_history({
                    "newsletter_content": result["newsletter"],
                    "delivery_status": "assembled",
                    "assembled_at": result["metadata"]["assembled_at"],
                })
            except Exception as e:
                logger.warning(f"Failed to store newsletter in database: {str(e)}")

            logger.info(f"Newsletter assembled from database successfully")

            return result

        except Exception as e:
            logger.error(f"Failed to assemble newsletter from database: {str(e)}")
            raise NewsletterAssemblyError(
                f"Database assembly failed: {str(e)}"
            )

    def validate_newsletter_structure(
        self, newsletter_text: str
    ) -> Dict[str, Any]:
        """Validate newsletter structure and content.

        Args:
            newsletter_text: Newsletter text to validate

        Returns:
            Dictionary with validation results

        Raises:
            NewsletterAssemblyError: If newsletter is invalid
        """
        if not isinstance(newsletter_text, str):
            raise NewsletterAssemblyError("Newsletter must be a string")

        if not newsletter_text:
            raise NewsletterAssemblyError("Newsletter cannot be empty")

        issues = []
        warnings = []

        # Check character count
        char_count = len(newsletter_text)
        if char_count > 10000:
            warnings.append(f"Newsletter is large ({char_count} characters)")

        # Check for header
        if "AI NEWSLETTER" not in newsletter_text:
            warnings.append("Newsletter missing standard header")

        # Check for footer
        if "=" * 50 not in newsletter_text:
            warnings.append("Newsletter missing standard footer")

        # Check for content sections
        section_count = newsletter_text.count("🔹")
        if section_count == 0:
            issues.append("Newsletter has no topic sections")

        # Check for content items
        item_count = (
            newsletter_text.count("\n1.")
            + newsletter_text.count("\n2.")
            + newsletter_text.count("\n3.")
        )
        if item_count == 0:
            issues.append("Newsletter has no content items")

        is_valid = len(issues) == 0

        logger.info(
            f"Newsletter validation: valid={is_valid}, "
            f"issues={len(issues)}, warnings={len(warnings)}"
        )

        return {
            "is_valid": is_valid,
            "character_count": char_count,
            "section_count": section_count,
            "issues": issues,
            "warnings": warnings,
        }

    def update_config(self, config: NewsletterConfig) -> None:
        """Update newsletter configuration.

        Args:
            config: New configuration

        Raises:
            NewsletterAssemblyError: If config is invalid
        """
        if not isinstance(config, NewsletterConfig):
            raise NewsletterAssemblyError(
                "Config must be a NewsletterConfig instance"
            )

        self.config = config
        logger.info("Updated newsletter configuration")

    def get_assembly_statistics(
        self, content_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate statistics about newsletter assembly.

        Args:
            content_list: List of content items

        Returns:
            Dictionary with statistics
        """
        if not isinstance(content_list, list):
            return {
                "total_items": 0,
                "total_categories": 0,
                "avg_items_per_category": 0.0,
                "min_items_per_category": 0,
                "max_items_per_category": 0,
                "categories": {},
            }

        grouped = self.group_content_by_category(content_list)

        if not grouped:
            return {
                "total_items": len(content_list),
                "total_categories": 0,
                "avg_items_per_category": 0.0,
                "min_items_per_category": 0,
                "max_items_per_category": 0,
                "categories": {},
            }

        counts = {cat: len(items) for cat, items in grouped.items()}
        category_counts = list(counts.values())

        return {
            "total_items": len(content_list),
            "total_categories": len(grouped),
            "avg_items_per_category": sum(category_counts) / len(category_counts),
            "min_items_per_category": min(category_counts),
            "max_items_per_category": max(category_counts),
            "categories": counts,
        }
