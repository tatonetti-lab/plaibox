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
