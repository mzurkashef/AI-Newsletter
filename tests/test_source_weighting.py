"""Test suite for source weighting module."""

import pytest
from unittest.mock import Mock, MagicMock
from src.processors.source_weighting import (
    SourceWeightingSystem,
    SourceWeightingError,
    SourceWeight,
)
from src.database.storage import DatabaseStorage


class TestSourceWeightingInitialization:
    """Test SourceWeightingSystem initialization."""

    def test_init_with_valid_storage(self):
        """Test initialization with valid storage."""
        storage = Mock(spec=DatabaseStorage)
        system = SourceWeightingSystem(storage=storage)

        assert system.storage == storage
        assert system.target_items_per_source == 5
        assert system.min_weight == 0.1
        assert system.max_weight == 5.0

    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        storage = Mock(spec=DatabaseStorage)
        system = SourceWeightingSystem(
            storage=storage,
            target_items_per_source=10,
            min_weight=0.2,
            max_weight=3.0,
        )

        assert system.target_items_per_source == 10
        assert system.min_weight == 0.2
        assert system.max_weight == 3.0

    def test_init_with_invalid_storage(self):
        """Test initialization with invalid storage."""
        with pytest.raises(SourceWeightingError):
            SourceWeightingSystem(storage="not_a_storage")

    def test_init_with_invalid_target_items(self):
        """Test initialization with invalid target items."""
        storage = Mock(spec=DatabaseStorage)

        with pytest.raises(SourceWeightingError):
            SourceWeightingSystem(storage=storage, target_items_per_source=0)

    def test_init_with_invalid_min_weight(self):
        """Test initialization with invalid min_weight."""
        storage = Mock(spec=DatabaseStorage)

        with pytest.raises(SourceWeightingError):
            SourceWeightingSystem(storage=storage, min_weight=0)

    def test_init_with_invalid_max_weight(self):
        """Test initialization with invalid max_weight."""
        storage = Mock(spec=DatabaseStorage)

        with pytest.raises(SourceWeightingError):
            SourceWeightingSystem(storage=storage, max_weight=0)

    def test_init_with_min_greater_than_max(self):
        """Test initialization with min_weight > max_weight."""
        storage = Mock(spec=DatabaseStorage)

        with pytest.raises(SourceWeightingError):
            SourceWeightingSystem(
                storage=storage, min_weight=5.0, max_weight=1.0
            )


class TestSourceWeightCalculation:
    """Test weight calculation."""

    @pytest.fixture
    def system(self):
        """Create weighting system for testing."""
        storage = Mock(spec=DatabaseStorage)
        return SourceWeightingSystem(storage=storage)

    def test_calculate_weights_empty_list(self, system):
        """Test weight calculation with empty list."""
        weights = system.calculate_source_weights([])

        assert weights == {}

    def test_calculate_weights_single_source(self, system):
        """Test weight calculation with single source."""
        content = [
            {"source": "NewsA", "content": "Item 1"},
            {"source": "NewsA", "content": "Item 2"},
            {"source": "NewsA", "content": "Item 3"},
        ]

        weights = system.calculate_source_weights(content)

        assert len(weights) == 1
        assert "NewsA" in weights
        assert weights["NewsA"].content_count == 3

    def test_calculate_weights_multiple_sources(self, system):
        """Test weight calculation with multiple sources."""
        content = [
            {"source": "NewsA", "content": "Item 1"},
            {"source": "NewsA", "content": "Item 2"},
            {"source": "NewsB", "content": "Item 3"},
            {"source": "NewsC", "content": "Item 4"},
            {"source": "NewsC", "content": "Item 5"},
            {"source": "NewsC", "content": "Item 6"},
        ]

        weights = system.calculate_source_weights(content)

        assert len(weights) == 3
        assert weights["NewsA"].content_count == 2
        assert weights["NewsB"].content_count == 1
        assert weights["NewsC"].content_count == 3

    def test_calculate_weights_inverse_weighting(self, system):
        """Test that weights are inversely proportional to counts."""
        content = [
            {"source": "A", "content": "1"},
            {"source": "B", "content": "2"},
            {"source": "B", "content": "3"},
            {"source": "B", "content": "4"},
        ]

        weights = system.calculate_source_weights(content)

        # Source A (1 item) should have higher weight than B (3 items)
        assert weights["A"].weight > weights["B"].weight

    def test_calculate_weights_clamped_to_bounds(self, system):
        """Test that weights are clamped to min/max bounds."""
        content = [
            {"source": "A", "content": "1"},  # Very few items
            {"source": "B", "content": "2"},
            {"source": "B", "content": "3"},
            {"source": "B", "content": "4"},
            {"source": "B", "content": "5"},
            {"source": "B", "content": "6"},
            {"source": "B", "content": "7"},
            {"source": "B", "content": "8"},
            {"source": "B", "content": "9"},
            {"source": "B", "content": "10"},
        ]

        weights = system.calculate_source_weights(content)

        assert weights["A"].weight <= system.max_weight
        assert weights["A"].weight >= system.min_weight
        assert weights["B"].weight <= system.max_weight
        assert weights["B"].weight >= system.min_weight

    def test_calculate_weights_missing_source(self, system):
        """Test weight calculation with missing source field."""
        content = [
            {"content": "Item 1"},  # No source field
            {"source": "NewsA", "content": "Item 2"},
        ]

        weights = system.calculate_source_weights(content)

        assert "Unknown" in weights
        assert "NewsA" in weights


