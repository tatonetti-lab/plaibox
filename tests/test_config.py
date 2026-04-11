from pathlib import Path
import yaml

from plaibox.config import load_config, DEFAULT_CONFIG


def test_load_config_creates_default_when_missing(tmp_config_dir):
    config_path = tmp_config_dir / "config.yaml"
    config = load_config(config_path)

    assert config["root"] == str(Path.home() / "plaibox")
    assert config["stale_days"] == 30
    assert config_path.exists()


def test_load_config_reads_existing(tmp_config_dir):
    config_path = tmp_config_dir / "config.yaml"
    config_path.write_text(yaml.dump({"root": "/custom/path", "stale_days": 14}))

    config = load_config(config_path)

    assert config["root"] == "/custom/path"
    assert config["stale_days"] == 14


def test_default_config_has_required_keys():
    assert "root" in DEFAULT_CONFIG
    assert "stale_days" in DEFAULT_CONFIG
