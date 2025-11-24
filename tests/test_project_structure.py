"""
Tests for Story 1.1: Project Initialization and Repository Setup
Validates that all required directories, files, and dependencies are in place.
"""

import os
import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestProjectStructure:
    """Test suite for project structure validation."""

    def test_required_directories_exist(self):
        """AC1.1.1: Test that all required directories exist."""
        required_dirs = [
            "src",
            "config",
            "data",
            "logs",
            "tests",
        ]
        
        for dir_name in required_dirs:
            dir_path = PROJECT_ROOT / dir_name
            assert dir_path.exists(), f"Required directory '{dir_name}' does not exist"
            assert dir_path.is_dir(), f"'{dir_name}' exists but is not a directory"

    def test_src_subdirectories_exist(self):
        """AC1.1.9: Test that src/ contains all required subdirectories."""
        required_subdirs = [
            "collectors",
            "processors",
            "delivery",
            "utils",
            "database",
            "config",
        ]
        
        src_path = PROJECT_ROOT / "src"
        for subdir in required_subdirs:
            subdir_path = src_path / subdir
            assert subdir_path.exists(), f"Required subdirectory 'src/{subdir}' does not exist"
            assert subdir_path.is_dir(), f"'src/{subdir}' exists but is not a directory"

    def test_python_packages_have_init_files(self):
        """AC1.1.10: Test that all Python package directories contain __init__.py files."""
        package_dirs = [
            "src",
            "src/collectors",
            "src/processors",
            "src/delivery",
            "src/utils",
            "src/database",
            "src/config",
            "tests",
            "tests/test_collectors",
            "tests/test_processors",
            "tests/test_delivery",
            "tests/test_utils",
        ]
        
        for package_dir in package_dirs:
            init_file = PROJECT_ROOT / package_dir / "__init__.py"
            assert init_file.exists(), f"__init__.py missing in '{package_dir}'"
            assert init_file.is_file(), f"'{package_dir}/__init__.py' exists but is not a file"

    def test_requirements_txt_exists(self):
        """AC1.1.2: Test that requirements.txt exists."""
        requirements_file = PROJECT_ROOT / "requirements.txt"
        assert requirements_file.exists(), "requirements.txt does not exist"
        assert requirements_file.is_file(), "requirements.txt exists but is not a file"

    def test_requirements_txt_contains_core_dependencies(self):
        """AC1.1.7: Test that requirements.txt contains all core dependencies."""
        requirements_file = PROJECT_ROOT / "requirements.txt"
        assert requirements_file.exists(), "requirements.txt does not exist"
        
        with open(requirements_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        core_dependencies = [
            "requests",
            "beautifulsoup4",
            "yt-dlp",
            "python-telegram-bot",
            "python-dotenv",
            "tenacity",
            "fuzzywuzzy",
            "PyYAML",
        ]
        
        for dep in core_dependencies:
            assert dep.lower() in content.lower(), f"Core dependency '{dep}' not found in requirements.txt"

    def test_requirements_txt_contains_dev_dependencies(self):
        """AC1.1.8: Test that requirements.txt contains development dependencies."""
        requirements_file = PROJECT_ROOT / "requirements.txt"
        assert requirements_file.exists(), "requirements.txt does not exist"
        
        with open(requirements_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        dev_dependencies = [
            "pytest",
            "black",
            "pylint",
        ]
        
        for dep in dev_dependencies:
            assert dep.lower() in content.lower(), f"Dev dependency '{dep}' not found in requirements.txt"

    def test_requirements_txt_has_version_pins(self):
        """AC1.1.2: Test that requirements.txt has version pins (not 'latest')."""
        requirements_file = PROJECT_ROOT / "requirements.txt"
        assert requirements_file.exists(), "requirements.txt does not exist"
        
        with open(requirements_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # Check that at least some lines have version pins (>= or ==)
        has_version_pins = any(">=" in line or "==" in line for line in lines if line.strip() and not line.strip().startswith("#"))
        assert has_version_pins, "requirements.txt should pin versions (use >= or ==), not 'latest'"

    def test_env_example_exists(self):
        """AC1.1.3: Test that .env.example exists."""
        env_example = PROJECT_ROOT / ".env.example"
        assert env_example.exists(), ".env.example does not exist"
        assert env_example.is_file(), ".env.example exists but is not a file"

    def test_env_example_contains_required_variables(self):
        """AC1.1.3: Test that .env.example contains required environment variable placeholders."""
        env_example = PROJECT_ROOT / ".env.example"
        assert env_example.exists(), ".env.example does not exist"
        
        with open(env_example, "r", encoding="utf-8") as f:
            content = f.read()
        
        required_vars = [
            "TELEGRAM_BOT_TOKEN",
            "AI_SERVICE_TYPE",
        ]
        
        for var in required_vars:
            assert var in content, f"Required environment variable '{var}' not found in .env.example"

    def test_gitignore_exists(self):
        """AC1.1.4: Test that .gitignore exists."""
        gitignore = PROJECT_ROOT / ".gitignore"
        assert gitignore.exists(), ".gitignore does not exist"
        assert gitignore.is_file(), ".gitignore exists but is not a file"

    def test_gitignore_excludes_sensitive_files(self):
        """AC1.1.4: Test that .gitignore excludes sensitive files and directories."""
        gitignore = PROJECT_ROOT / ".gitignore"
        assert gitignore.exists(), ".gitignore does not exist"
        
        with open(gitignore, "r", encoding="utf-8") as f:
            content = f.read()
        
        required_exclusions = [
            ".env",
            "data/",
            "logs/",
            "__pycache__/",
            "venv/",
        ]
        
        for exclusion in required_exclusions:
            assert exclusion in content, f"Required exclusion '{exclusion}' not found in .gitignore"

    def test_gitignore_keeps_gitkeep_files(self):
        """AC1.1.4: Test that .gitignore keeps .gitkeep files."""
        gitignore = PROJECT_ROOT / ".gitignore"
        assert gitignore.exists(), ".gitignore does not exist"
        
        with open(gitignore, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check that .gitkeep is explicitly kept
        assert ".gitkeep" in content or "!data/.gitkeep" in content or "!logs/.gitkeep" in content, \
            ".gitignore should keep .gitkeep files (use !data/.gitkeep or !logs/.gitkeep)"

    def test_readme_exists(self):
        """AC1.1.5: Test that README.md exists."""
        readme = PROJECT_ROOT / "README.md"
        assert readme.exists(), "README.md does not exist"
        assert readme.is_file(), "README.md exists but is not a file"

    def test_readme_contains_setup_instructions(self):
        """AC1.1.5: Test that README.md contains setup instructions."""
        readme = PROJECT_ROOT / "README.md"
        assert readme.exists(), "README.md does not exist"
        
        with open(readme, "r", encoding="utf-8") as f:
            content = f.read()
        
        setup_keywords = [
            "setup",
            "install",
            "requirements",
            "virtual environment",
            "venv",
        ]
        
        # Check that at least some setup-related keywords are present
        has_setup_content = any(keyword.lower() in content.lower() for keyword in setup_keywords)
        assert has_setup_content, "README.md should contain setup instructions"

    def test_readme_documents_python_version(self):
        """AC1.1.6: Test that README.md documents Python 3.9+ requirement."""
        readme = PROJECT_ROOT / "README.md"
        assert readme.exists(), "README.md does not exist"
        
        with open(readme, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check for Python version requirement
        assert "3.9" in content or "Python 3" in content, \
            "README.md should document Python 3.9+ requirement"

    def test_gitkeep_files_exist(self):
        """Test that .gitkeep files exist in data/ and logs/ directories."""
        data_gitkeep = PROJECT_ROOT / "data" / ".gitkeep"
        logs_gitkeep = PROJECT_ROOT / "logs" / ".gitkeep"
        
        assert data_gitkeep.exists(), ".gitkeep file missing in data/ directory"
        assert logs_gitkeep.exists(), ".gitkeep file missing in logs/ directory"

    def test_test_structure_matches_source(self):
        """Test that test directory structure mirrors source structure."""
        test_dirs = [
            "tests/test_collectors",
            "tests/test_processors",
            "tests/test_delivery",
            "tests/test_utils",
        ]
        
        for test_dir in test_dirs:
            dir_path = PROJECT_ROOT / test_dir
            assert dir_path.exists(), f"Test directory '{test_dir}' does not exist"
            assert dir_path.is_dir(), f"'{test_dir}' exists but is not a directory"