class TestApplyWeights:
    """Test applying weights to content."""

    @pytest.fixture
    def system(self):
        """Create weighting system for testing."""
        storage = Mock(spec=DatabaseStorage)
        return SourceWeightingSystem(storage=storage)

    def test_apply_weights_empty_content(self, system):
        """Test applying weights to empty content list."""
        result = system.apply_weights_to_content([], {})

        assert result == []

    def test_apply_weights_adds_weight_field(self, system):
        """Test that applying weights adds weight field to items."""
        content = [
            {"source": "A", "content": "Item 1"},
            {"source": "B", "content": "Item 2"},
        ]

        weights = system.calculate_source_weights(content)
        weighted = system.apply_weights_to_content(content, weights)

        assert all("source_weight" in item for item in weighted)
        assert all("source_boost" in item for item in weighted)

    def test_apply_weights_preserves_content(self, system):
        """Test that applying weights preserves original content."""
        content = [
            {"id": 1, "source": "A", "content": "Item 1", "title": "Test"},
        ]

        weights = system.calculate_source_weights(content)
        weighted = system.apply_weights_to_content(content, weights)

        assert weighted[0]["id"] == 1
        assert weighted[0]["content"] == "Item 1"
        assert weighted[0]["title"] == "Test"

    def test_apply_weights_invalid_content_type(self, system):
        """Test applying weights with invalid content type."""
        with pytest.raises(SourceWeightingError):
            system.apply_weights_to_content("not a list", {})

    def test_apply_weights_invalid_weights_type(self, system):
        """Test applying weights with invalid weights type."""
        content = [{"source": "A", "content": "Item 1"}]

        with pytest.raises(SourceWeightingError):
            system.apply_weights_to_content(content, "not a dict")


class TestBalancedSelection:
    """Test balanced content selection."""

    @pytest.fixture
    def system(self):
        """Create weighting system for testing."""
        storage = Mock(spec=DatabaseStorage)
        return SourceWeightingSystem(storage=storage)

    def test_balanced_selection_empty_content(self, system):
        """Test selection with empty content."""
        result = system.get_balanced_selection([], 5)

        assert result["selected"] == []
        assert result["selected_count"] == 0
        assert result["sources_represented"] == 0

    def test_balanced_selection_single_source(self, system):
        """Test selection from single source."""
        content = [
            {"id": i, "source": "A", "content": f"Item {i}"}
            for i in range(10)
        ]

        result = system.get_balanced_selection(content, 5)

        assert len(result["selected"]) == 5
        assert result["selected_count"] == 5
        assert result["sources_represented"] == 1

    def test_balanced_selection_multiple_sources(self, system):
        """Test selection from multiple sources."""
        content = [
            {"id": i, "source": "A", "content": f"Item {i}"}
            for i in range(5)
        ]
        content.extend([
            {"id": i + 5, "source": "B", "content": f"Item {i}"}
            for i in range(5)
        ])

        result = system.get_balanced_selection(content, 6)

        assert len(result["selected"]) == 6
        assert result["sources_represented"] == 2

    def test_balanced_selection_respects_target_count(self, system):
        """Test that selection respects target count."""
        content = [
            {"id": i, "source": "A", "content": f"Item {i}"}
            for i in range(100)
        ]

        for target in [5, 10, 20]:
            result = system.get_balanced_selection(content, target)
            assert len(result["selected"]) == target

    def test_balanced_selection_invalid_content_type(self, system):
        """Test selection with invalid content type."""
        with pytest.raises(SourceWeightingError):
            system.get_balanced_selection("not a list", 5)

    def test_balanced_selection_invalid_target_count(self, system):
        """Test selection with invalid target count."""
        content = [{"source": "A", "content": "Item"}]

        with pytest.raises(SourceWeightingError):
            system.get_balanced_selection(content, 0)


