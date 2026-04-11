import pytest
from pathlib import Path


@pytest.fixture
def tmp_plaibox_root(tmp_path):
    """A temporary plaibox root directory with sandbox/projects/archive."""
    root = tmp_path / "plaibox"
    root.mkdir()
    (root / "sandbox").mkdir()
    (root / "projects").mkdir()
    (root / "archive").mkdir()
    return root


@pytest.fixture
def tmp_config_dir(tmp_path):
    """A temporary ~/.plaibox config directory."""
    config_dir = tmp_path / ".plaibox"
    config_dir.mkdir()
    return config_dir
