"""Source weighting system for balanced content coverage in AI Newsletter."""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from src.database.storage import DatabaseStorage
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)


class SourceWeightingError(Exception):
    """Exception raised for source weighting errors."""

    pass


@dataclass
class SourceWeight:
    """Weight information for a source."""

    source: str
    content_count: int = 0
    weight: float = 1.0
    weighted_count: float = 0.0
    boost: float = 1.0


class SourceWeightingSystem:
    """Balance content coverage across sources using inverse weighting.

    Implements a system to ensure no single source dominates the newsletter
    by applying weights inversely proportional to the number of items from
    that source. This ensures diverse perspectives and prevents bias toward
    prolific sources.
    """

    def __init__(
        self,
        storage: DatabaseStorage,
        target_items_per_source: int = 5,
        min_weight: float = 0.1,
        max_weight: float = 5.0,
    ) -> None:
        """Initialize source weighting system.

        Args:
            storage: DatabaseStorage instance
            target_items_per_source: Target number of items per source (5)
            min_weight: Minimum weight for any source (0.1)
            max_weight: Maximum weight for any source (5.0)

        Raises:
            SourceWeightingError: If parameters are invalid
        """
        if not isinstance(storage, DatabaseStorage):
            raise SourceWeightingError("Invalid storage instance")

        if target_items_per_source <= 0:
            raise SourceWeightingError("target_items_per_source must be > 0")

        if min_weight <= 0:
            raise SourceWeightingError("min_weight must be > 0")

        if max_weight <= 0:
            raise SourceWeightingError("max_weight must be > 0")

        if min_weight > max_weight:
            raise SourceWeightingError("min_weight must be <= max_weight")

        self.storage = storage
        self.target_items_per_source = target_items_per_source
        self.min_weight = min_weight
        self.max_weight = max_weight

        logger.info(
            f"Initialized SourceWeightingSystem with target={target_items_per_source}, "
            f"min_weight={min_weight}, max_weight={max_weight}"
        )

    def calculate_source_weights(
        self, content_list: List[Dict[str, Any]]
    ) -> Dict[str, SourceWeight]:
        """Calculate weights for each source based on content count.

        Uses inverse weighting: sources with more content get lower weights
        to encourage selection from underrepresented sources.

        Formula: weight = target / max(1, content_count)
        Clamped to [min_weight, max_weight]

        Args:
            content_list: List of content items with 'source' field

        Returns:
            Dictionary mapping source names to SourceWeight objects

        Raises:
            SourceWeightingError: If content_list is invalid
        """
        if not isinstance(content_list, list):
            raise SourceWeightingError("Content list must be a list")

        if not content_list:
            return {}

        # Count items per source
        source_counts: Dict[str, int] = defaultdict(int)
        for content in content_list:
            source = content.get("source", "Unknown")
            source_counts[source] += 1

        # Calculate weights
        source_weights: Dict[str, SourceWeight] = {}
        for source, count in source_counts.items():
            # Inverse weight: sources with more content get lower weights
            base_weight = self.target_items_per_source / max(1, count)

            # Clamp to min/max bounds
            weight = max(self.min_weight, min(self.max_weight, base_weight))

            source_weights[source] = SourceWeight(
                source=source,
                content_count=count,
                weight=weight,
                boost=1.0,
            )

        logger.info(
            f"Calculated weights for {len(source_weights)} sources: "
            f"{[(s, w.weight) for s, w in source_weights.items()]}"
        )

        return source_weights

    def apply_weights_to_content(
        self, content_list: List[Dict[str, Any]], weights: Dict[str, SourceWeight]
    ) -> List[Dict[str, Any]]:
        """Apply source weights to content items.

        Adds weight information to each content item based on its source.

        Args:
            content_list: List of content items
            weights: Source weights from calculate_source_weights()

        Returns:
            List of content items with added weight field

        Raises:
            SourceWeightingError: If inputs are invalid
        """
        if not isinstance(content_list, list):
            raise SourceWeightingError("Content list must be a list")

        if not isinstance(weights, dict):
            raise SourceWeightingError("Weights must be a dictionary")

        weighted_content = []
        for content in content_list:
            source = content.get("source", "Unknown")
            source_weight = weights.get(source, SourceWeight(source=source, weight=1.0))

            weighted_item = {
                **content,
                "source_weight": source_weight.weight,
                "source_boost": source_weight.boost,
            }
            weighted_content.append(weighted_item)

        logger.info(f"Applied weights to {len(weighted_content)} content items")

        return weighted_content

    def get_balanced_selection(
        self,
        content_list: List[Dict[str, Any]],
        target_count: int,
        weights: Optional[Dict[str, SourceWeight]] = None,
    ) -> Dict[str, Any]:
        """Select balanced set of items from multiple sources.

        Attempts to select items while respecting source weights, ensuring
        diversity of sources in the selection.

        Args:
            content_list: List of content items to select from
            target_count: Target number of items to select
            weights: Optional pre-calculated weights (calculated if not provided)

        Returns:
            Dictionary with:
                - selected: List of selected items
                - total_items: Total items available
                - selected_count: Number of items selected
                - sources_represented: Number of unique sources
                - distribution: Dict of source -> count in selection
                - coverage: Percentage of target achieved

        Raises:
            SourceWeightingError: If parameters are invalid
        """
        if not isinstance(content_list, list):
            raise SourceWeightingError("Content list must be a list")

        if target_count <= 0:
            raise SourceWeightingError("target_count must be > 0")

        if not content_list:
            return {
                "selected": [],
                "total_items": 0,
                "selected_count": 0,
                "sources_represented": 0,
                "distribution": {},
                "coverage": 0.0,
            }

        # Calculate weights if not provided
        if weights is None:
            weights = self.calculate_source_weights(content_list)

        # Apply weights
        weighted_content = self.apply_weights_to_content(content_list, weights)

        # Sort by weight (descending) and then by index
        sorted_content = sorted(
            enumerate(weighted_content),
            key=lambda x: (-x[1].get("source_weight", 1.0), x[0]),
        )

        # Track selection by source
        source_selection: Dict[str, int] = defaultdict(int)
        selected = []

        # First pass: try to balance by source
        items_by_source: Dict[str, List[int]] = defaultdict(list)
        for idx, (orig_idx, item) in enumerate(sorted_content):
            source = item.get("source", "Unknown")
            items_by_source[source].append(orig_idx)

        # Select items, cycling through sources to ensure diversity
        item_queue = []
        for source, indices in sorted(items_by_source.items()):
            for idx in indices:
                item_queue.append((source, idx))

        for source, idx in item_queue:
            if len(selected) >= target_count:
                break
            selected.append(weighted_content[idx])
            source_selection[source] += 1

        # Distribution map
        distribution = dict(source_selection)
        sources_represented = len(distribution)
        coverage = (len(selected) / target_count * 100) if target_count > 0 else 0

        logger.info(
            f"Selected {len(selected)} items from {sources_represented} sources. "
            f"Coverage: {coverage:.1f}%"
        )

        return {
            "selected": selected,
            "total_items": len(content_list),
            "selected_count": len(selected),
            "sources_represented": sources_represented,
            "distribution": distribution,
            "coverage": coverage,
        }

    def get_source_statistics(
        self, content_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate source distribution statistics.

        Args:
            content_list: List of content items

        Returns:
            Dictionary with:
                - total_sources: Number of unique sources
                - total_items: Total content items
                - source_distribution: Dict of source -> count
                - avg_items_per_source: Average
                - max_items: Maximum from single source
                - min_items: Minimum from single source
                - dominant_source: Source with most items
                - diversity_ratio: Min/Max items ratio

        Raises:
            SourceWeightingError: If content_list is invalid
        """
        if not isinstance(content_list, list):
            raise SourceWeightingError("Content list must be a list")

        if not content_list:
            return {
                "total_sources": 0,
                "total_items": 0,
                "source_distribution": {},
                "avg_items_per_source": 0.0,
                "max_items": 0,
                "min_items": 0,
                "dominant_source": None,
                "diversity_ratio": 0.0,
            }

        # Count items per source
        source_counts = Counter()
        for content in content_list:
            source = content.get("source", "Unknown")
            source_counts[source] += 1

        counts = list(source_counts.values())
        total_sources = len(source_counts)
        total_items = len(content_list)
        max_items = max(counts) if counts else 0
        min_items = min(counts) if counts else 0
        avg_items = total_items / total_sources if total_sources > 0 else 0
        dominant_source = source_counts.most_common(1)[0][0] if source_counts else None
        diversity_ratio = (min_items / max_items) if max_items > 0 else 0.0

        logger.info(
            f"Source statistics: {total_sources} sources, {total_items} items, "
            f"avg={avg_items:.2f}, diversity_ratio={diversity_ratio:.2f}"
        )

        return {
            "total_sources": total_sources,
            "total_items": total_items,
            "source_distribution": dict(source_counts),
            "avg_items_per_source": avg_items,
            "max_items": max_items,
            "min_items": min_items,
            "dominant_source": dominant_source,
            "diversity_ratio": diversity_ratio,
        }

    def weight_content_list(
        self, content_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Complete weighting pipeline for content list.

        Args:
            content_list: List of content items

        Returns:
            Dictionary with:
                - total: Total items
                - weighted_content: List with weights applied
                - weights: Source weight information
                - statistics: Source statistics

        Raises:
            SourceWeightingError: If content_list is invalid
        """
        if not isinstance(content_list, list):
            raise SourceWeightingError("Content list must be a list")

        logger.info(f"Starting complete weighting pipeline for {len(content_list)} items")

        # Calculate weights
        weights = self.calculate_source_weights(content_list)

        # Apply weights
        weighted_content = self.apply_weights_to_content(content_list, weights)

        # Get statistics
        statistics = self.get_source_statistics(content_list)

        logger.info(
            f"Weighting complete: {len(weighted_content)} items, "
            f"{len(weights)} sources"
        )

        return {
            "total": len(content_list),
            "weighted_content": weighted_content,
            "weights": weights,
            "statistics": statistics,
        }

    def weight_database_content(
        self, source_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Weight content from database.

        Retrieves processed content and applies source weighting.

        Args:
            source_type: Optional filter by source type

        Returns:
            Dictionary with weighting results and update count

        Raises:
            SourceWeightingError: If database operation fails
        """
        try:
            logger.info("Retrieving processed content from database")
            content_list = self.storage.get_processed_content(status="summarized")

            if not content_list:
                logger.info("No summarized content found in database")
                return {
                    "total": 0,
                    "weighted": 0,
                    "updates": 0,
                    "weights": {},
                }

            if source_type:
                content_list = [
                    c for c in content_list if c.get("source") == source_type
                ]
                logger.info(f"Filtered to {len(content_list)} items from {source_type}")

            # Apply weighting
            result = self.weight_content_list(content_list)

            # Update database with weights
            updates = 0
            for item in result["weighted_content"]:
                try:
                    self.storage.update_content_status(
                        item.get("id"),
                        "weighted",
                        metadata={
                            "source_weight": item.get("source_weight"),
                            "source_boost": item.get("source_boost"),
                        },
                    )
                    updates += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to update database for item {item.get('id')}: "
                        f"{str(e)}"
                    )

            logger.info(f"Database weighting complete: {updates} items updated")

            return {
                "total": len(content_list),
                "weighted": len(result["weighted_content"]),
                "updates": updates,
                "weights": result["weights"],
                "statistics": result["statistics"],
            }

        except Exception as e:
            logger.error(f"Database weighting failed: {str(e)}")
            raise SourceWeightingError(
                f"Failed to weight database content: {str(e)}"
            )

    def boost_underrepresented_sources(
        self,
        content_list: List[Dict[str, Any]],
        weights: Dict[str, SourceWeight],
        boost_factor: float = 1.5,
    ) -> Dict[str, SourceWeight]:
        """Apply boost to weights of underrepresented sources.

        Increases weights for sources with below-average representation.

        Args:
            content_list: List of content items
            weights: Current source weights
            boost_factor: Factor to multiply weights by (default 1.5)

        Returns:
            Updated weights with boosts applied

        Raises:
            SourceWeightingError: If inputs are invalid
        """
        if not isinstance(weights, dict):
            raise SourceWeightingError("Weights must be a dictionary")

        if boost_factor <= 0:
            raise SourceWeightingError("boost_factor must be > 0")

        # Calculate average content count
        counts = [w.content_count for w in weights.values()]
        avg_count = sum(counts) / len(counts) if counts else 0

        # Boost underrepresented sources
        boosted_weights = {}
        for source, weight_obj in weights.items():
            if weight_obj.content_count < avg_count:
                new_weight = min(self.max_weight, weight_obj.weight * boost_factor)
                boosted_obj = SourceWeight(
                    source=source,
                    content_count=weight_obj.content_count,
                    weight=new_weight,
                    boost=boost_factor,
                )
                boosted_weights[source] = boosted_obj
                logger.info(
                    f"Boosted {source}: {weight_obj.weight:.2f} -> {new_weight:.2f}"
                )
            else:
                boosted_weights[source] = weight_obj

        return boosted_weights

    def get_weighting_metrics(
        self, weights: Dict[str, SourceWeight]
    ) -> Dict[str, Any]:
        """Calculate metrics about weight distribution.

        Args:
            weights: Source weights dictionary

        Returns:
            Dictionary with metrics:
                - total_sources: Number of sources
                - avg_weight: Average weight value
                - max_weight_value: Maximum weight
                - min_weight_value: Minimum weight
                - weight_range: Max - Min
                - weight_stddev: Standard deviation of weights

        Raises:
            SourceWeightingError: If weights invalid
        """
        if not isinstance(weights, dict):
            raise SourceWeightingError("Weights must be a dictionary")

        if not weights:
            return {
                "total_sources": 0,
                "avg_weight": 1.0,
                "max_weight_value": 1.0,
                "min_weight_value": 1.0,
                "weight_range": 0.0,
                "weight_stddev": 0.0,
            }

        weight_values = [w.weight for w in weights.values()]
        avg_weight = sum(weight_values) / len(weight_values)
        max_wt = max(weight_values)
        min_wt = min(weight_values)
        weight_range = max_wt - min_wt

        # Calculate standard deviation
        variance = sum((w - avg_weight) ** 2 for w in weight_values) / len(weight_values)
        stddev = variance ** 0.5

        return {
            "total_sources": len(weights),
            "avg_weight": avg_weight,
            "max_weight_value": max_wt,
            "min_weight_value": min_wt,
            "weight_range": weight_range,
            "weight_stddev": stddev,
        }
