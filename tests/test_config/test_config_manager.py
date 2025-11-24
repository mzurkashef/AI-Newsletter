"""
Tests for Story 1.2: Configuration Management System
Validates configuration loading, validation, and error handling.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Import the Config class and exceptions
import sys

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.config_manager import (
    Config,
    ConfigError,
    InvalidConfigError,
    MissingConfigError,
)


class TestConfigExceptions:
    """Test custom exception classes."""

    def test_config_error_base(self):
        """Test ConfigError is a base exception."""
        error = ConfigError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    def test_missing_config_error(self):
        """Test MissingConfigError includes field name and file path."""
        error = MissingConfigError("TELEGRAM_BOT_TOKEN", "/path/to/.env")
        assert error.field_name == "TELEGRAM_BOT_TOKEN"
        assert error.file_path == "/path/to/.env"
        assert "TELEGRAM_BOT_TOKEN" in str(error)
        assert "/path/to/.env" in str(error)

    def test_invalid_config_error(self):
        """Test InvalidConfigError includes field name, value, and expected format."""
        error = InvalidConfigError("AI_SERVICE_TYPE", "invalid", "ollama or huggingface")
        assert error.field_name == "AI_SERVICE_TYPE"
        assert error.value == "invalid"
        assert error.expected_format == "ollama or huggingface"
        assert "AI_SERVICE_TYPE" in str(error)
        assert "invalid" in str(error)
        assert "ollama or huggingface" in str(error)


class TestConfigLoading:
    """Test configuration loading from files."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory with config structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "ai-newsletter"
            project_root.mkdir()
            (project_root / "config").mkdir()
            (project_root / "data").mkdir()
            (project_root / "logs").mkdir()

            yield project_root

    @pytest.fixture
    def valid_env_file(self, temp_project):
        """Create a valid .env file."""
        env_file = temp_project / ".env"
        env_file.write_text(
            """TELEGRAM_BOT_TOKEN=test_token_123
TELEGRAM_CHAT_ID=test_chat_456
AI_SERVICE_TYPE=ollama
AI_MODEL_PATH=llama2
DATABASE_PATH=data/newsletter.db
LOG_DIR=logs
DELIVERY_DAY=0
CONTENT_WINDOW_DAYS=7
"""
        )
        return env_file

    @pytest.fixture
    def valid_sources_yaml(self, temp_project):
        """Create a valid sources.yaml file."""
        sources_file = temp_project / "config" / "sources.yaml"
        sources_data = {
            "newsletters": [
                {"name": "Test Newsletter", "url": "https://example.com/newsletter"}
            ],
            "youtube_channels": [
                {"name": "Test Channel", "channel_id": "UC1234567890"}
            ],
        }
        sources_file.write_text(yaml.dump(sources_data), encoding="utf-8")
        return sources_file

    @pytest.fixture
    def valid_settings_yaml(self, temp_project):
        """Create a valid settings.yaml file."""
        settings_file = temp_project / "config" / "settings.yaml"
        settings_data = {
            "schedule": {"delivery_day": 0, "delivery_time": "09:00"},
            "content": {"window_days": 7, "min_items_per_category": 1},
            "ai": {"filter_threshold": 0.7, "max_categories": 4},
        }
        settings_file.write_text(yaml.dump(settings_data), encoding="utf-8")
        return settings_file

    def test_load_valid_config(
        self, temp_project, valid_env_file, valid_sources_yaml, valid_settings_yaml
    ):
        """Test loading valid configuration from all sources."""
        config = Config.load(project_root=temp_project)

        # Check environment variables
        assert config.telegram_bot_token == "test_token_123"
        assert config.telegram_chat_id == "test_chat_456"
        assert config.ai_service_type == "ollama"
        assert config.ai_model_path == "llama2"
        assert config.database_path == "data/newsletter.db"
        assert config.log_dir == "logs"

        # Check sources
        assert len(config.newsletter_sources) == 1
        assert config.newsletter_sources[0]["name"] == "Test Newsletter"
        assert config.newsletter_sources[0]["url"] == "https://example.com/newsletter"

        # Check settings
        assert config.delivery_schedule["delivery_day"] == 0
        assert config.content_settings["window_days"] == 7
        assert config.ai_settings["filter_threshold"] == 0.7

    def test_missing_env_file(self, temp_project, valid_sources_yaml, valid_settings_yaml):
        """Test error when .env file is missing."""
        with pytest.raises(MissingConfigError) as exc_info:
            Config.load(project_root=temp_project)
        assert ".env file" in str(exc_info.value)
        assert exc_info.value.file_path == str(temp_project / ".env")

    def test_missing_sources_yaml(self, temp_project, valid_env_file, valid_settings_yaml):
        """Test error when sources.yaml is missing."""
        with pytest.raises(MissingConfigError) as exc_info:
            Config.load(project_root=temp_project)
        assert "config/sources.yaml" in str(exc_info.value)

    def test_missing_settings_yaml(self, temp_project, valid_env_file, valid_sources_yaml):
        """Test error when settings.yaml is missing."""
        with pytest.raises(MissingConfigError) as exc_info:
            Config.load(project_root=temp_project)
        assert "config/settings.yaml" in str(exc_info.value)

    def test_invalid_yaml_syntax(self, temp_project, valid_env_file, valid_settings_yaml):
        """Test error when YAML syntax is invalid."""
        sources_file = temp_project / "config" / "sources.yaml"
        sources_file.write_text("invalid: yaml: syntax: [", encoding="utf-8")

        with pytest.raises(InvalidConfigError) as exc_info:
            Config.load(project_root=temp_project)
        assert "config/sources.yaml" in str(exc_info.value)
        assert "invalid YAML syntax" in str(exc_info.value)