class TestSourceStatistics:
    """Test source statistics calculation."""

    @pytest.fixture
    def system(self):
        """Create weighting system for testing."""
        storage = Mock(spec=DatabaseStorage)
        return SourceWeightingSystem(storage=storage)

    def test_statistics_empty_content(self, system):
        """Test statistics with empty content."""
        stats = system.get_source_statistics([])

        assert stats["total_sources"] == 0
        assert stats["total_items"] == 0
        assert stats["dominant_source"] is None

    def test_statistics_single_source(self, system):
        """Test statistics with single source."""
        content = [
            {"source": "A", "content": f"Item {i}"}
            for i in range(5)
        ]

        stats = system.get_source_statistics(content)

        assert stats["total_sources"] == 1
        assert stats["total_items"] == 5
        assert stats["dominant_source"] == "A"
        assert stats["diversity_ratio"] == 1.0

    def test_statistics_multiple_sources(self, system):
        """Test statistics with multiple sources."""
        content = [
            {"source": "A", "content": f"Item {i}"}
            for i in range(10)
        ]
        content.extend([
            {"source": "B", "content": f"Item {i}"}
            for i in range(5)
        ])
        content.extend([
            {"source": "C", "content": f"Item {i}"}
            for i in range(3)
        ])

        stats = system.get_source_statistics(content)

        assert stats["total_sources"] == 3
        assert stats["total_items"] == 18
        assert stats["dominant_source"] == "A"
        assert stats["max_items"] == 10
        assert stats["min_items"] == 3

    def test_statistics_diversity_ratio(self, system):
        """Test diversity ratio calculation."""
        content = [
            {"source": "A", "content": f"Item {i}"}
            for i in range(10)
        ]
        content.extend([
            {"source": "B", "content": f"Item {i}"}
            for i in range(1)
        ])

        stats = system.get_source_statistics(content)

        # Diversity ratio = min / max = 1 / 10
        assert stats["diversity_ratio"] == pytest.approx(0.1, rel=0.01)


class TestCompleteWeightingPipeline:
    """Test complete weighting pipeline."""

    @pytest.fixture
    def system(self):
        """Create weighting system for testing."""
        storage = Mock(spec=DatabaseStorage)
        return SourceWeightingSystem(storage=storage)

    def test_weight_content_list_returns_all_fields(self, system):
        """Test that complete pipeline returns all expected fields."""
        content = [
            {"source": "A", "content": f"Item {i}"}
            for i in range(3)
        ]
        content.extend([
            {"source": "B", "content": f"Item {i}"}
            for i in range(5)
        ])

        result = system.weight_content_list(content)

        assert "total" in result
        assert "weighted_content" in result
        assert "weights" in result
        assert "statistics" in result

    def test_weight_content_list_preserves_count(self, system):
        """Test that weighting preserves item count."""
        content = [
            {"source": "A", "content": f"Item {i}"}
            for i in range(10)
        ]

        result = system.weight_content_list(content)

        assert len(result["weighted_content"]) == len(content)
        assert result["total"] == len(content)

    def test_weight_content_list_invalid_content(self, system):
        """Test pipeline with invalid content."""
        with pytest.raises(SourceWeightingError):
            system.weight_content_list("not a list")


class TestDatabaseIntegration:
    """Test database integration."""

    def test_weight_database_empty_content(self):
        """Test weighting empty database content."""
        storage = Mock(spec=DatabaseStorage)
        storage.get_processed_content.return_value = []

        system = SourceWeightingSystem(storage=storage)
        result = system.weight_database_content()

        assert result["total"] == 0
        assert result["weighted"] == 0

    def test_weight_database_with_content(self):
        """Test weighting database content."""
        storage = Mock(spec=DatabaseStorage)
        content_list = [
            {
                "id": 1,
                "source": "A",
                "content": "Item 1",
            },
            {
                "id": 2,
                "source": "B",
                "content": "Item 2",
            },
        ]
        storage.get_processed_content.return_value = content_list

        system = SourceWeightingSystem(storage=storage)
        result = system.weight_database_content()

        assert result["total"] == 2
        assert result["weighted"] == 2


