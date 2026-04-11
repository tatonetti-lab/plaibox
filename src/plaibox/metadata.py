from pathlib import Path
import yaml


METADATA_FILENAME = ".plaibox.yaml"


def write_metadata(project_dir: Path, meta: dict) -> None:
    """Write metadata dict to .plaibox.yaml in the given directory."""
    path = project_dir / METADATA_FILENAME
    with open(path, "w") as f:
        yaml.dump(meta, f, default_flow_style=False, sort_keys=False)


def read_metadata(project_dir: Path) -> dict | None:
    """Read .plaibox.yaml from the given directory. Returns None if missing."""
    path = project_dir / METADATA_FILENAME
    if not path.exists():
        return None
    with open(path) as f:
        return yaml.safe_load(f)
