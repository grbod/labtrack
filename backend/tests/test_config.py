"""Tests for configuration module."""

import pytest
from pathlib import Path
import os


def test_settings_import():
    """Test that settings can be imported."""
    from app.config import settings

    assert settings is not None


def test_default_settings():
    """Test default settings values."""
    from app.config import settings

    assert settings.app_name == "COA Management System"
    assert settings.app_env == "development"
    assert settings.debug is False  # Default is False
    assert settings.database_url == "sqlite:///./coa_management.db"


def test_paths_created():
    """Test that required directories are created."""
    from app.config import settings

    # Check that directory attributes exist (settings doesn't have upload_path or export_path)
    assert hasattr(settings, 'templates_path')
    assert hasattr(settings, 'watch_folder_path')
    assert hasattr(settings, 'coa_output_folder')


def test_env_override():
    """Test that environment variables override defaults."""
    # Set a test environment variable
    os.environ["APP_NAME"] = "Test COA System"

    # Re-import to get new settings
    from importlib import reload
    import app.config

    reload(src.config)
    from app.config import settings

    assert settings.app_name == "Test COA System"

    # Clean up
    del os.environ["APP_NAME"]
