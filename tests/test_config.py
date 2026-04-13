from pathlib import Path
import yaml

from plaibox.config import load_config, save_config, is_sync_enabled, get_sync_config, DEFAULT_CONFIG


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


def test_save_config_writes_yaml(tmp_path):
    config_path = tmp_path / "config.yaml"
    config = {"root": "/tmp/plaibox", "stale_days": 30}
    save_config(config, config_path)

    assert config_path.exists()
    loaded = load_config(config_path)
    assert loaded["root"] == "/tmp/plaibox"
    assert loaded["stale_days"] == 30


def test_is_sync_enabled_false_by_default(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("root: /tmp/plaibox\nstale_days: 30\n")
    cfg = load_config(config_path)
    assert is_sync_enabled(cfg) is False


def test_is_sync_enabled_true_when_configured(tmp_path):
    import yaml
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "root": "/tmp/plaibox",
        "stale_days": 30,
        "sync": {
            "enabled": True,
            "repo": "git@github.com:user/plaibox-sync.git",
            "sandbox_repos": ["git@github.com:user/plaibox-sandbox.git"],
            "sandbox_branch_limit": 50,
            "machine_name": "test-machine",
        },
    }))
    cfg = load_config(config_path)
    assert is_sync_enabled(cfg) is True


def test_get_sync_config_returns_none_when_not_configured(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("root: /tmp/plaibox\nstale_days: 30\n")
    cfg = load_config(config_path)
    assert get_sync_config(cfg) is None


def test_get_sync_config_returns_dict_when_configured(tmp_path):
    import yaml
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "root": "/tmp/plaibox",
        "stale_days": 30,
        "sync": {
            "enabled": True,
            "repo": "git@github.com:user/plaibox-sync.git",
            "sandbox_repos": ["git@github.com:user/plaibox-sandbox.git"],
            "sandbox_branch_limit": 50,
            "machine_name": "test-machine",
        },
    }))
    cfg = load_config(config_path)
    sync_cfg = get_sync_config(cfg)
    assert sync_cfg["repo"] == "git@github.com:user/plaibox-sync.git"
    assert sync_cfg["machine_name"] == "test-machine"
