"""AI-powered content processing module for AI Newsletter system."""

from .content_ai_filter import ContentAIFilter, ContentAIFilterError
from .content_deduplicator import ContentDeduplicator, ContentDuplicateError
from .topic_categorizer import TopicCategorizer, TopicCategorizationError
from .content_summarizer import (
    ContentSummarizer,
    ContentSummarizationError,
    SummaryFormat,
)
from .source_weighting import (
    SourceWeightingSystem,
    SourceWeightingError,
    SourceWeight,
)
from .duplicate_processor import (
    DuplicateProcessor,
    DuplicateProcessingError,
    ContentMatchMethod,
)

__all__ = [
    "ContentAIFilter",
    "ContentAIFilterError",
    "ContentDeduplicator",
    "ContentDuplicateError",
    "TopicCategorizer",
    "TopicCategorizationError",
    "ContentSummarizer",
    "ContentSummarizationError",
    "SummaryFormat",
    "SourceWeightingSystem",
    "SourceWeightingError",
    "SourceWeight",
    "DuplicateProcessor",
    "DuplicateProcessingError",
    "ContentMatchMethod",
]
