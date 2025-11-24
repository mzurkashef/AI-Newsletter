"""
Configuration Management Module

Loads and validates configuration from environment variables and YAML files.
Provides typed access to all configuration settings.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

import yaml
from dotenv import load_dotenv


# Custom Exception Classes
class ConfigError(Exception):
    """Base exception for configuration errors."""

    pass


class MissingConfigError(ConfigError):
    """Raised when required configuration is missing."""

    def __init__(self, field_name: str, file_path: str):
        self.field_name = field_name
        self.file_path = file_path
        message = (
            f"Required configuration '{field_name}' is missing. "
            f"Add it to {file_path}"
        )
        super().__init__(message)


class InvalidConfigError(ConfigError):
    """Raised when configuration format is invalid."""

    def __init__(self, field_name: str, value: Any, expected_format: str):
        self.field_name = field_name
        self.value = value
        self.expected_format = expected_format
        message = (
            f"Invalid configuration for '{field_name}': got '{value}'. "
            f"Expected: {expected_format}"
        )
        super().__init__(message)


class Config:
    """
    Configuration manager providing typed access to settings.

    Loads configuration from:
    - Environment variables (from .env file)
    - config/sources.yaml (newsletter and YouTube sources)
    - config/settings.yaml (application settings)

    Validates all configuration at initialization.
    """

    # Required environment variables
    REQUIRED_ENV_VARS = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "AI_SERVICE_TYPE",
    ]

    # Valid AI service types
    VALID_AI_SERVICE_TYPES = ["ollama", "huggingface", "groq", "local"]

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize configuration by loading from all sources and validating.

        Args:
            project_root: Root directory of the project. If None, uses current directory.

        Raises:
            MissingConfigError: If required configuration is missing.
            InvalidConfigError: If configuration format is invalid.
        """
        if project_root is None:
            # Assume we're in ai-newsletter directory or find it
            current = Path.cwd()
            if current.name == "ai-newsletter":
                self.project_root = current
            elif (current / "ai-newsletter").exists():
                self.project_root = current / "ai-newsletter"
            else:
                # Try to find ai-newsletter in parent directories
                self.project_root = current
        else:
            self.project_root = Path(project_root)

        # Load environment variables
        self._load_env_vars()

        # Load YAML configuration files
        self._load_sources_yaml()
        self._load_settings_yaml()

        # Validate all configuration
        self.validate()

    def _load_env_vars(self) -> None:
        """Load environment variables from .env file."""
        env_file = self.project_root / ".env"

        if not env_file.exists():
            raise MissingConfigError(
                ".env file", str(env_file)
            )

        # Load .env file (override=True to ensure test isolation)
        load_dotenv(dotenv_path=env_file, override=True)

        # Load required environment variables
        self.telegram_bot_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        self.telegram_chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
        self.ai_service_type = (os.getenv("AI_SERVICE_TYPE") or "").strip().lower()

        # Load optional environment variables
        self.ai_api_key = (os.getenv("AI_API_KEY") or "").strip() or None
        self.ai_model_path = (os.getenv("AI_MODEL_PATH") or "").strip() or None
        self.database_path = (os.getenv("DATABASE_PATH") or "data/newsletter.db").strip()
        self.log_dir = (os.getenv("LOG_DIR") or "logs").strip()
        self.delivery_day = (os.getenv("DELIVERY_DAY") or "0").strip()
        self.content_window_days = (os.getenv("CONTENT_WINDOW_DAYS") or "7").strip()

    def _load_sources_yaml(self) -> None:
        """Load sources configuration from config/sources.yaml."""
        sources_file = self.project_root / "config" / "sources.yaml"

        if not sources_file.exists():
            raise MissingConfigError(
                "config/sources.yaml", str(sources_file)
            )

        try:
            with open(sources_file, "r", encoding="utf-8") as f:
                sources_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise InvalidConfigError(
                "config/sources.yaml",
                "invalid YAML syntax",
                f"valid YAML format. Error: {str(e)}",
            ) from e

        if sources_data is None:
            sources_data = {}

        # Extract newsletter sources
        self.newsletter_sources = sources_data.get("newsletters", [])
        if not isinstance(self.newsletter_sources, list):
            raise InvalidConfigError(
                "newsletters",
                type(self.newsletter_sources).__name__,
                "list of newsletter objects",
            )

        # Extract YouTube channel sources
        self.youtube_channels = sources_data.get("youtube_channels", [])
        if not isinstance(self.youtube_channels, list):
            raise InvalidConfigError(
                "youtube_channels",
                type(self.youtube_channels).__name__,
                "list of YouTube channel objects",
            )

    def _load_settings_yaml(self) -> None:
        """Load settings configuration from config/settings.yaml."""
        settings_file = self.project_root / "config" / "settings.yaml"

        if not settings_file.exists():
            raise MissingConfigError(
                "config/settings.yaml", str(settings_file)
            )

        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise InvalidConfigError(
                "config/settings.yaml",
                "invalid YAML syntax",
                f"valid YAML format. Error: {str(e)}",
            ) from e

        if settings_data is None:
            settings_data = {}

        # Extract schedule settings
        schedule = settings_data.get("schedule", {})
        self.delivery_schedule = {
            "delivery_day": schedule.get("delivery_day", 0),
            "delivery_time": schedule.get("delivery_time", "09:00"),
        }

        # Extract content settings
        content = settings_data.get("content", {})
        self.content_settings = {
            "window_days": content.get("window_days", 7),
            "min_items_per_category": content.get("min_items_per_category", 1),
        }

        # Extract AI settings
        ai = settings_data.get("ai", {})
        self.ai_settings = {
            "filter_threshold": ai.get("filter_threshold", 0.7),
            "max_categories": ai.get("max_categories", 4),
        }

    def validate(self) -> None:
        """
        Validate all configuration values.

        Raises:
            MissingConfigError: If required configuration is missing.
            InvalidConfigError: If configuration format is invalid.
        """
        env_file = self.project_root / ".env"

        # Validate required environment variables (check for empty strings)
        env_file = self.project_root / ".env"
        if not self.telegram_bot_token or self.telegram_bot_token.strip() == "":
            raise MissingConfigError("TELEGRAM_BOT_TOKEN", str(env_file))
        if not self.telegram_chat_id or self.telegram_chat_id.strip() == "":
            raise MissingConfigError("TELEGRAM_CHAT_ID", str(env_file))
        if not self.ai_service_type or self.ai_service_type.strip() == "":
            raise MissingConfigError("AI_SERVICE_TYPE", str(env_file))

        # Validate AI service type
        if self.ai_service_type not in self.VALID_AI_SERVICE_TYPES:
            raise InvalidConfigError(
                "AI_SERVICE_TYPE",
                self.ai_service_type,
                f"one of: {', '.join(self.VALID_AI_SERVICE_TYPES)}",
            )

        # Validate delivery_day
        try:
            delivery_day_int = int(self.delivery_day)
            if delivery_day_int < 0 or delivery_day_int > 6:
                raise InvalidConfigError(
                    "DELIVERY_DAY",
                    self.delivery_day,
                    "integer between 0 (Monday) and 6 (Sunday)",
                )
        except ValueError:
            raise InvalidConfigError(
                "DELIVERY_DAY",
                self.delivery_day,
                "integer between 0 (Monday) and 6 (Sunday)",
            ) from None

        # Validate content_window_days
        try:
            window_days_int = int(self.content_window_days)
            if window_days_int <= 0:
                raise InvalidConfigError(
                    "CONTENT_WINDOW_DAYS",
                    self.content_window_days,
                    "positive integer",
                )
        except ValueError:
            raise InvalidConfigError(
                "CONTENT_WINDOW_DAYS",
                self.content_window_days,
                "positive integer",
            ) from None

        # Validate newsletter sources
        for idx, newsletter in enumerate(self.newsletter_sources):
            if not isinstance(newsletter, dict):
                raise InvalidConfigError(
                    f"newsletters[{idx}]",
                    type(newsletter).__name__,
                    "dictionary with 'name' and 'url' keys",
                )
            if "url" not in newsletter:
                raise MissingConfigError(
                    f"newsletters[{idx}].url",
                    str(self.project_root / "config" / "sources.yaml"),
                )
            url = newsletter.get("url", "")
            if not self._is_valid_url(url):
                raise InvalidConfigError(
                    f"newsletters[{idx}].url",
                    url,
                    "valid URL format",
                )

        # Validate YouTube channels
        for idx, channel in enumerate(self.youtube_channels):
            if not isinstance(channel, dict):
                raise InvalidConfigError(
                    f"youtube_channels[{idx}]",
                    type(channel).__name__,
                    "dictionary with 'name' and 'channel_id' keys",
                )
            if "channel_id" not in channel:
                raise MissingConfigError(
                    f"youtube_channels[{idx}].channel_id",
                    str(self.project_root / "config" / "sources.yaml"),
                )
            channel_id = channel.get("channel_id", "")
            if not channel_id or not isinstance(channel_id, str):
                raise InvalidConfigError(
                    f"youtube_channels[{idx}].channel_id",
                    channel_id,
                    "non-empty string",
                )

    def _is_valid_url(self, url: str) -> bool:
        """Check if a string is a valid URL."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    # Configuration access methods
    def get_telegram_config(self) -> Dict[str, str]:
        """
        Get Telegram configuration.

        Returns:
            Dictionary with 'bot_token' and 'chat_id' keys.
        """
        return {
            "bot_token": self.telegram_bot_token,
            "chat_id": self.telegram_chat_id,
        }

    def get_ai_config(self) -> Dict[str, Optional[str]]:
        """
        Get AI service configuration.

        Returns:
            Dictionary with 'service_type', 'api_key', and 'model_path' keys.
        """
        return {
            "service_type": self.ai_service_type,
            "api_key": self.ai_api_key,
            "model_path": self.ai_model_path,
        }

    def get_database_config(self) -> Dict[str, str]:
        """
        Get database configuration.

        Returns:
            Dictionary with 'database_path' key.
        """
        return {
            "database_path": str(self.project_root / self.database_path),
        }

    def get_logging_config(self) -> Dict[str, str]:
        """
        Get logging configuration.

        Returns:
            Dictionary with 'log_dir' key.
        """
        return {
            "log_dir": str(self.project_root / self.log_dir),
        }

    def get_sources(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get content sources configuration.

        Returns:
            Dictionary with 'newsletters' and 'youtube_channels' keys.
        """
        return {
            "newsletters": self.newsletter_sources,
            "youtube_channels": self.youtube_channels,
        }

    def get_settings(self) -> Dict[str, Dict[str, Any]]:
        """
        Get application settings.

        Returns:
            Dictionary with 'schedule', 'content', and 'ai' keys.
        """
        return {
            "schedule": self.delivery_schedule,
            "content": self.content_settings,
            "ai": self.ai_settings,
        }

    @classmethod
    def load(cls, project_root: Optional[Path] = None) -> "Config":
        """
        Load configuration from all sources and validate.

        Args:
            project_root: Root directory of the project. If None, uses current directory.

        Returns:
            Config instance with loaded and validated configuration.

        Raises:
            MissingConfigError: If required configuration is missing.
            InvalidConfigError: If configuration format is invalid.
        """
        return cls(project_root=project_root)

