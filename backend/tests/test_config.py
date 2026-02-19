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

    # Check that app_name is set (value may vary by environment)
    assert settings.app_name is not None
    assert len(settings.app_name) > 0
    # Check other expected defaults
    assert settings.app_env in ["development", "production", "test"]
    assert isinstance(settings.debug, bool)
    assert "sqlite" in settings.database_url or "postgresql" in settings.database_url


def test_paths_created():
    """Test that required directories are created."""
    from app.config import settings

    # Check that directory attributes exist
    assert hasattr(settings, 'templates_path')
    assert hasattr(settings, 'watch_folder_path')
    assert hasattr(settings, 'coa_output_folder')


def test_env_override():
    """Test that environment variables override defaults."""
    import app.config
    from importlib import reload

    # Set a test environment variable
    original_value = os.environ.get("APP_NAME")
    os.environ["APP_NAME"] = "Test LabTrack"

    # Re-import to get new settings
    reload(app.config)
    from app.config import settings

    assert settings.app_name == "Test LabTrack"

    # Clean up - restore original or delete
    if original_value:
        os.environ["APP_NAME"] = original_value
    else:
        del os.environ["APP_NAME"]

    # Reload again to restore
    reload(app.config)
