"""
Content Deduplication Module

Identifies and removes duplicate content based on multiple similarity metrics:
- Exact title matching
- Content similarity (Jaccard index)
- Fuzzy string matching
- URL-based deduplication
Supports configurable similarity thresholds and deduplication strategies.
"""

import logging
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Tuple
from difflib import SequenceMatcher

from src.database import DatabaseStorage
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)


class ContentDuplicateError(Exception):
    """Base exception for content deduplication errors."""

    pass


class ContentDeduplicator:
    """
    Identifies and removes duplicate content from collections.

    Features:
    - Exact title matching
    - Jaccard similarity for content
    - Fuzzy string matching (SequenceMatcher)
    - URL-based deduplication
    - Configurable similarity thresholds
    - Batch deduplication with statistics
    - Database integration
    """

    # Default similarity thresholds
    DEFAULT_TITLE_THRESHOLD = 0.85  # 85% title similarity
    DEFAULT_CONTENT_THRESHOLD = 0.75  # 75% content similarity
    DEFAULT_URL_THRESHOLD = 0.90  # 90% URL similarity

    def __init__(
        self,
        storage: DatabaseStorage,
        title_threshold: float = DEFAULT_TITLE_THRESHOLD,
        content_threshold: float = DEFAULT_CONTENT_THRESHOLD,
        url_threshold: float = DEFAULT_URL_THRESHOLD,
    ):
        """
        Initialize content deduplicator.

        Args:
            storage: DatabaseStorage instance
            title_threshold: Minimum title similarity (0.0-1.0)
            content_threshold: Minimum content similarity (0.0-1.0)
            url_threshold: Minimum URL similarity (0.0-1.0)
        """
        self.storage = storage
        self.title_threshold = title_threshold
        self.content_threshold = content_threshold
        self.url_threshold = url_threshold
        self.logger = get_logger(__name__)

    def calculate_string_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings using SequenceMatcher.

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity score (0.0-1.0)
        """
        if not str1 or not str2:
            return 0.0

        # Normalize strings
        str1_norm = str1.lower().strip()
        str2_norm = str2.lower().strip()

        # Quick exact match check
        if str1_norm == str2_norm:
            return 1.0

        # Use SequenceMatcher for similarity
        matcher = SequenceMatcher(None, str1_norm, str2_norm)
        return matcher.ratio()

    def calculate_jaccard_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate Jaccard similarity between two texts (set intersection/union).

        Args:
            text1: First text
            text2: Second text

        Returns:
            Jaccard similarity score (0.0-1.0)
        """
        if not text1 or not text2:
            return 0.0

        # Split into words and create sets
        words1: Set[str] = set(text1.lower().split())
        words2: Set[str] = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        # Calculate Jaccard similarity
        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def normalize_url(self, url: Optional[str]) -> Optional[str]:
        """
        Normalize URL for comparison.

        Args:
            url: URL to normalize

        Returns:
            Normalized URL or None
        """
        if not url:
            return None

        url_norm = url.lower().strip()
        # Remove trailing slashes
        url_norm = url_norm.rstrip("/")
        # Remove query parameters for comparison
        url_norm = url_norm.split("?")[0]

        return url_norm if url_norm else None

    def is_duplicate_by_url(self, url1: Optional[str], url2: Optional[str]) -> bool:
        """
        Check if two URLs represent the same content.

        Args:
            url1: First URL
            url2: Second URL

        Returns:
            True if URLs match above threshold
        """
        norm_url1 = self.normalize_url(url1)
        norm_url2 = self.normalize_url(url2)

        if not norm_url1 or not norm_url2:
            return False

        similarity = self.calculate_string_similarity(norm_url1, norm_url2)
        return similarity >= self.url_threshold

    def is_duplicate(
        self, content1: Dict[str, Any], content2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Determine if two content items are duplicates.

        Args:
            content1: First content item
            content2: Second content item

        Returns:
            {
                'is_duplicate': bool,
                'similarity_score': float,
                'methods': List[str],  # Which methods detected duplicate
                'details': {...}
            }
        """
        if not isinstance(content1, dict) or not isinstance(content2, dict):
            return {
                "is_duplicate": False,
                "similarity_score": 0.0,
                "methods": [],
                "details": {},
            }

        # Don't compare content with itself
        if content1.get("id") and content1.get("id") == content2.get("id"):
            return {
                "is_duplicate": False,
                "similarity_score": 1.0,
                "methods": ["same_id"],
                "details": {"reason": "Same content ID"},
            }

        methods = []
        details = {}

        # Check 1: Exact title match
        title1 = content1.get("title", "")
        title2 = content2.get("title", "")
        title_sim = self.calculate_string_similarity(title1, title2)

        if title_sim >= 1.0:
            methods.append("exact_title")
            details["title_similarity"] = 1.0

        # Check 2: URL-based deduplication
        url1 = content1.get("source_url") or content1.get("url")
        url2 = content2.get("source_url") or content2.get("url")

        if self.is_duplicate_by_url(url1, url2):
            methods.append("same_url")
            details["url"] = self.normalize_url(url1)

        # Check 3: Title similarity
        if title_sim >= self.title_threshold and title_sim < 1.0:
            methods.append("title_similarity")
            details["title_similarity"] = round(title_sim, 3)

        # Check 4: Content similarity
        text1 = content1.get("content", "")
        text2 = content2.get("content", "")

        # Use Jaccard for content similarity
        content_sim = self.calculate_jaccard_similarity(text1, text2)

        if content_sim >= self.content_threshold:
            methods.append("content_similarity")
            details["content_similarity"] = round(content_sim, 3)

        # Overall similarity score (average of detected similarities)
        similarities = []
        if title_sim >= self.title_threshold:
            similarities.append(title_sim)
        if content_sim >= self.content_threshold:
            similarities.append(content_sim)

        overall_similarity = (
            sum(similarities) / len(similarities) if similarities else 0.0
        )

        is_duplicate = len(methods) > 0

        return {
            "is_duplicate": is_duplicate,
            "similarity_score": round(overall_similarity, 3),
            "methods": methods,
            "details": details,
        }

    def deduplicate_content_list(
        self, content_list: List[Dict[str, Any]], keep_first: bool = True
    ) -> Dict[str, Any]:
        """
        Deduplicate a list of content items.

        Args:
            content_list: List of content dictionaries
            keep_first: If True, keep first occurrence; if False, keep last

        Returns:
            {
                'total': int,
                'duplicates_found': int,
                'duplicates_removed': int,
                'unique_content': List[Dict],
                'removed_ids': List[int],
                'duplicate_groups': List[List[int]],
                'statistics': {...}
            }
        """
        if not content_list:
            return {
                "total": 0,
                "duplicates_found": 0,
                "duplicates_removed": 0,
                "unique_content": [],
                "removed_ids": [],
                "duplicate_groups": [],
                "statistics": {"deduplication_ratio": 0.0},
            }

        seen_ids: Set[int] = set()
        duplicate_groups: List[List[int]] = []
        unique_content = []
        removed_ids = []

        for i, content1 in enumerate(content_list):
            content_id = content1.get("id")

            # Skip if already marked as duplicate
            if content_id and content_id in seen_ids:
                continue

            # Check against all remaining items
            duplicates = [content_id] if content_id else []

            for j in range(i + 1, len(content_list)):
                content2 = content_list[j]
                content2_id = content2.get("id")

                # Skip if already marked as duplicate
                if content2_id and content2_id in seen_ids:
                    continue

                # Check if duplicate
                dup_result = self.is_duplicate(content1, content2)

                if dup_result["is_duplicate"]:
                    duplicates.append(content2_id)
                    if content2_id:
                        seen_ids.add(content2_id)

            # Add current item as unique
            unique_content.append(content1)
            if content_id:
                seen_ids.add(content_id)

            # Track duplicate group if found
            if len(duplicates) > 1:
                duplicate_groups.append(duplicates)
                removed_ids.extend(duplicates[1:])

        try:
            dedup_ratio = (len(removed_ids) / len(content_list)) if content_list else 0.0
        except ZeroDivisionError:
            dedup_ratio = 0.0

        self.logger.info(
            f"Deduplication: {len(unique_content)} unique from {len(content_list)} total "
            f"({len(removed_ids)} removed, {len(duplicate_groups)} duplicate groups)"
        )

        return {
            "total": len(content_list),
            "duplicates_found": len(duplicate_groups),
            "duplicates_removed": len(removed_ids),
            "unique_content": unique_content,
            "removed_ids": removed_ids,
            "duplicate_groups": duplicate_groups,
            "statistics": {
                "deduplication_ratio": round(dedup_ratio, 3),
                "unique_count": len(unique_content),
                "duplicate_groups_count": len(duplicate_groups),
            },
        }

    def deduplicate_database_content(
        self, source_type: Optional[str] = None, status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Deduplicate content from database.

        Args:
            source_type: Optional source type filter
            status: Optional status filter

        Returns:
            {
                'total': int,
                'duplicates_removed': int,
                'removed_ids': List[int],
                'error': str (if any)
            }
        """
        try:
            # Get content from database
            content_list = self.storage.get_processed_content(
                source_type=source_type, status=status
            )

            if not content_list:
                self.logger.debug("No content to deduplicate in database")
                return {
                    "total": 0,
                    "duplicates_removed": 0,
                    "removed_ids": [],
                }

            # Deduplicate
            result = self.deduplicate_content_list(content_list)

            # Mark duplicates in database
            for dup_id in result["removed_ids"]:
                try:
                    self.storage.update_content_status(
                        content_id=dup_id,
                        status="duplicate",
                        metadata={"deduplication_info": "Marked as duplicate"},
                    )
                except Exception as e:
                    self.logger.warning(f"Error marking duplicate {dup_id}: {e}")

            self.logger.info(
                f"Database deduplication: Removed {result['duplicates_removed']} duplicates"
            )

            return {
                "total": result["total"],
                "duplicates_removed": result["duplicates_removed"],
                "removed_ids": result["removed_ids"],
            }

        except Exception as e:
            self.logger.error(f"Error deduplicating database content: {e}", exc_info=True)
            return {
                "total": 0,
                "duplicates_removed": 0,
                "removed_ids": [],
                "error": str(e),
            }

    def update_similarity_thresholds(
        self,
        title_threshold: Optional[float] = None,
        content_threshold: Optional[float] = None,
        url_threshold: Optional[float] = None,
    ) -> None:
        """
        Update similarity thresholds.

        Args:
            title_threshold: New title threshold (0.0-1.0)
            content_threshold: New content threshold (0.0-1.0)
            url_threshold: New URL threshold (0.0-1.0)

        Raises:
            ContentDuplicateError: If thresholds are invalid
        """
        if title_threshold is not None:
            if not (0.0 <= title_threshold <= 1.0):
                raise ContentDuplicateError("Title threshold must be between 0.0 and 1.0")
            self.title_threshold = title_threshold

        if content_threshold is not None:
            if not (0.0 <= content_threshold <= 1.0):
                raise ContentDuplicateError("Content threshold must be between 0.0 and 1.0")
            self.content_threshold = content_threshold

        if url_threshold is not None:
            if not (0.0 <= url_threshold <= 1.0):
                raise ContentDuplicateError("URL threshold must be between 0.0 and 1.0")
            self.url_threshold = url_threshold

        self.logger.info(
            f"Updated thresholds - Title: {self.title_threshold}, "
            f"Content: {self.content_threshold}, URL: {self.url_threshold}"
        )

    def find_duplicate_pairs(
        self, content_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Find all duplicate pairs in content list.

        Args:
            content_list: List of content items

        Returns:
            {
                'total': int,
                'pairs_found': int,
                'duplicate_pairs': List[Tuple[int, int]],
                'pair_details': List[Dict]
            }
        """
        if not content_list:
            return {
                "total": 0,
                "pairs_found": 0,
                "duplicate_pairs": [],
                "pair_details": [],
            }

        duplicate_pairs = []
        pair_details = []

        for i in range(len(content_list)):
            for j in range(i + 1, len(content_list)):
                content1 = content_list[i]
                content2 = content_list[j]

                dup_result = self.is_duplicate(content1, content2)

                if dup_result["is_duplicate"]:
                    id1 = content1.get("id")
                    id2 = content2.get("id")
                    duplicate_pairs.append((id1, id2))

                    pair_details.append(
                        {
                            "id1": id1,
                            "id2": id2,
                            "title1": content1.get("title", ""),
                            "title2": content2.get("title", ""),
                            "similarity_score": dup_result["similarity_score"],
                            "methods": dup_result["methods"],
                        }
                    )

        return {
            "total": len(content_list),
            "pairs_found": len(duplicate_pairs),
            "duplicate_pairs": duplicate_pairs,
            "pair_details": pair_details,
        }

    def get_deduplication_statistics(self, content_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get deduplication statistics without removing duplicates.

        Args:
            content_list: List of content items

        Returns:
            {
                'total': int,
                'estimated_duplicates': int,
                'estimated_ratio': float,
                'duplicate_pairs': int,
                'by_similarity_range': {...}
            }
        """
        if not content_list:
            return {
                "total": 0,
                "estimated_duplicates": 0,
                "estimated_ratio": 0.0,
                "duplicate_pairs": 0,
                "by_similarity_range": {},
            }

        similarities = []
        duplicate_pairs = 0

        for i in range(len(content_list)):
            for j in range(i + 1, len(content_list)):
                dup_result = self.is_duplicate(content_list[i], content_list[j])
                similarities.append(dup_result["similarity_score"])

                if dup_result["is_duplicate"]:
                    duplicate_pairs += 1

        # Analyze similarity distribution
        ranges = {"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}

        for sim in similarities:
            if sim < 0.2:
                ranges["0.0-0.2"] += 1
            elif sim < 0.4:
                ranges["0.2-0.4"] += 1
            elif sim < 0.6:
                ranges["0.4-0.6"] += 1
            elif sim < 0.8:
                ranges["0.6-0.8"] += 1
            else:
                ranges["0.8-1.0"] += 1

        avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
        estimated_duplicates = duplicate_pairs

        return {
            "total": len(content_list),
            "estimated_duplicates": estimated_duplicates,
            "estimated_ratio": round(estimated_duplicates / len(content_list), 3)
            if content_list
            else 0.0,
            "duplicate_pairs": duplicate_pairs,
            "by_similarity_range": ranges,
            "average_similarity": round(avg_similarity, 3),
        }