class TestBoostUnderrepresentedSources:
    """Test boost mechanism for underrepresented sources."""

    @pytest.fixture
    def system(self):
        """Create weighting system for testing."""
        storage = Mock(spec=DatabaseStorage)
        return SourceWeightingSystem(storage=storage)

    def test_boost_underrepresented_sources(self, system):
        """Test boosting underrepresented sources."""
        content = [
            {"source": "A", "content": f"Item {i}"}
            for i in range(10)
        ]
        content.extend([
            {"source": "B", "content": f"Item {i}"}
            for i in range(2)
        ])

        weights = system.calculate_source_weights(content)
        boosted = system.boost_underrepresented_sources(
            content, weights, boost_factor=1.5
        )

        # B should have higher weight after boost
        assert boosted["B"].weight > weights["B"].weight
        assert boosted["B"].boost == 1.5

    def test_boost_respects_max_weight(self, system):
        """Test that boost respects max_weight constraint."""
        content = [{"source": "A", "content": "Item 1"}]
        weights = system.calculate_source_weights(content)

        boosted = system.boost_underrepresented_sources(
            content, weights, boost_factor=100.0
        )

        assert boosted["A"].weight <= system.max_weight

    def test_boost_invalid_boost_factor(self, system):
        """Test boost with invalid boost factor."""
        weights = {"A": SourceWeight(source="A", weight=1.0)}

        with pytest.raises(SourceWeightingError):
            system.boost_underrepresented_sources([], weights, boost_factor=0)


class TestWeightingMetrics:
    """Test weight distribution metrics."""

    @pytest.fixture
    def system(self):
        """Create weighting system for testing."""
        storage = Mock(spec=DatabaseStorage)
        return SourceWeightingSystem(storage=storage)

    def test_weighting_metrics_empty_weights(self, system):
        """Test metrics with empty weights."""
        metrics = system.get_weighting_metrics({})

        assert metrics["total_sources"] == 0
        assert metrics["avg_weight"] == 1.0

    def test_weighting_metrics_single_source(self, system):
        """Test metrics with single source."""
        weights = {
            "A": SourceWeight(source="A", weight=2.0)
        }

        metrics = system.get_weighting_metrics(weights)

        assert metrics["total_sources"] == 1
        assert metrics["avg_weight"] == 2.0
        assert metrics["weight_stddev"] == 0.0

    def test_weighting_metrics_multiple_sources(self, system):
        """Test metrics with multiple sources."""
        weights = {
            "A": SourceWeight(source="A", weight=1.0),
            "B": SourceWeight(source="B", weight=2.0),
            "C": SourceWeight(source="C", weight=3.0),
        }

        metrics = system.get_weighting_metrics(weights)

        assert metrics["total_sources"] == 3
        assert metrics["avg_weight"] == 2.0
        assert metrics["max_weight_value"] == 3.0
        assert metrics["min_weight_value"] == 1.0
        assert metrics["weight_range"] == 2.0
        assert metrics["weight_stddev"] > 0

    def test_weighting_metrics_invalid_weights(self, system):
        """Test metrics with invalid weights."""
        with pytest.raises(SourceWeightingError):
            system.get_weighting_metrics("not a dict")


class TestSourceWeightDataclass:
    """Test SourceWeight dataclass."""

    def test_source_weight_creation(self):
        """Test SourceWeight creation."""
        weight = SourceWeight(source="A", content_count=5, weight=2.0)

        assert weight.source == "A"
        assert weight.content_count == 5
        assert weight.weight == 2.0

    def test_source_weight_defaults(self):
        """Test SourceWeight default values."""
        weight = SourceWeight(source="A")

        assert weight.source == "A"
        assert weight.content_count == 0
        assert weight.weight == 1.0
        assert weight.weighted_count == 0.0
        assert weight.boost == 1.0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def system(self):
        """Create weighting system for testing."""
        storage = Mock(spec=DatabaseStorage)
        return SourceWeightingSystem(storage=storage)

    def test_very_large_content_list(self, system):
        """Test with very large content list."""
        content = [
            {"id": i, "source": "A" if i % 3 == 0 else ("B" if i % 3 == 1 else "C"), "content": f"Item {i}"}
            for i in range(1000)
        ]

        result = system.weight_content_list(content)

        assert len(result["weighted_content"]) == 1000
        assert result["statistics"]["total_items"] == 1000

    def test_many_sources(self, system):
        """Test with many different sources."""
        content = [
            {"id": i, "source": f"Source{i % 100}", "content": f"Item {i}"}
            for i in range(1000)
        ]

        result = system.weight_content_list(content)

        assert result["statistics"]["total_sources"] == 100

    def test_missing_source_field(self, system):
        """Test handling missing source field."""
        content = [
            {"content": "Item 1"},
            {"source": "A", "content": "Item 2"},
            {"content": "Item 3"},
        ]

        result = system.weight_content_list(content)

        assert "Unknown" in result["weights"]
        assert result["statistics"]["total_sources"] == 2

    def test_all_sources_same_weight(self, system):
        """Test when all sources have same weight."""
        # Each source has exactly target_items_per_source items
        content = [
            {"source": "A", "content": f"Item {i}"}
            for i in range(5)
        ]
        content.extend([
            {"source": "B", "content": f"Item {i}"}
            for i in range(5)
        ])

        weights = system.calculate_source_weights(content)

        # Both should have same weight (target / count)
        assert weights["A"].weight == weights["B"].weight