class TestConfigValidation:
    """Test configuration validation."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "ai-newsletter"
            project_root.mkdir()
            (project_root / "config").mkdir()
            yield project_root

    def test_missing_required_env_var(self, temp_project):
        """Test error when required environment variable is missing."""
        # Clear any existing environment variables first
        if "TELEGRAM_BOT_TOKEN" in os.environ:
            del os.environ["TELEGRAM_BOT_TOKEN"]
        
        # Create .env without TELEGRAM_BOT_TOKEN
        env_file = temp_project / ".env"
        env_file.write_text(
            """TELEGRAM_CHAT_ID=test_chat
AI_SERVICE_TYPE=ollama
DELIVERY_DAY=0
"""
        )

        sources_file = temp_project / "config" / "sources.yaml"
        sources_file.write_text("newsletters: []\nyoutube_channels: []\n")

        settings_file = temp_project / "config" / "settings.yaml"
        settings_file.write_text("schedule: {}\ncontent: {}\nai: {}\n")

        with pytest.raises(MissingConfigError) as exc_info:
            Config.load(project_root=temp_project)
        assert "TELEGRAM_BOT_TOKEN" in str(exc_info.value)

    def test_invalid_ai_service_type(self, temp_project):
        """Test error when AI service type is invalid."""
        env_file = temp_project / ".env"
        env_file.write_text(
            """TELEGRAM_BOT_TOKEN=test_token
TELEGRAM_CHAT_ID=test_chat
AI_SERVICE_TYPE=invalid_service
DELIVERY_DAY=0
"""
        )

        sources_file = temp_project / "config" / "sources.yaml"
        sources_file.write_text("newsletters: []\nyoutube_channels: []\n")

        settings_file = temp_project / "config" / "settings.yaml"
        settings_file.write_text("schedule: {}\ncontent: {}\nai: {}\n")

        with pytest.raises(InvalidConfigError) as exc_info:
            Config.load(project_root=temp_project)
        assert "AI_SERVICE_TYPE" in str(exc_info.value)
        assert "invalid_service" in str(exc_info.value)

    def test_invalid_delivery_day(self, temp_project):
        """Test error when delivery_day is out of range."""
        env_file = temp_project / ".env"
        env_file.write_text(
            """TELEGRAM_BOT_TOKEN=test_token
