"""Unit tests for core configuration and package baseline."""

import os
from unittest.mock import patch

from personal_job_hunter import __version__
from personal_job_hunter.core.config import Settings, get_settings


def test_package_version() -> None:
    """Verify package version is defined."""
    assert __version__ == "0.1.0"


def test_default_settings() -> None:
    """Verify default settings load correctly without custom environment."""
    config = Settings()
    assert config.app_name == "Personal AI Job Hunter"
    assert config.app_env == "development"
    assert config.debug is False
    assert config.log_level == "INFO"


def test_settings_custom_override() -> None:
    """Verify explicit parameters override defaults."""
    config = Settings(
        app_name="Test Hunter",
        app_env="production",
        debug=True,
        log_level="DEBUG",
    )
    assert config.app_name == "Test Hunter"
    assert config.app_env == "production"
    assert config.debug is True
    assert config.log_level == "DEBUG"


def test_settings_env_var_override() -> None:
    """Verify environment variables correctly override default settings."""
    with patch.dict(os.environ, {"APP_ENV": "staging", "DEBUG": "true", "LOG_LEVEL": "WARNING"}):
        config = get_settings()
        assert config.app_env == "staging"
        assert config.debug is True
        assert config.log_level == "WARNING"


def test_database_settings_url() -> None:
    """Verify PostgreSQL database URL construction."""
    config = Settings(
        postgres_host="db.internal",
        postgres_port=5433,
        postgres_user="admin",
        postgres_password="secretpassword",
        postgres_db="jobhunter_prod",
    )
    assert (
        config.sqlalchemy_database_url
        == "postgresql+psycopg://admin:secretpassword@db.internal:5433/jobhunter_prod"
    )
