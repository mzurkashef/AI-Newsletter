"""
Database models and schema definitions for AI Newsletter system.

This module defines the SQLite schema for storing raw content, processed content,
delivery history, and source status tracking.
"""

import sqlite3
from datetime import datetime
from typing import Optional

# Schema version for migration tracking
SCHEMA_VERSION = 1


class DatabaseSchema:
    """SQLite database schema definitions."""

    # SQL statements for table creation
    CREATE_RAW_CONTENT_TABLE = """
    CREATE TABLE IF NOT EXISTS raw_content (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_type TEXT NOT NULL CHECK(source_type IN ('newsletter', 'youtube')),
        source_url TEXT NOT NULL,
        content_text TEXT,
        content_url TEXT,
        title TEXT,
        published_at TEXT,
        collected_at TEXT NOT NULL,
        metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """

    CREATE_PROCESSED_CONTENT_TABLE = """
    CREATE TABLE IF NOT EXISTS processed_content (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_content_id INTEGER NOT NULL UNIQUE,
        summary TEXT,
        category TEXT,
        importance_score REAL CHECK(importance_score >= 0.0 AND importance_score <= 1.0),
        processed_at TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (raw_content_id) REFERENCES raw_content(id)
    )
    """

    CREATE_DELIVERY_HISTORY_TABLE = """
    CREATE TABLE IF NOT EXISTS delivery_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        newsletter_content TEXT NOT NULL,
        delivered_at TEXT,
        delivery_status TEXT NOT NULL CHECK(delivery_status IN ('success', 'failure', 'partial')),
        telegram_message_id TEXT,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """

    CREATE_SOURCE_STATUS_TABLE = """
    CREATE TABLE IF NOT EXISTS source_status (
        source_id TEXT PRIMARY KEY,
        source_type TEXT NOT NULL CHECK(source_type IN ('newsletter', 'youtube')),
        last_collected_at TEXT,
        last_success TEXT,
        last_error TEXT,
        consecutive_failures INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """

    CREATE_SCHEMA_VERSION_TABLE = """
    CREATE TABLE IF NOT EXISTS schema_version (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        version INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """

    # Index creation statements for performance
    INDEXES = [
        "CREATE INDEX IF NOT EXISTS idx_raw_content_source_type ON raw_content(source_type)",
        "CREATE INDEX IF NOT EXISTS idx_raw_content_collected_at ON raw_content(collected_at)",
        "CREATE INDEX IF NOT EXISTS idx_raw_content_published_at ON raw_content(published_at)",
        "CREATE INDEX IF NOT EXISTS idx_processed_content_raw_id ON processed_content(raw_content_id)",
        "CREATE INDEX IF NOT EXISTS idx_processed_content_category ON processed_content(category)",
        "CREATE INDEX IF NOT EXISTS idx_processed_content_processed_at ON processed_content(processed_at)",
        "CREATE INDEX IF NOT EXISTS idx_delivery_history_delivered_at ON delivery_history(delivered_at)",
        "CREATE INDEX IF NOT EXISTS idx_delivery_history_status ON delivery_history(delivery_status)",
        "CREATE INDEX IF NOT EXISTS idx_source_status_type ON source_status(source_type)",
        "CREATE INDEX IF NOT EXISTS idx_source_status_collected ON source_status(last_collected_at)",
    ]

    @classmethod
    def get_all_create_statements(cls) -> list[str]:
        """Get all table creation statements in dependency order."""
        return [
            cls.CREATE_SCHEMA_VERSION_TABLE,
            cls.CREATE_RAW_CONTENT_TABLE,
            cls.CREATE_PROCESSED_CONTENT_TABLE,
            cls.CREATE_DELIVERY_HISTORY_TABLE,
            cls.CREATE_SOURCE_STATUS_TABLE,
        ]

    @classmethod
    def get_all_index_statements(cls) -> list[str]:
        """Get all index creation statements."""
        return cls.INDEXES


class RawContent:
    """Represents a raw content record."""

    def __init__(
        self,
        source_type: str,
        source_url: str,
        collected_at: str,
        content_text: Optional[str] = None,
        content_url: Optional[str] = None,
        title: Optional[str] = None,
        published_at: Optional[str] = None,
        metadata: Optional[str] = None,
    ):
        self.source_type = source_type
        self.source_url = source_url
        self.collected_at = collected_at
        self.content_text = content_text
        self.content_url = content_url
        self.title = title
        self.published_at = published_at
        self.metadata = metadata

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "source_type": self.source_type,
            "source_url": self.source_url,
            "content_text": self.content_text,
            "content_url": self.content_url,
            "title": self.title,
            "published_at": self.published_at,
            "collected_at": self.collected_at,
            "metadata": self.metadata,
        }


class ProcessedContent:
    """Represents a processed content record."""

    def __init__(
        self,
        raw_content_id: int,
        processed_at: str,
        summary: Optional[str] = None,
        category: Optional[str] = None,
        importance_score: Optional[float] = None,
    ):
        self.raw_content_id = raw_content_id
        self.processed_at = processed_at
        self.summary = summary
        self.category = category
        self.importance_score = importance_score

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "raw_content_id": self.raw_content_id,
            "summary": self.summary,
            "category": self.category,
            "importance_score": self.importance_score,
            "processed_at": self.processed_at,
        }


class DeliveryHistory:
    """Represents a delivery history record."""

    def __init__(
        self,
        newsletter_content: str,
        delivery_status: str,
        delivered_at: Optional[str] = None,
        telegram_message_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        self.newsletter_content = newsletter_content
        self.delivery_status = delivery_status
        self.delivered_at = delivered_at
        self.telegram_message_id = telegram_message_id
        self.error_message = error_message

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "newsletter_content": self.newsletter_content,
            "delivered_at": self.delivered_at,
            "delivery_status": self.delivery_status,
            "telegram_message_id": self.telegram_message_id,
            "error_message": self.error_message,
        }


class SourceStatus:
    """Represents a source status record."""

    def __init__(
        self,
        source_id: str,
        source_type: str,
        last_collected_at: Optional[str] = None,
        last_success: Optional[str] = None,
        last_error: Optional[str] = None,
        consecutive_failures: int = 0,
    ):
        self.source_id = source_id
        self.source_type = source_type
        self.last_collected_at = last_collected_at
        self.last_success = last_success
        self.last_error = last_error
        self.consecutive_failures = consecutive_failures

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion/update."""
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "last_collected_at": self.last_collected_at,
            "last_success": self.last_success,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
        }