TELEGRAM_CHAT_ID=test_chat
AI_SERVICE_TYPE=ollama
DELIVERY_DAY=7
"""
        )

        sources_file = temp_project / "config" / "sources.yaml"
        sources_file.write_text("newsletters: []\nyoutube_channels: []\n")

        settings_file = temp_project / "config" / "settings.yaml"
        settings_file.write_text("schedule: {}\ncontent: {}\nai: {}\n")

        with pytest.raises(InvalidConfigError) as exc_info:
            Config.load(project_root=temp_project)
        assert "DELIVERY_DAY" in str(exc_info.value)

    def test_invalid_url_in_sources(self, temp_project):
        """Test error when newsletter URL is invalid."""
        env_file = temp_project / ".env"
        env_file.write_text(
            """TELEGRAM_BOT_TOKEN=test_token
TELEGRAM_CHAT_ID=test_chat
AI_SERVICE_TYPE=ollama
DELIVERY_DAY=0
"""
        )

        sources_file = temp_project / "config" / "sources.yaml"
        sources_data = {
            "newsletters": [{"name": "Test", "url": "not-a-valid-url"}],
            "youtube_channels": [],
        }
        sources_file.write_text(yaml.dump(sources_data), encoding="utf-8")

        settings_file = temp_project / "config" / "settings.yaml"
        settings_file.write_text("schedule: {}\ncontent: {}\nai: {}\n")

        with pytest.raises(InvalidConfigError) as exc_info:
            Config.load(project_root=temp_project)
        assert "url" in str(exc_info.value).lower()
        assert "valid URL format" in str(exc_info.value)

    def test_missing_channel_id(self, temp_project):
        """Test error when YouTube channel_id is missing."""
        env_file = temp_project / ".env"
        env_file.write_text(
            """TELEGRAM_BOT_TOKEN=test_token
TELEGRAM_CHAT_ID=test_chat
AI_SERVICE_TYPE=ollama
DELIVERY_DAY=0
"""
        )

        sources_file = temp_project / "config" / "sources.yaml"
        sources_data = {
            "newsletters": [],
            "youtube_channels": [{"name": "Test Channel"}],
        }
        sources_file.write_text(yaml.dump(sources_data), encoding="utf-8")

        settings_file = temp_project / "config" / "settings.yaml"
        settings_file.write_text("schedule: {}\ncontent: {}\nai: {}\n")

        with pytest.raises(MissingConfigError) as exc_info:
            Config.load(project_root=temp_project)
        assert "channel_id" in str(exc_info.value).lower()


class TestConfigMethods:
    """Test Config class methods and properties."""

    @pytest.fixture
    def valid_config(self):
        """Create a valid Config instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "ai-newsletter"
            project_root.mkdir()
            (project_root / "config").mkdir()

            # Create .env
            env_file = project_root / ".env"
            env_file.write_text(
                """TELEGRAM_BOT_TOKEN=test_token
TELEGRAM_CHAT_ID=test_chat
AI_SERVICE_TYPE=ollama
AI_MODEL_PATH=llama2
DATABASE_PATH=data/newsletter.db
LOG_DIR=logs
"""
            )

            # Create sources.yaml
            sources_file = project_root / "config" / "sources.yaml"
            sources_data = {
                "newsletters": [
                    {"name": "Test Newsletter", "url": "https://example.com/news"}
                ],
                "youtube_channels": [
                    {"name": "Test Channel", "channel_id": "UC123"}
                ],
            }
            sources_file.write_text(yaml.dump(sources_data), encoding="utf-8")

            # Create settings.yaml
            settings_file = project_root / "config" / "settings.yaml"
            settings_data = {
                "schedule": {"delivery_day": 0, "delivery_time": "09:00"},
                "content": {"window_days": 7},
                "ai": {"filter_threshold": 0.7},
            }
            settings_file.write_text(yaml.dump(settings_data), encoding="utf-8")

            config = Config.load(project_root=project_root)
            yield config, project_root

    def test_get_telegram_config(self, valid_config):
        """Test get_telegram_config() method."""
        config, _ = valid_config
        telegram_config = config.get_telegram_config()

        assert isinstance(telegram_config, dict)
        assert "bot_token" in telegram_config
        assert "chat_id" in telegram_config
        assert telegram_config["bot_token"] == "test_token"
        assert telegram_config["chat_id"] == "test_chat"

    def test_get_ai_config(self, valid_config):
        """Test get_ai_config() method."""
        config, _ = valid_config
        ai_config = config.get_ai_config()

        assert isinstance(ai_config, dict)
        assert "service_type" in ai_config
        assert "api_key" in ai_config
        assert "model_path" in ai_config
        assert ai_config["service_type"] == "ollama"
        assert ai_config["model_path"] == "llama2"

    def test_get_database_config(self, valid_config):
        """Test get_database_config() method."""
        config, project_root = valid_config
        db_config = config.get_database_config()

        assert isinstance(db_config, dict)
        assert "database_path" in db_config
        assert str(project_root / "data" / "newsletter.db") in db_config["database_path"]

    def test_get_logging_config(self, valid_config):
        """Test get_logging_config() method."""
        config, project_root = valid_config
        logging_config = config.get_logging_config()

        assert isinstance(logging_config, dict)
        assert "log_dir" in logging_config
        assert str(project_root / "logs") in logging_config["log_dir"]

    def test_get_sources(self, valid_config):
        """Test get_sources() method."""
        config, _ = valid_config
        sources = config.get_sources()

        assert isinstance(sources, dict)
        assert "newsletters" in sources
        assert "youtube_channels" in sources
        assert len(sources["newsletters"]) == 1
        assert len(sources["youtube_channels"]) == 1

    def test_get_settings(self, valid_config):
        """Test get_settings() method."""
        config, _ = valid_config
        settings = config.get_settings()

        assert isinstance(settings, dict)
        assert "schedule" in settings
        assert "content" in settings
        assert "ai" in settings
        assert settings["schedule"]["delivery_day"] == 0
        assert settings["content"]["window_days"] == 7


