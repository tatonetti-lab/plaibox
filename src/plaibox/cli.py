# src/plaibox/cli.py
import subprocess
from datetime import date, timedelta
from pathlib import Path

import click
import yaml

from plaibox.config import load_config, DEFAULT_CONFIG_PATH
from plaibox.metadata import write_metadata
from plaibox.project import slugify, make_sandbox_dirname, discover_projects, detect_tech


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


@cli.command("ls")
@click.argument("space", required=False, type=click.Choice(["sandbox", "projects", "archive"]))
@click.option("--stale", is_flag=True, help="Show only sandbox projects older than stale_days.")
@click.option("--config", "config_path", default=None, help="Path to config file.")
def ls_cmd(space: str | None, stale: bool, config_path: str | None):
    """List projects."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    root = Path(cfg["root"]).expanduser()
    stale_days = cfg["stale_days"]

    projects = discover_projects(root)

    if space:
        projects = [p for p in projects if p["space"] == space]

    if stale:
        projects = [p for p in projects if p["space"] == "sandbox"]
        cutoff = date.today() - timedelta(days=stale_days)
        projects = [p for p in projects if _last_modified(p["path"]) < cutoff]

    if not projects:
        click.echo("No projects found.")
        return

    for p in projects:
        tech = detect_tech(p["path"])
        tech_str = f" [{', '.join(tech)}]" if tech else ""
        click.echo(f"  {p['meta']['status']:8s}  {p['meta']['name']:30s}  {p['meta']['description']}{tech_str}")


def _last_modified(path: Path) -> date:
    """Get the last modification date of a directory."""
    import os
    mtime = os.path.getmtime(path)
    return date.fromtimestamp(mtime)
