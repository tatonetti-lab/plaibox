# src/plaibox/cli.py
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

import click
import yaml

from plaibox.config import load_config, DEFAULT_CONFIG_PATH
from plaibox.metadata import write_metadata, read_metadata
from plaibox.project import slugify, make_sandbox_dirname, discover_projects, detect_tech, ensure_spaces, fuzzy_match, write_gitignore
from plaibox.shell import shell_init_script


@click.group()
def cli():
    """Plaibox — lifecycle manager for vibe-coded projects."""
    pass


@cli.command()
@click.argument("description", required=False)
@click.option("--python", "create_venv", is_flag=True, help="Create a Python virtual environment (.venv).")
@click.option("--config", "config_path", default=None, help="Path to config file.")
def new(description: str | None, create_venv: bool, config_path: str | None):
    """Create a new sandbox project."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    root = Path(cfg["root"]).expanduser()
    ensure_spaces(root)

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

    if create_venv:
        meta["tech"] = ["python"]

    write_metadata(project_dir, meta)

    subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)
    write_gitignore(project_dir)

    if create_venv:
        subprocess.run(
            ["python3", "-m", "venv", ".venv"],
            cwd=project_dir,
            capture_output=True,
        )

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

    click.echo(f"  {'ID':6s}  {'STATUS':8s}  {'CREATED':10s}  {'MODIFIED':10s}  {'NAME':25s}  DESCRIPTION")
    click.echo(f"  {'─' * 6}  {'─' * 8}  {'─' * 10}  {'─' * 10}  {'─' * 25}  {'─' * 20}")

    for p in projects:
        meta = p["meta"]
        tech = detect_tech(p["path"])
        tech_str = ", ".join(tech) if tech else "-"
        tags_str = ", ".join(meta.get("tags", [])) if meta.get("tags") else ""
        modified = _last_modified(p["path"])

        click.echo(
            f"  {p['id']}  {meta['status']:8s}  {meta['created']}  "
            f"{modified}  {meta['name']:25s}  {meta['description']}"
        )
        detail_parts = [f"tech: {tech_str}"]
        if tags_str:
            detail_parts.append(f"tags: {tags_str}")
        click.echo(f"        {' | '.join(detail_parts)}")

    click.echo("")
    click.echo("Open a project: plaibox open <name-or-id>")


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
    meta["remote"] = None
    write_metadata(new_path, meta)

    click.echo(f"Promoted to {new_path}")

    # Offer to create a GitHub repo
    if click.confirm("Create a GitHub repo?", default=True):
        visibility = click.prompt(
            "Visibility",
            type=click.Choice(["private", "public"]),
            default="private",
        )
        result = subprocess.run(
            ["gh", "repo", "create", new_name, f"--{visibility}", "--source", str(new_path), "--push"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            # Extract the repo URL from gh output
            repo_url = result.stdout.strip()
            meta["remote"] = repo_url
            write_metadata(new_path, meta)
            click.echo(f"GitHub repo created: {repo_url}")
        else:
            click.echo(f"Failed to create repo: {result.stderr.strip()}", err=True)
            click.echo("You can create one later with: gh repo create")
    else:
        click.echo("Skipped. You can add a remote later with: gh repo create")


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

    # Check for exact ID match first
    for p in projects:
        if p["id"] == query_lower:
            click.echo(str(p["path"]))
            return

    matches = fuzzy_match(query, projects)

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


@cli.command()
@click.option("--save", "resume_cmd", default=None, help="Save a session resume command.")
@click.option("--dir", "project_dir", default=".", help="Project directory.")
def session(resume_cmd: str | None, project_dir: str):
    """Show or save the AI session resume command for a project."""
    project_path = Path(project_dir).resolve()
    meta = read_metadata(project_path)
    if meta is None:
        click.echo("Error: not a plaibox project (no .plaibox.yaml found).", err=True)
        raise SystemExit(1)

    if resume_cmd:
        meta["session"] = resume_cmd
        write_metadata(project_path, meta)
        click.echo(f"Session saved: {resume_cmd}")
    else:
        saved = meta.get("session")
        if saved:
            click.echo(f"Resume session: {saved}")
        else:
            click.echo("No session saved for this project.")


@cli.command("import")
@click.argument("path", default=".", type=click.Path(exists=False))
@click.option("--project", "as_project", is_flag=True, help="Import directly as a project (skip sandbox).")
@click.option("--config", "config_path", default=None, help="Path to config file.")
def import_cmd(path: str, as_project: bool, config_path: str | None):
    """Import an existing project directory into plaibox."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    root = Path(cfg["root"]).expanduser()
    ensure_spaces(root)

    source = Path(path).resolve()

    if not source.exists():
        click.echo(f"Error: {source} does not exist.", err=True)
        raise SystemExit(1)

    if not source.is_dir():
        click.echo(f"Error: {source} is not a directory.", err=True)
        raise SystemExit(1)

    # Refuse to import something already inside plaibox root
    try:
        source.relative_to(root.resolve())
        click.echo("Error: already inside plaibox root. Use promote/archive instead.", err=True)
        raise SystemExit(1)
    except ValueError:
        pass  # Not inside root — good

    # Check for existing metadata
    existing_meta = read_metadata(source)

    if existing_meta:
        description = existing_meta.get("description", source.name)
    else:
        description = click.prompt("Description", default=source.name)

    # Determine destination space
    if as_project:
        space = "p"
    else:
        if existing_meta and existing_meta.get("status") == "project":
            space = "p"
        else:
            space = click.prompt("Import as: [s]andbox or [p]roject", type=click.Choice(["s", "p"]))

    today = date.today()

    if space == "s":
        dirname = make_sandbox_dirname(description, today)
        dest = root / "sandbox" / dirname
        status = "sandbox"
        name = slugify(description)
    else:
        name = click.prompt("Project name", default=slugify(description))
        dest = root / "projects" / name
        status = "project"

    if dest.exists():
        click.echo(f"Error: {dest} already exists.", err=True)
        raise SystemExit(1)

    shutil.move(str(source), str(dest))

    # Write metadata (preserve existing if present)
    if existing_meta:
        existing_meta["status"] = status
        if space == "p":
            existing_meta["name"] = name
        write_metadata(dest, existing_meta)
    else:
        meta = {
            "name": name,
            "description": description,
            "status": status,
            "created": today.isoformat(),
            "tags": [],
            "tech": detect_tech(dest),
        }
        write_metadata(dest, meta)

    # Init git if not already a repo
    if not (dest / ".git").exists():
        subprocess.run(["git", "init"], cwd=dest, capture_output=True)

    write_gitignore(dest)

    # Offer to create venv if Python project without one
    if not (dest / ".venv").exists() and detect_tech(dest) and "python" in detect_tech(dest):
        if click.confirm("Python project detected. Create a .venv?", default=True):
            subprocess.run(
                ["python3", "-m", "venv", ".venv"],
                cwd=dest,
                capture_output=True,
            )

    click.echo(str(dest))


