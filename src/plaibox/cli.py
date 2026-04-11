# src/plaibox/cli.py
import subprocess
from datetime import date
from pathlib import Path

import click
import yaml

from plaibox.config import load_config, DEFAULT_CONFIG_PATH
from plaibox.metadata import write_metadata
from plaibox.project import slugify, make_sandbox_dirname


@click.group()
def cli():
    """Plaibox — lifecycle manager for vibe-coded projects."""
    pass


@cli.command()
@click.argument("description", required=False)
@click.option("--config", "config_path", default=None, help="Path to config file.")
def new(description: str | None, config_path: str | None):
    """Create a new sandbox project."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    root = Path(cfg["root"]).expanduser()

    if not description:
        description = click.prompt("Project description")

    today = date.today()
    dirname = make_sandbox_dirname(description, today)
    project_dir = root / "sandbox" / dirname
    project_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "name": slugify(description),
        "description": description,
        "status": "sandbox",
        "created": today.isoformat(),
        "tags": [],
        "tech": [],
    }
    write_metadata(project_dir, meta)

    subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)

    click.echo(str(project_dir))
