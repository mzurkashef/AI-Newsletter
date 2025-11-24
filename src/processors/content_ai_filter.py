"""
AI Content Filtering Module

Identifies and filters major announcements from collected content.
Uses rule-based detection combined with keyword/entity analysis.
Assigns importance scores to content for downstream processing.
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any

from src.database import DatabaseStorage
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)


class ContentAIFilterError(Exception):
    """Base exception for content filtering errors."""

    pass


class ContentAIFilter:
    """
    Filters content to identify major announcements.

    Features:
    - Rule-based announcement detection
    - Keyword and entity extraction
    - Importance score calculation (0.0-1.0)
    - Batch filtering with statistics
    - Comprehensive logging
    """

    # Keywords that indicate major announcements
    MAJOR_KEYWORDS = {
        "announce": 2.0,
        "release": 1.8,
        "launch": 1.8,
        "breakthrough": 2.0,
        "major": 1.5,
        "new": 1.2,
        "introduce": 1.5,
        "unveil": 1.8,
        "acquire": 1.8,
        "acquisition": 1.8,
        "partnership": 1.6,
        "collaborate": 1.3,
        "funding": 1.8,
        "series": 1.7,
        "investment": 1.6,
        "first": 1.3,
        "record": 1.4,
        "milestone": 1.6,
        "achievement": 1.4,
        "innovation": 1.5,
        "revolutionary": 1.9,
        "game-changing": 1.9,
        "breakthrough": 2.0,
        "discovery": 1.7,
        "research": 1.2,
        "study": 1.0,
    }

    # Keywords indicating noise or low-quality content
    NOISE_KEYWORDS = {
        "opinion": 0.5,
        "rumor": 0.3,
        "speculation": 0.3,
        "alleged": 0.4,
        "claim": 0.5,
        "report": 0.6,
        "could": 0.7,
        "may": 0.7,
        "might": 0.7,
        "possible": 0.7,
        "subscribe": 0.2,
        "click here": 0.2,
        "read more": 0.3,
        "sponsored": 0.1,
        "advertisement": 0.1,
    }

    # Company/entity patterns
    ENTITY_PATTERNS = {
        r"\b(?:google|microsoft|apple|amazon|meta|openai|anthropic|tesla|ibm)\b": 1.5,
        r"\b[a-z][a-z]+\s+(?:inc|corp|ltd|llc|ai)\b": 0.8,
        r"\$\d+(?:\s*(?:million|billion|trillion|m|b|t))?": 1.0,
        r"\d{1,3}(?:,\d{3})*(?:\.\d+)?%": 0.7,
    }

    def __init__(
        self,
        storage: DatabaseStorage,
        min_importance_threshold: float = 0.5,
    ):
        """
        Initialize content AI filter.

        Args:
            storage: DatabaseStorage instance
            min_importance_threshold: Minimum score to include (default: 0.5)
        """
        self.storage = storage
        self.min_importance_threshold = min_importance_threshold
        self.logger = get_logger(__name__)

    def calculate_importance_score(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate importance score for content.

        Args:
            content: Content dictionary with title and text

        Returns:
            {
                'score': float (0.0-1.0),
                'major_keywords': List[str],
                'entities': List[str],
                'reasons': List[str]
            }
        """
        if not isinstance(content, dict):
            self.logger.warning(f"Invalid content type: {type(content)}")
            return {"score": 0.0, "major_keywords": [], "entities": [], "reasons": []}

        title = content.get("title", "") or ""
        text = content.get("content", "") or ""

        # Handle None values
        try:
            title = str(title).lower()
            text = str(text).lower()
        except (TypeError, AttributeError):
            self.logger.warning("Error converting title/content to string")
            return {"score": 0.0, "major_keywords": [], "entities": [], "reasons": []}

        combined = f"{title} {text}"

        # Initialize scoring
        score = 0.5  # Base score
        reasons = []
        major_keywords = []
        entities = []

        # Check content length
        content_length = len(text.split())
        if content_length < 50:
            score -= 0.2
            reasons.append("Short content (likely summary or noise)")
        elif content_length > 5000:
            score += 0.1
            reasons.append("Substantive content (long article)")

        # Check for major keywords
        for keyword, weight in self.MAJOR_KEYWORDS.items():
            if keyword in combined:
                count = combined.count(keyword)
                score += min(count * 0.1 * weight, 0.3)
                major_keywords.append(keyword)
                reasons.append(f"Contains '{keyword}' ({weight}x weight)")

        # Check for noise keywords
        for keyword, weight in self.NOISE_KEYWORDS.items():
            if keyword in combined:
                count = combined.count(keyword)
                score -= count * 0.05 * weight
                reasons.append(f"Contains noise keyword '{keyword}' ({weight}x penalty)")

        # Check for entities
        for pattern, weight in self.ENTITY_PATTERNS.items():
            matches = re.findall(pattern, combined)
            if matches:
                entities.extend(matches)
                score += min(len(matches) * 0.05 * weight, 0.2)
                reasons.append(f"Found {len(matches)} named entities")

        # Check publication freshness (prefer recent content)
        if "published_at" in content:
            pub_date = content.get("published_at")
            if isinstance(pub_date, str):
                try:
                    pub_dt = datetime.fromisoformat(pub_date)
                    age_hours = (datetime.utcnow() - pub_dt).total_seconds() / 3600
                    if age_hours < 24:
                        score += 0.1
                        reasons.append("Very recent content (+0.1)")
                    elif age_hours < 72:
                        score += 0.05
                        reasons.append("Recent content (+0.05)")
                except (ValueError, TypeError):
                    pass

        # Normalize score to 0.0-1.0
        score = max(0.0, min(1.0, score))

        return {
            "score": round(score, 2),
            "major_keywords": list(set(major_keywords)),
            "entities": list(set(entities)),
            "reasons": reasons,
        }

    def is_major_announcement(self, content: Dict[str, Any]) -> bool:
        """
        Check if content is a major announcement.

        Args:
            content: Content dictionary

        Returns:
            True if score >= threshold, False otherwise
        """
        result = self.calculate_importance_score(content)
        return result["score"] >= self.min_importance_threshold

    def filter_content_list(
        self, content_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Filter a list of content items.

        Args:
            content_list: List of content dictionaries

        Returns:
            {
                'total': int,
                'filtered': int,
                'filtered_content': List[Dict],
                'filtered_out': int,
                'average_score': float,
                'statistics': {...}
            }
        """
        if not content_list:
            return {
                "total": 0,
                "filtered": 0,
                "filtered_content": [],
                "filtered_out": 0,
                "average_score": 0.0,
                "statistics": {
                    "min_score": None,
                    "max_score": None,
                    "median_score": None,
                },
            }

        filtered = []
        scores = []

        for content in content_list:
            try:
                scoring = self.calculate_importance_score(content)
                score = scoring["score"]
                scores.append(score)

                # Add scoring to content
                content_with_score = content.copy()
                content_with_score["importance_score"] = score
                content_with_score["major_keywords"] = scoring["major_keywords"]
                content_with_score["entities"] = scoring["entities"]

                if score >= self.min_importance_threshold:
                    filtered.append(content_with_score)

            except Exception as e:
                self.logger.warning(f"Error filtering content: {e}")
                continue

        # Calculate statistics
        if scores:
            scores.sort()
            median = scores[len(scores) // 2]
            avg = sum(scores) / len(scores)
        else:
            median = None
            avg = 0.0

        self.logger.info(
            f"Content filtering: {len(filtered)} major announcements from {len(content_list)} total "
            f"(avg score: {avg:.2f})"
        )

        return {
            "total": len(content_list),
            "filtered": len(filtered),
            "filtered_content": filtered,
            "filtered_out": len(content_list) - len(filtered),
            "average_score": round(avg, 2),
            "statistics": {
                "min_score": round(min(scores), 2) if scores else None,
                "max_score": round(max(scores), 2) if scores else None,
                "median_score": round(median, 2) if scores else None,
            },
        }

    def filter_database_content(self, source_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Filter unprocessed content from database.

        Args:
            source_type: Optional source type to filter

        Returns:
            {
                'total': int,
                'filtered': int,
                'content_ids': List[int],
                'average_score': float,
                'error': str (if any)
            }
        """
        try:
            # Get unprocessed content
            unprocessed = self.storage.get_unprocessed_content()
            self.logger.debug(f"Found {len(unprocessed)} unprocessed items")

            # Filter by source type if specified
            if source_type:
                unprocessed = [
                    c for c in unprocessed if c.get("source_type") == source_type
                ]
                self.logger.debug(f"Filtered to {len(unprocessed)} items of type {source_type}")

            # Filter content
            result = self.filter_content_list(unprocessed)

            # Extract IDs from filtered content
            content_ids = [
                c.get("id") for c in result["filtered_content"] if c.get("id")
            ]

            self.logger.info(
                f"Database filtering: {result['filtered']} major announcements from {result['total']} total"
            )

            return {
                "total": result["total"],
                "filtered": result["filtered"],
                "content_ids": content_ids,
                "average_score": result["average_score"],
            }

        except Exception as e:
            self.logger.error(f"Error filtering database content: {e}", exc_info=True)
            return {
                "total": 0,
                "filtered": 0,
                "content_ids": [],
                "average_score": 0.0,
                "error": str(e),
            }

    def update_importance_threshold(self, threshold: float) -> None:
        """
        Update the importance threshold.

        Args:
            threshold: New threshold (0.0-1.0)

        Raises:
            ContentAIFilterError: If threshold is invalid
        """
        if not (0.0 <= threshold <= 1.0):
            raise ContentAIFilterError("Threshold must be between 0.0 and 1.0")

        old_threshold = self.min_importance_threshold
        self.min_importance_threshold = threshold
        self.logger.info(f"Updated importance threshold from {old_threshold} to {threshold}")

    def get_filter_statistics(self, content_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get filtering statistics without actually filtering.

        Args:
            content_list: List of content to analyze

        Returns:
            {
                'total': int,
                'score_distribution': {score_range: count},
                'avg_score': float,
                'top_keywords': List[str],
                'content_with_scores': List[Dict]
            }
        """
        if not content_list:
            return {
                "total": 0,
                "score_distribution": {},
                "avg_score": 0.0,
                "top_keywords": [],
                "content_with_scores": [],
            }

        scores = []
        keywords_count = {}
        content_with_scores = []

        for content in content_list:
            try:
                scoring = self.calculate_importance_score(content)
                score = scoring["score"]
                scores.append(score)

                # Track keywords
                for keyword in scoring["major_keywords"]:
                    keywords_count[keyword] = keywords_count.get(keyword, 0) + 1

                # Store with score
                content_copy = content.copy()
                content_copy["importance_score"] = score
                content_with_scores.append(content_copy)

            except Exception as e:
                self.logger.warning(f"Error analyzing content: {e}")
                continue

        # Calculate distribution
        distribution = {}
        for score in scores:
            bucket = f"{int(score * 10) * 0.1:.1f}"
            distribution[bucket] = distribution.get(bucket, 0) + 1

        # Get top keywords
        top_keywords = sorted(
            keywords_count.items(), key=lambda x: x[1], reverse=True
        )[:10]

        return {
            "total": len(content_list),
            "score_distribution": distribution,
            "avg_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
            "top_keywords": [kw for kw, _ in top_keywords],
            "content_with_scores": content_with_scores,
        }