class TestConfigEdgeCases:
    """Test edge cases and optional configuration."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "ai-newsletter"
            project_root.mkdir()
            (project_root / "config").mkdir()
            yield project_root

    def test_optional_ai_api_key(self, temp_project):
        """Test that AI API key is optional."""
        env_file = temp_project / ".env"
        env_file.write_text(
            """TELEGRAM_BOT_TOKEN=test_token
TELEGRAM_CHAT_ID=test_chat
AI_SERVICE_TYPE=ollama
"""
        )

        sources_file = temp_project / "config" / "sources.yaml"
        sources_file.write_text("newsletters: []\nyoutube_channels: []\n")

        settings_file = temp_project / "config" / "settings.yaml"
        settings_file.write_text("schedule: {}\ncontent: {}\nai: {}\n")

        config = Config.load(project_root=temp_project)
        assert config.ai_api_key is None

    def test_empty_sources_lists(self, temp_project):
        """Test that empty sources lists are valid."""
        env_file = temp_project / ".env"
        env_file.write_text(
            """TELEGRAM_BOT_TOKEN=test_token
TELEGRAM_CHAT_ID=test_chat
AI_SERVICE_TYPE=ollama
"""
        )

        sources_file = temp_project / "config" / "sources.yaml"
        sources_file.write_text("newsletters: []\nyoutube_channels: []\n")

        settings_file = temp_project / "config" / "settings.yaml"
        settings_file.write_text("schedule: {}\ncontent: {}\nai: {}\n")

        config = Config.load(project_root=temp_project)
        assert config.newsletter_sources == []
        assert config.youtube_channels == []

    def test_default_settings(self, temp_project):
        """Test that default settings are used when not specified."""
        env_file = temp_project / ".env"
        env_file.write_text(
            """TELEGRAM_BOT_TOKEN=test_token
TELEGRAM_CHAT_ID=test_chat
AI_SERVICE_TYPE=ollama
"""
        )

        sources_file = temp_project / "config" / "sources.yaml"
        sources_file.write_text("newsletters: []\nyoutube_channels: []\n")

        settings_file = temp_project / "config" / "settings.yaml"
        settings_file.write_text("schedule: {}\ncontent: {}\nai: {}\n")

        config = Config.load(project_root=temp_project)
        # Check defaults are applied
        assert config.delivery_schedule["delivery_day"] == 0
        assert config.content_settings["window_days"] == 7
        assert config.ai_settings["filter_threshold"] == 0.7

