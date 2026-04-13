from pathlib import Path
import yaml


DEFAULT_CONFIG = {
    "root": str(Path.home() / "plaibox"),
    "stale_days": 30,
}

DEFAULT_CONFIG_PATH = Path.home() / ".plaibox" / "config.yaml"


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict:
    """Load config from disk, creating default if missing."""
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False)
    return dict(DEFAULT_CONFIG)


def save_config(config: dict, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Write config dict to disk."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def is_sync_enabled(config: dict) -> bool:
    """Check if sync is configured and enabled."""
    sync = config.get("sync")
    if sync is None:
        return False
    return sync.get("enabled", False)


def get_sync_config(config: dict) -> dict | None:
    """Get the sync config section, or None if not configured."""
    sync = config.get("sync")
    if sync is None or not sync.get("enabled", False):
        return None
    return sync
