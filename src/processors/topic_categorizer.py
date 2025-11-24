"""
Topic Categorization Module

Automatically categorizes content into predefined topics using keyword-based analysis.
Supports multi-label categorization where content can belong to multiple topics.
Provides confidence scores and detailed category reasoning.
"""

import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass

from src.database import DatabaseStorage
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)


class TopicCategorizationError(Exception):
    """Base exception for topic categorization errors."""

    pass


@dataclass
class Topic:
    """Represents a topic category with keywords."""

    id: str
    name: str
    description: str
    keywords: Dict[str, float]  # keyword -> weight
    min_confidence: float = 0.5


class TopicCategorizer:
    """
    Categorizes content into predefined topics.

    Features:
    - Keyword-based multi-label categorization
    - Configurable topic definitions
    - Confidence scoring
    - Batch categorization
    - Database integration
    """

    # Default topics for AI Newsletter
    DEFAULT_TOPICS = {
        "ai": Topic(
            id="ai",
            name="Artificial Intelligence",
            description="AI models, techniques, and general AI advances",
            keywords={
                "ai": 2.0,
                "artificial intelligence": 2.0,
                "machine learning": 1.8,
                "neural network": 1.7,
                "deep learning": 1.7,
                "llm": 1.9,
                "language model": 1.8,
                "transformer": 1.6,
                "model": 1.2,
                "algorithm": 1.1,
                "training": 1.0,
                "inference": 1.0,
            },
        ),
        "llm": Topic(
            id="llm",
            name="Large Language Models",
            description="LLMs, chatbots, prompt engineering, and language model applications",
            keywords={
                "llm": 2.0,
                "language model": 1.9,
                "chatbot": 1.8,
                "gpt": 1.9,
                "chat": 1.3,
                "prompt": 1.5,
                "token": 1.1,
                "fine-tune": 1.6,
                "instruction": 1.2,
                "embedding": 1.4,
            },
        ),
        "cloud": Topic(
            id="cloud",
            name="Cloud Computing",
            description="Cloud services, AWS, Azure, GCP, and infrastructure",
            keywords={
                "cloud": 1.8,
                "aws": 1.9,
                "azure": 1.9,
                "gcp": 1.9,
                "kubernetes": 1.7,
                "docker": 1.6,
                "serverless": 1.6,
                "container": 1.5,
                "infra": 1.3,
                "devops": 1.4,
            },
        ),
        "security": Topic(
            id="security",
            name="Security & Privacy",
            description="Cybersecurity, privacy, encryption, and threat protection",
            keywords={
                "security": 1.8,
                "privacy": 1.7,
                "encryption": 1.7,
                "threat": 1.6,
                "vulnerability": 1.7,
                "attack": 1.6,
                "hack": 1.5,
                "breach": 1.8,
                "auth": 1.4,
                "firewall": 1.5,
            },
        ),
        "data": Topic(
            id="data",
            name="Data & Analytics",
            description="Big data, data science, analytics, and data engineering",
            keywords={
                "data": 1.5,
                "analytics": 1.6,
                "database": 1.5,
                "sql": 1.4,
                "warehouse": 1.5,
                "bigquery": 1.6,
                "analytics": 1.6,
                "dbt": 1.4,
                "etl": 1.4,
                "pipeline": 1.3,
            },
        ),
        "web": Topic(
            id="web",
            name="Web & Frontend",
            description="Web technologies, frameworks, and frontend development",
            keywords={
                "web": 1.4,
                "frontend": 1.5,
                "react": 1.6,
                "javascript": 1.4,
                "html": 1.2,
                "css": 1.2,
                "typescript": 1.4,
                "vue": 1.5,
                "angular": 1.5,
                "framework": 1.2,
            },
        ),
        "mobile": Topic(
            id="mobile",
            name="Mobile Development",
            description="Mobile apps, iOS, Android, and cross-platform development",
            keywords={
                "mobile": 1.6,
                "ios": 1.7,
                "android": 1.7,
                "app": 1.3,
                "swift": 1.5,
                "flutter": 1.6,
                "react native": 1.6,
                "apk": 1.4,
            },
        ),
        "devops": Topic(
            id="devops",
            name="DevOps & Deployment",
            description="DevOps, CI/CD, deployment, and infrastructure automation",
            keywords={
                "devops": 1.8,
                "cicd": 1.7,
                "ci/cd": 1.7,
                "deployment": 1.6,
                "jenkins": 1.5,
                "gitlab": 1.4,
                "github": 1.3,
                "monitoring": 1.5,
                "observability": 1.6,
                "logging": 1.3,
            },
        ),
        "startup": Topic(
            id="startup",
            name="Startups & Business",
            description="Startup funding, business news, and company announcements",
            keywords={
                "startup": 1.8,
                "funding": 1.7,
                "investment": 1.6,
                "series": 1.6,
                "valuation": 1.5,
                "acquisition": 1.7,
                "ipo": 1.6,
                "business": 1.2,
                "company": 1.1,
            },
        ),
    }

    def __init__(
        self,
        storage: DatabaseStorage,
        topics: Optional[Dict[str, Topic]] = None,
        min_confidence: float = 0.5,
    ):
        """
        Initialize topic categorizer.

        Args:
            storage: DatabaseStorage instance
            topics: Custom topics dict (uses DEFAULT_TOPICS if None)
            min_confidence: Minimum confidence to assign category
        """
        self.storage = storage
        self.topics = topics or self.DEFAULT_TOPICS
        self.min_confidence = min_confidence
        self.logger = get_logger(__name__)

    def categorize_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Categorize a single content item.

        Args:
            content: Content dictionary with title and content

        Returns:
            {
                'categories': List[str],  # Assigned category IDs
                'confidence': Dict[str, float],  # Category -> confidence score
                'reasons': Dict[str, List[str]],  # Category -> matching keywords
                'primary_category': Optional[str],  # Highest confidence category
                'primary_confidence': float
            }
        """
        if not isinstance(content, dict):
            self.logger.warning(f"Invalid content type: {type(content)}")
            return {
                "categories": [],
                "confidence": {},
                "reasons": {},
                "primary_category": None,
                "primary_confidence": 0.0,
            }

        title = (content.get("title", "") or "").lower()
        text = (content.get("content", "") or "").lower()
        combined = f"{title} {text}"

        # Categorize against each topic
        category_scores = {}
        category_reasons = {}

        for topic_id, topic in self.topics.items():
            score = 0.0
            matching_keywords = []

            # Check each keyword in topic
            for keyword, weight in topic.keywords.items():
                if keyword in combined:
                    count = combined.count(keyword)
                    score += count * weight * 0.1  # Scale contribution
                    matching_keywords.append(f"{keyword} ({count}x)")

            # Normalize score to 0.0-1.0
            if matching_keywords:
                score = min(score, 1.0)
                category_scores[topic_id] = score
                category_reasons[topic_id] = matching_keywords

        # Filter by confidence threshold
        assigned_categories = [
            cat_id
            for cat_id, score in category_scores.items()
            if score >= self.min_confidence
        ]

        # Find primary category (highest confidence)
        primary_category = None
        primary_confidence = 0.0

        if category_scores:
            primary_category = max(category_scores, key=category_scores.get)
            primary_confidence = category_scores[primary_category]

        self.logger.debug(
            f"Categorized content: {assigned_categories} "
            f"(primary: {primary_category} at {primary_confidence:.2f})"
        )

        return {
            "categories": assigned_categories,
            "confidence": category_scores,
            "reasons": category_reasons,
            "primary_category": primary_category,
            "primary_confidence": primary_confidence,
        }

    def categorize_content_list(
        self, content_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Categorize a list of content items.

        Args:
            content_list: List of content dictionaries

        Returns:
            {
                'total': int,
                'categorized': int,
                'content_with_categories': List[Dict],
                'category_distribution': Dict[str, int],
                'statistics': {...}
            }
        """
        if not content_list:
            return {
                "total": 0,
                "categorized": 0,
                "content_with_categories": [],
                "category_distribution": {},
                "statistics": {
                    "avg_categories_per_item": 0.0,
                    "items_with_primary": 0,
                    "items_with_multiple": 0,
                },
            }

        categorized_content = []
        category_counts = {topic_id: 0 for topic_id in self.topics.keys()}
        total_categories_assigned = 0
        items_with_primary = 0
        items_with_multiple = 0

        for content in content_list:
            try:
                result = self.categorize_content(content)

                # Add categories to content
                content_with_cat = content.copy()
                content_with_cat["categories"] = result["categories"]
                content_with_cat["primary_category"] = result["primary_category"]
                content_with_cat["primary_confidence"] = result[
                    "primary_confidence"
                ]
                content_with_cat["category_confidence"] = result["confidence"]

                categorized_content.append(content_with_cat)

                # Update statistics
                num_categories = len(result["categories"])
                total_categories_assigned += num_categories

                if result["primary_category"]:
                    items_with_primary += 1
                    category_counts[result["primary_category"]] += 1

                if num_categories > 1:
                    items_with_multiple += 1

            except Exception as e:
                self.logger.warning(f"Error categorizing content: {e}")
                continue

        avg_categories = (
            total_categories_assigned / len(categorized_content)
            if categorized_content
            else 0.0
        )

        # Remove zero counts from distribution
        category_distribution = {k: v for k, v in category_counts.items() if v > 0}

        self.logger.info(
            f"Categorized {len(categorized_content)} items into "
            f"{len(category_distribution)} categories"
        )

        return {
            "total": len(content_list),
            "categorized": len(categorized_content),
            "content_with_categories": categorized_content,
            "category_distribution": category_distribution,
            "statistics": {
                "avg_categories_per_item": round(avg_categories, 2),
                "items_with_primary": items_with_primary,
                "items_with_multiple": items_with_multiple,
            },
        }

    def categorize_database_content(self, source_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Categorize content from database.

        Args:
            source_type: Optional source type filter

        Returns:
            {
                'total': int,
                'categorized': int,
                'category_distribution': Dict[str, int],
                'error': str (if any)
            }
        """
        try:
            # Get unprocessed content
            content_list = self.storage.get_processed_content(source_type=source_type)

            if not content_list:
                self.logger.debug("No content to categorize in database")
                return {
                    "total": 0,
                    "categorized": 0,
                    "category_distribution": {},
                }

            # Categorize
            result = self.categorize_content_list(content_list)

            # Update database with categories
            for content in result["content_with_categories"]:
                try:
                    content_id = content.get("id")
                    if content_id:
                        self.storage.update_content_status(
                            content_id=content_id,
                            status="categorized",
                            metadata={
                                "categories": content.get("categories", []),
                                "primary_category": content.get("primary_category"),
                                "primary_confidence": content.get("primary_confidence", 0.0),
                            },
                        )
                except Exception as e:
                    self.logger.warning(f"Error updating content {content_id}: {e}")

            self.logger.info(
                f"Database categorization: {result['categorized']} items categorized"
            )

            return {
                "total": result["total"],
                "categorized": result["categorized"],
                "category_distribution": result["category_distribution"],
            }

        except Exception as e:
            self.logger.error(f"Error categorizing database content: {e}", exc_info=True)
            return {
                "total": 0,
                "categorized": 0,
                "category_distribution": {},
                "error": str(e),
            }

    def update_min_confidence(self, min_confidence: float) -> None:
        """
        Update minimum confidence threshold.

        Args:
            min_confidence: New minimum confidence (0.0-1.0)

        Raises:
            TopicCategorizationError: If confidence is invalid
        """
        if not (0.0 <= min_confidence <= 1.0):
            raise TopicCategorizationError(
                "Minimum confidence must be between 0.0 and 1.0"
            )

        old_confidence = self.min_confidence
        self.min_confidence = min_confidence
        self.logger.info(
            f"Updated min confidence from {old_confidence} to {min_confidence}"
        )

    def add_custom_topic(
        self, topic: Topic
    ) -> None:
        """
        Add a custom topic.

        Args:
            topic: Topic object to add

        Raises:
            TopicCategorizationError: If topic ID already exists
        """
        if topic.id in self.topics:
            raise TopicCategorizationError(f"Topic '{topic.id}' already exists")

        self.topics[topic.id] = topic
        self.logger.info(f"Added custom topic: {topic.id} - {topic.name}")

    def remove_topic(self, topic_id: str) -> None:
        """
        Remove a topic.

        Args:
            topic_id: Topic ID to remove

        Raises:
            TopicCategorizationError: If topic doesn't exist
        """
        if topic_id not in self.topics:
            raise TopicCategorizationError(f"Topic '{topic_id}' not found")

        del self.topics[topic_id]
        self.logger.info(f"Removed topic: {topic_id}")

    def get_topic_info(self, topic_id: str) -> Optional[Topic]:
        """Get information about a topic."""
        return self.topics.get(topic_id)

    def list_topics(self) -> List[Dict[str, Any]]:
        """List all available topics."""
        return [
            {
                "id": topic.id,
                "name": topic.name,
                "description": topic.description,
                "keyword_count": len(topic.keywords),
            }
            for topic in self.topics.values()
        ]

    def get_categorization_statistics(
        self, content_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get categorization statistics without storing results.

        Args:
            content_list: List of content items

        Returns:
            {
                'total': int,
                'by_topic': Dict[str, int],
                'coverage': Dict[str, float],
                'avg_categories_per_item': float
            }
        """
        if not content_list:
            return {
                "total": 0,
                "by_topic": {},
                "coverage": {},
                "avg_categories_per_item": 0.0,
            }

        topic_counts = {topic_id: 0 for topic_id in self.topics.keys()}
        total_categories = 0

        for content in content_list:
            result = self.categorize_content(content)
            for cat_id in result["categories"]:
                topic_counts[cat_id] += 1
                total_categories += 1

        # Calculate coverage (% of items with at least one category)
        items_with_categories = sum(1 for content in content_list
                                     if self.categorize_content(content)["categories"])
        coverage_pct = (items_with_categories / len(content_list) * 100
                       if content_list else 0.0)

        # Remove zero counts
        topic_counts = {k: v for k, v in topic_counts.items() if v > 0}

        avg_per_item = (total_categories / len(content_list)
                       if content_list else 0.0)

        return {
            "total": len(content_list),
            "by_topic": topic_counts,
            "coverage": {
                "items_with_categories": items_with_categories,
                "percentage": round(coverage_pct, 1),
            },
            "avg_categories_per_item": round(avg_per_item, 2),
        }

    def find_uncategorized_content(
        self, content_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Find content that doesn't match any category.

        Args:
            content_list: List of content items

        Returns:
            List of uncategorized content items
        """
        uncategorized = []

        for content in content_list:
            result = self.categorize_content(content)
            if not result["categories"]:
                uncategorized.append(content)

        self.logger.info(f"Found {len(uncategorized)} uncategorized items")

        return uncategorized
