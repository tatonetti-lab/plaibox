# src/plaibox/cli.py
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

import click
import yaml

from plaibox.config import load_config, DEFAULT_CONFIG_PATH
from plaibox.metadata import write_metadata, read_metadata
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


@cli.command()
@click.option("--config", "config_path", default=None, help="Path to config file.")
@click.option("--dir", "project_dir", default=".", help="Project directory to promote.")
def promote(config_path: str | None, project_dir: str):
    """Promote a sandbox project to projects."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    root = Path(cfg["root"]).expanduser()
    project_path = Path(project_dir).resolve()

    meta = read_metadata(project_path)
    if meta is None:
        click.echo("Error: not a plaibox project (no .plaibox.yaml found).", err=True)
        raise SystemExit(1)

    if meta["status"] != "sandbox":
        click.echo("Error: can only promote sandbox projects.", err=True)
        raise SystemExit(1)

    new_name = click.prompt("Project name")
    new_path = root / "projects" / new_name

    if new_path.exists():
        click.echo(f"Error: {new_path} already exists.", err=True)
        raise SystemExit(1)

    shutil.move(str(project_path), str(new_path))

    meta["status"] = "project"
    meta["name"] = new_name
    write_metadata(new_path, meta)

    click.echo(f"Promoted to {new_path}")


@cli.command()
@click.option("--config", "config_path", default=None, help="Path to config file.")
@click.option("--dir", "project_dir", default=".", help="Project directory to archive.")
def archive(config_path: str | None, project_dir: str):
    """Archive a project."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    root = Path(cfg["root"]).expanduser()
    project_path = Path(project_dir).resolve()

    meta = read_metadata(project_path)
    if meta is None:
        click.echo("Error: not a plaibox project (no .plaibox.yaml found).", err=True)
        raise SystemExit(1)

    new_path = root / "archive" / project_path.name

    if new_path.exists():
        click.echo(f"Error: {new_path} already exists in archive.", err=True)
        raise SystemExit(1)

    shutil.move(str(project_path), str(new_path))

    meta["status"] = "archived"
    write_metadata(new_path, meta)

    click.echo(f"Archived to {new_path}")


@cli.command()
@click.option("--config", "config_path", default=None, help="Path to config file.")
@click.option("--dir", "project_dir", default=".", help="Project directory to delete.")
def delete(config_path: str | None, project_dir: str):
    """Permanently delete an archived project."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    project_path = Path(project_dir).resolve()

    meta = read_metadata(project_path)
    if meta is None:
        click.echo("Error: not a plaibox project (no .plaibox.yaml found).", err=True)
        raise SystemExit(1)

    if meta["status"] != "archived":
        click.echo("Error: can only delete archived projects. Archive it first.", err=True)
        raise SystemExit(1)

    if not click.confirm(f"Permanently delete '{meta['name']}'?"):
        click.echo("Cancelled.")
        return

    shutil.rmtree(project_path)
    click.echo(f"Deleted {meta['name']}.")


@cli.command("open")
@click.argument("query")
@click.option("--config", "config_path", default=None, help="Path to config file.")
def open_cmd(query: str, config_path: str | None):
    """Find a project by name or description and print its path."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    root = Path(cfg["root"]).expanduser()

    projects = discover_projects(root)
    query_lower = query.lower()

    matches = []
    for p in projects:
        name = p["meta"].get("name", "").lower()
        desc = p["meta"].get("description", "").lower()
        if query_lower in name or query_lower in desc:
            matches.append(p)

    if not matches:
        click.echo(f"No project matching '{query}'.")
        raise SystemExit(1)

    if len(matches) == 1:
        click.echo(str(matches[0]["path"]))
        return

    click.echo(f"Multiple matches for '{query}':")
    for i, m in enumerate(matches, 1):
        click.echo(f"  {i}. {m['meta']['name']} — {m['meta']['description']}")

    choice = click.prompt("Which one?", type=int)
    if 1 <= choice <= len(matches):
        click.echo(str(matches[choice - 1]["path"]))
    else:
        click.echo("Invalid choice.")
        raise SystemExit(1)


@cli.command()
@click.option("--config", "config_path", default=None, help="Path to config file.")
def tidy(config_path: str | None):
    """Interactively triage stale sandbox projects."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    root = Path(cfg["root"]).expanduser()
    stale_days = cfg["stale_days"]

    projects = discover_projects(root)
    cutoff = date.today() - timedelta(days=stale_days)

    stale = [
        p for p in projects
        if p["space"] == "sandbox" and _last_modified(p["path"]) < cutoff
    ]

    if not stale:
        click.echo("No stale sandbox projects. Nice!")
        return

    click.echo(f"Found {len(stale)} stale sandbox project(s):\n")

    for p in stale:
        meta = p["meta"]
        click.echo(f"  {meta['name']} — {meta['description']}")
        click.echo(f"  Created: {meta['created']}  |  Last modified: {_last_modified(p['path'])}")
        action = click.prompt("  [p]romote / [a]rchive / [s]kip", type=click.Choice(["p", "a", "s"]))

        if action == "p":
            new_name = click.prompt("  Project name")
            new_path = root / "projects" / new_name
            if new_path.exists():
                click.echo(f"  Error: {new_path} already exists. Skipping.")
                continue
            shutil.move(str(p["path"]), str(new_path))
            meta["status"] = "project"
            meta["name"] = new_name
            write_metadata(new_path, meta)
            click.echo(f"  Promoted to {new_path}\n")
        elif action == "a":
            new_path = root / "archive" / p["path"].name
            shutil.move(str(p["path"]), str(new_path))
            meta["status"] = "archived"
            write_metadata(new_path, meta)
            click.echo(f"  Archived.\n")
        else:
            click.echo(f"  Skipped.\n")
