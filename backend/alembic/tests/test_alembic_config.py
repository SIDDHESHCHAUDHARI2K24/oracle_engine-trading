"""Tests for Alembic configuration and environment."""

from pathlib import Path

from alembic.config import Config


def _get_config() -> Config:
    """Return an Alembic Config pointing at the local alembic.ini."""
    ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    config = Config(str(ini_path))
    return config


def test_alembic_ini_loads() -> None:
    """alembic.ini should be loadable and have a script_location."""
    config = _get_config()
    script_location = config.get_main_option("script_location")
    assert script_location


def test_alembic_env_imports() -> None:
    """The Alembic env module should be importable."""
    config = _get_config()
    script_location = Path(config.get_main_option("script_location")).resolve()
    env_path = script_location / "env.py"
    assert env_path.exists()