@cli.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--git-only", is_flag=True, help="Only show directories that contain a git repo.")
@click.option("--config", "config_path", default=None, help="Path to config file.")
def scan(directory: str, git_only: bool, config_path: str | None):
    """Scan a directory for existing projects to import into plaibox."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    root = Path(cfg["root"]).expanduser().resolve()
    ensure_spaces(root)

    scan_dir = Path(directory).resolve()

    # Load ignore list
    ignore_path = (Path(config_path).parent if config_path else DEFAULT_CONFIG_PATH.parent) / "scan-ignore"
    ignored = set()
    if ignore_path.exists():
        ignored = {line.strip() for line in ignore_path.read_text().splitlines() if line.strip()}

    # Collect candidate directories (one level deep, non-hidden)
    candidates = []
    for child in sorted(scan_dir.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        resolved = str(child.resolve())
        # Skip if already inside plaibox root
        try:
            child.resolve().relative_to(root)
            continue
        except ValueError:
            pass
        # Skip if in ignore list
        if resolved in ignored:
            continue
        # Skip if already a plaibox project (has metadata)
        if read_metadata(child) is not None:
            continue
        # Filter by git if requested
        if git_only and not (child / ".git").exists():
            continue
        candidates.append(child)

    if not candidates:
        click.echo("No new projects found to import.")
        return

    click.echo(f"Found {len(candidates)} director{'y' if len(candidates) == 1 else 'ies'} in {scan_dir}\n")

    imported = 0
    for child in candidates:
        has_git = (child / ".git").exists()
        tech = detect_tech(child)
        tech_str = ", ".join(tech) if tech else "unknown"
        modified = _last_modified(child)

        click.echo(f"  {child}/")
        click.echo(f"  {'git' if has_git else 'no git'}  |  tech: {tech_str}  |  modified: {modified}")
        action = click.prompt("  [i]mport / [s]kip / [n]ever", type=click.Choice(["i", "s", "n"]))

        if action == "i":
            description = click.prompt("  Description", default=child.name)
            space = click.prompt("  Import as: [s]andbox or [p]roject", type=click.Choice(["s", "p"]))

            today = date.today()
            if space == "s":
                dirname = make_sandbox_dirname(description, today)
                dest = root / "sandbox" / dirname
                status = "sandbox"
                name = slugify(description)
            else:
                name = click.prompt("  Project name", default=slugify(description))
                dest = root / "projects" / name
                status = "project"

            if dest.exists():
                click.echo(f"  Error: {dest} already exists. Skipping.\n")
                continue

            shutil.move(str(child), str(dest))

            meta = {
                "name": name,
                "description": description,
                "status": status,
                "created": today.isoformat(),
                "tags": [],
                "tech": detect_tech(dest),
            }
            write_metadata(dest, meta)

            if not (dest / ".git").exists():
                subprocess.run(["git", "init"], cwd=dest, capture_output=True)

            write_gitignore(dest)

            # Offer venv for Python projects
            if not (dest / ".venv").exists() and "python" in detect_tech(dest):
                if click.confirm("  Python project detected. Create a .venv?", default=True):
                    subprocess.run(["python3", "-m", "venv", ".venv"], cwd=dest, capture_output=True)

            click.echo(f"  Imported to {dest}\n")
            imported += 1
        elif action == "n":
            ignored.add(str(child.resolve()))
            click.echo(f"  Ignored permanently.\n")
        else:
            click.echo(f"  Skipped.\n")

    # Save updated ignore list
    if ignored:
        ignore_path.parent.mkdir(parents=True, exist_ok=True)
        ignore_path.write_text("\n".join(sorted(ignored)) + "\n")

    click.echo(f"Imported {imported} project{'s' if imported != 1 else ''}.")


@cli.command("init-shell")
def init_shell():
    """Print shell function for cd integration. Add to your .zshrc/.bashrc:

    eval "$(plaibox init-shell)"
    """
    click.echo(shell_init_script())
