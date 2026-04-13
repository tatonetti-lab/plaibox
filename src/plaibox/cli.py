# src/plaibox/cli.py
import shutil
import socket
import subprocess
from datetime import date, timedelta
from pathlib import Path

import click
import yaml

from plaibox.config import load_config, save_config, is_sync_enabled, get_sync_config, DEFAULT_CONFIG_PATH
from plaibox.metadata import write_metadata, read_metadata
from plaibox.project import slugify, make_sandbox_dirname, discover_projects, detect_tech, ensure_spaces, fuzzy_match, write_gitignore
from plaibox.shell import shell_init_script
from plaibox.sync import (
    ensure_sync_repo_cloned, auto_push, pull_sync_repo,
    read_remote_projects, remove_project_meta,
    push_sandbox_branch, clone_sandbox_branch, delete_sandbox_branch,
)


@click.group()
def cli():
    """Plaibox — lifecycle manager for vibe-coded projects."""
    pass


@cli.command()
@click.argument("description", required=False)
@click.option("--python", "create_venv", is_flag=True, help="Create a Python virtual environment (.venv).")
@click.option("--private", is_flag=True, help="Mark project as private (code never pushed to remotes).")
@click.option("--config", "config_path", default=None, help="Path to config file.")
def new(description: str | None, create_venv: bool, private: bool, config_path: str | None):
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

    from plaibox.project import generate_project_id
    pid = generate_project_id()

    meta = {
        "id": pid,
        "name": slugify(description),
        "description": description,
        "status": "sandbox",
        "created": today.isoformat(),
        "tags": [],
        "tech": [],
    }

    if private:
        meta["private"] = True

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

    # Auto-push to sync if enabled
    if is_sync_enabled(cfg):
        sync_cfg = get_sync_config(cfg)
        from plaibox.sync import get_active_sandbox_repo
        sandbox_repo = None
        branch_name = None

        if not meta.get("private"):
            sandbox_repo = get_active_sandbox_repo(sync_cfg)
            branch_name = f"{slugify(description)}-{pid}"

            # Push code to sandbox repo
            if sandbox_repo:
                # Need at least one commit to push
                subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
                subprocess.run(
                    ["git", "commit", "-m", "plaibox: initial project"],
                    cwd=project_dir, capture_output=True,
                )
                push_sandbox_branch(project_dir, sandbox_repo, branch_name)
                # Save sandbox info to local metadata
                meta["sandbox_repo"] = sandbox_repo
                meta["sandbox_branch"] = branch_name
                write_metadata(project_dir, meta)

        # Push metadata to sync repo
        auto_push(
            project_id=pid,
            local_meta=meta,
            space="sandbox",
            remote=None,
            sandbox_repo=sandbox_repo,
            sync_config=sync_cfg,
            config_dir=Path(config_path).parent if config_path else DEFAULT_CONFIG_PATH.parent,
        )


@cli.command("ls")
@click.argument("space", required=False, type=click.Choice(["sandbox", "projects", "archive"]))
@click.option("--stale", is_flag=True, help="Show only sandbox projects older than stale_days.")
@click.option("--config", "config_path", default=None, help="Path to config file.")
def ls_cmd(space: str | None, stale: bool, config_path: str | None):
    """List projects."""
    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    cfg = load_config(cfg_path)
    root = Path(cfg["root"]).expanduser()
    stale_days = cfg["stale_days"]

    projects = discover_projects(root)

    # Load remote-only projects if sync is enabled
    remote_only = []
    if is_sync_enabled(cfg):
        registry_path = cfg_path.parent / "remote-registry.yaml"
        if registry_path.exists():
            with open(registry_path) as f:
                registry = yaml.safe_load(f) or {}
            local_ids = {p["id"] for p in projects}
            for rid, rmeta in registry.items():
                if rid not in local_ids:
                    remote_only.append({"id": rid, "meta": rmeta, "space": "remote", "path": None})

    all_projects = projects + remote_only

    if space:
        all_projects = [p for p in all_projects if p["space"] == space]

    if stale:
        all_projects = [p for p in all_projects if p["space"] == "sandbox"]
        cutoff = date.today() - timedelta(days=stale_days)
        all_projects = [p for p in all_projects if p.get("path") and _last_modified(p["path"]) < cutoff]

    if not all_projects:
        click.echo("No projects found.")
        _show_sync_hint(cfg)
        return

    click.echo(f"  {'ID':6s}  {'STATUS':8s}  {'CREATED':10s}  {'MODIFIED':10s}  {'NAME':25s}  DESCRIPTION")
    click.echo(f"  {'─' * 6}  {'─' * 8}  {'─' * 10}  {'─' * 10}  {'─' * 25}  {'─' * 20}")

    for p in all_projects:
        meta = p["meta"]
        if p["path"] is not None:
            tech = detect_tech(p["path"])
            modified = _last_modified(p["path"])
        else:
            tech = meta.get("tech", [])
            modified = meta.get("updated", "-")[:10] if meta.get("updated") else "-"
        tech_str = ", ".join(tech) if tech else "-"
        tags_str = ", ".join(meta.get("tags", [])) if meta.get("tags") else ""

        if p["space"] == "remote" and meta.get("private") and not meta.get("remote") and not meta.get("sandbox_repo"):
            status_display = "private"
        elif p["space"] == "remote":
            status_display = "remote"
        elif meta.get("private"):
            status_display = meta["status"] + "*"
        else:
            status_display = meta["status"]

        click.echo(
            f"  {p['id']}  {status_display:8s}  {meta['created']}  "
            f"{modified}  {meta['name']:25s}  {meta['description']}"
        )
        detail_parts = [f"tech: {tech_str}"]
        if tags_str:
            detail_parts.append(f"tags: {tags_str}")
        if p["space"] == "remote":
            detail_parts.append(f"on: {meta.get('machine', '?')}")
        click.echo(f"        {' | '.join(detail_parts)}")

    click.echo("")
    click.echo("Open a project: plaibox open <name-or-id>")
    _show_sync_hint(cfg)


def _show_sync_hint(cfg: dict) -> None:
    """Show a one-time hint about sync if not configured or dismissed."""
    if is_sync_enabled(cfg):
        return
    if cfg.get("sync_hint_dismissed"):
        return
    click.echo("Tip: Use plaibox across devices with 'plaibox sync init'")


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

    # Get project ID before updating metadata
    from plaibox.project import project_id
    pid = meta.get("id") or project_id(new_path)

    meta["status"] = "project"
    meta["name"] = new_name
    meta["remote"] = None
    write_metadata(new_path, meta)

    click.echo(f"Promoted to {new_path}")

    # Clean up sandbox branch
    sandbox_repo = meta.get("sandbox_repo")
    sandbox_branch = meta.get("sandbox_branch")
    if sandbox_repo and sandbox_branch:
        try:
            delete_sandbox_branch(sandbox_repo, sandbox_branch)
        except Exception:
            pass

    # Handle remote setup
    if meta.get("private"):
        # Private project — don't offer gh repo create
        click.echo("This project is private. Enter a remote URL to push code to an approved remote.")
        remote_url = click.prompt("Remote URL (or press Enter to skip)", default="", show_default=False)
        if remote_url:
            subprocess.run(
                ["git", "remote", "add", "origin", remote_url],
                cwd=new_path, capture_output=True,
            )
            subprocess.run(
                ["git", "push", "-u", "origin", "HEAD"],
                cwd=new_path, capture_output=True,
            )
            meta["remote"] = remote_url
            write_metadata(new_path, meta)
            click.echo(f"Pushed to {remote_url}")
        else:
            click.echo("Skipped. You can add a remote later.")
    else:
        # Normal project — offer GitHub repo creation
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

    # Auto-push to sync if enabled
    if is_sync_enabled(cfg):
        sync_cfg = get_sync_config(cfg)
        auto_push(
            project_id=pid,
            local_meta=meta,
            space="projects",
            remote=meta.get("remote"),
            sandbox_repo=None,
            sync_config=sync_cfg,
            config_dir=Path(config_path).parent if config_path else DEFAULT_CONFIG_PATH.parent,
        )


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

    # Get project ID before updating metadata
    from plaibox.project import project_id
    pid = meta.get("id") or project_id(new_path)

    meta["status"] = "archived"
    write_metadata(new_path, meta)

    click.echo(f"Archived to {new_path}")

    # Auto-push to sync if enabled
    if is_sync_enabled(cfg):
        sync_cfg = get_sync_config(cfg)
        auto_push(
            project_id=pid,
            local_meta=meta,
            space="archive",
            remote=meta.get("remote"),
            sandbox_repo=None,
            sync_config=sync_cfg,
            config_dir=Path(config_path).parent if config_path else DEFAULT_CONFIG_PATH.parent,
        )


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

    # Get ID before deletion
    from plaibox.project import project_id
    pid = meta.get("id") or project_id(project_path)

    shutil.rmtree(project_path)

    # Remove from sync if enabled
    if is_sync_enabled(cfg):
        sync_cfg = get_sync_config(cfg)
        try:
            repo_path = ensure_sync_repo_cloned(sync_cfg,
                Path(config_path).parent if config_path else DEFAULT_CONFIG_PATH.parent)
            pull_sync_repo(repo_path)
            remove_project_meta(pid, repo_path)
        except Exception:
            pass

    click.echo(f"Deleted {meta['name']}.")


@cli.command("open")
@click.argument("query")
@click.option("--config", "config_path", default=None, help="Path to config file.")
def open_cmd(query: str, config_path: str | None):
    """Find a project by name or description and print its path."""
    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    cfg = load_config(cfg_path)
    root = Path(cfg["root"]).expanduser()

    projects = discover_projects(root)
    query_lower = query.lower()

    # Check for exact ID match first (local)
    for p in projects:
        if p["id"] == query_lower:
            click.echo(str(p["path"]))
            return

    # Try fuzzy match on local projects
    matches = fuzzy_match(query, projects)

    if len(matches) == 1:
        click.echo(str(matches[0]["path"]))
        return

    if len(matches) > 1:
        click.echo(f"Multiple matches for '{query}':")
        for i, m in enumerate(matches, 1):
            click.echo(f"  {i}. {m['meta']['name']} — {m['meta']['description']}")
        choice = click.prompt("Which one?", type=int)
        if 1 <= choice <= len(matches):
            click.echo(str(matches[choice - 1]["path"]))
        else:
            click.echo("Invalid choice.")
            raise SystemExit(1)
        return

    # No local match — check remote registry
    if is_sync_enabled(cfg):
        registry_path = cfg_path.parent / "remote-registry.yaml"
        if registry_path.exists():
            with open(registry_path) as f:
                registry = yaml.safe_load(f) or {}

            local_ids = {p["id"] for p in projects}
            remote_projects = []
            for rid, rmeta in registry.items():
                if rid not in local_ids:
                    remote_projects.append({"id": rid, "meta": rmeta, "space": "remote", "path": None})

            # Check ID match
            for rp in remote_projects:
                if rp["id"] == query_lower:
                    _clone_remote_project(rp, cfg, root)
                    return

            # Fuzzy match on remote projects
            remote_matches = fuzzy_match(query, remote_projects)
            if len(remote_matches) == 1:
                _clone_remote_project(remote_matches[0], cfg, root)
                return
            elif len(remote_matches) > 1:
                click.echo(f"Multiple remote matches for '{query}':")
                for i, m in enumerate(remote_matches, 1):
                    click.echo(f"  {i}. {m['meta']['name']} — {m['meta']['description']} (on {m['meta'].get('machine', '?')})")
                choice = click.prompt("Which one?", type=int)
                if 1 <= choice <= len(remote_matches):
                    _clone_remote_project(remote_matches[choice - 1], cfg, root)
                else:
                    click.echo("Invalid choice.")
                    raise SystemExit(1)
                return

    click.echo(f"No project matching '{query}'.")
    raise SystemExit(1)


def _clone_remote_project(remote_project: dict, cfg: dict, root: Path) -> None:
    """Clone a remote-only project locally."""
    meta = remote_project["meta"]
    name = meta["name"]
    space = meta.get("space", "projects")

    remote_url = meta.get("remote")
    sandbox_repo = meta.get("sandbox_repo")

    if not remote_url and not sandbox_repo:
        if meta.get("private"):
            click.echo(f"Project '{name}' is private on {meta.get('machine', 'another machine')}. No remote code available.")
        else:
            click.echo(f"Project '{name}' exists on {meta.get('machine', 'another machine')} but has no remote URL.")
        raise SystemExit(1)

    click.echo(f"Project '{name}' is on {meta.get('machine', 'another machine')}.")
    if not click.confirm("Clone it locally?"):
        click.echo("Cancelled.")
        return

    if space == "sandbox":
        dirname = f"{meta['created']}_{slugify(meta['description'])}"
        dest = root / "sandbox" / dirname
    else:
        dest = root / space / name

    if dest.exists():
        click.echo(f"Error: {dest} already exists.", err=True)
        raise SystemExit(1)

    if sandbox_repo:
        # Clone from sandbox repo branch
        branch_name = f"{slugify(meta['description'])}-{remote_project['id']}"
        success = clone_sandbox_branch(sandbox_repo, branch_name, dest)
    else:
        # Clone from project's own repo
        result = subprocess.run(
            ["git", "clone", remote_url, str(dest)],
            capture_output=True, text=True,
        )
        success = result.returncode == 0

    if not success:
        click.echo(f"Failed to clone '{name}'.", err=True)
        raise SystemExit(1)

    # Write local metadata
    write_metadata(dest, {
        "id": remote_project["id"],  # preserve the sync ID
        "name": meta["name"],
        "description": meta["description"],
        "status": meta["status"],
        "created": meta["created"],
        "tags": meta.get("tags", []),
        "tech": meta.get("tech", []),
        "remote": remote_url,
    })

    # Auto-push so the sync repo knows this machine has the project
    if is_sync_enabled(cfg):
        sync_cfg = get_sync_config(cfg)
        if sync_cfg:
            auto_push(
                project_id=remote_project["id"],
                local_meta={"name": meta["name"], "description": meta["description"],
                            "status": meta["status"], "created": meta["created"],
                            "tags": meta.get("tags", []), "tech": meta.get("tech", [])},
                space=space,
                remote=remote_url,
                sandbox_repo=sandbox_repo,
                sync_config=sync_cfg,
                config_dir=DEFAULT_CONFIG_PATH.parent,
            )

    click.echo(str(dest))


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

    from plaibox.project import generate_project_id
    # Generate a stable ID
    new_id = generate_project_id()

    # Write metadata (preserve existing if present)
    if existing_meta:
        existing_meta["id"] = existing_meta.get("id") or new_id
        existing_meta["status"] = status
        if space == "p":
            existing_meta["name"] = name
        write_metadata(dest, existing_meta)
    else:
        meta = {
            "id": new_id,
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

            from plaibox.project import generate_project_id
            new_id = generate_project_id()

            meta = {
                "id": new_id,
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


@cli.group()
def sync():
    """Cross-device sync commands."""
    pass


@sync.command()
@click.option("--config", "config_path", default=None, help="Path to config file.")
def init(config_path: str | None):
    """Set up cross-device sync with GitHub."""
    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    cfg = load_config(cfg_path)

    if is_sync_enabled(cfg):
        click.echo("Sync is already configured.")
        return

    # Check gh auth
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        click.echo("Error: GitHub CLI not authenticated. Run 'gh auth login' first.", err=True)
        raise SystemExit(1)

    click.echo("GitHub accounts available:")
    click.echo(result.stdout.strip() if result.stdout.strip() else result.stderr.strip())

    if not click.confirm("Continue with this account?"):
        click.echo("Cancelled. Switch accounts with 'gh auth login' and try again.")
        return

    # Create sync repo
    click.echo("Creating plaibox-sync repo...")
    result = subprocess.run(
        ["gh", "repo", "create", "plaibox-sync", "--private", "--description",
         "Plaibox cross-device sync registry"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 and "already exists" not in result.stderr:
        click.echo(f"Error creating sync repo: {result.stderr.strip()}", err=True)
        raise SystemExit(1)
    sync_url = result.stdout.strip()

    # Get SSH URL for the repo
    result = subprocess.run(
        ["gh", "repo", "view", "plaibox-sync", "--json", "sshUrl", "-q", ".sshUrl"],
        capture_output=True, text=True,
    )
    sync_ssh = result.stdout.strip() if result.returncode == 0 else sync_url

    # Create sandbox repo
    click.echo("Creating plaibox-sandbox repo...")
    result = subprocess.run(
        ["gh", "repo", "create", "plaibox-sandbox", "--private", "--description",
         "Plaibox sandbox project code"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 and "already exists" not in result.stderr:
        click.echo(f"Error creating sandbox repo: {result.stderr.strip()}", err=True)
        raise SystemExit(1)

    result = subprocess.run(
        ["gh", "repo", "view", "plaibox-sandbox", "--json", "sshUrl", "-q", ".sshUrl"],
        capture_output=True, text=True,
    )
    sandbox_ssh = result.stdout.strip() if result.returncode == 0 else ""

    machine_name = socket.gethostname()

    cfg["sync"] = {
        "enabled": True,
        "repo": sync_ssh,
        "sandbox_repos": [sandbox_ssh] if sandbox_ssh else [],
        "sandbox_branch_limit": 50,
        "machine_name": machine_name,
    }
    save_config(cfg, cfg_path)

    # Clone the sync repo locally
    ensure_sync_repo_cloned(cfg["sync"], cfg_path.parent)

    click.echo(f"Sync configured! Machine name: {machine_name}")
    click.echo("Your projects will now sync automatically after changes.")
    click.echo("Run 'plaibox sync pull' on your other machine to get started.")


@sync.command()
@click.option("--config", "config_path", default=None, help="Path to config file.")
def pull(config_path: str | None):
    """Pull latest project registry from the sync repo."""
    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    cfg = load_config(cfg_path)

    sync_cfg = get_sync_config(cfg)
    if sync_cfg is None:
        click.echo("Sync not configured. Run 'plaibox sync init' first.", err=True)
        raise SystemExit(1)

    repo_path = ensure_sync_repo_cloned(sync_cfg, cfg_path.parent)
    pull_sync_repo(repo_path)

    root = Path(cfg["root"]).expanduser()
    remote_projects = read_remote_projects(repo_path)

    # Compare with local projects
    local_projects = discover_projects(root)
    local_ids = {p["id"] for p in local_projects}

    new_remote = [rp for rp in remote_projects if rp["id"] not in local_ids]

    # Write remote registry for ls to pick up
    registry_path = cfg_path.parent / "remote-registry.yaml"
    registry = {}
    for rp in remote_projects:
        registry[rp["id"]] = rp["meta"]
    with open(registry_path, "w") as f:
        yaml.dump(registry, f, default_flow_style=False, sort_keys=False)

    if new_remote:
        click.echo(f"Found {len(new_remote)} remote-only project(s):")
        for rp in new_remote:
            m = rp["meta"]
            click.echo(f"  {m['name']} — {m['description']} (on {m.get('machine', '?')})")
        click.echo("\nUse 'plaibox open <name>' to clone a remote project.")
    else:
        click.echo("All synced. No new remote projects.")


@cli.command("init-shell")
def init_shell():
    """Print shell function for cd integration. Add to your .zshrc/.bashrc:

    eval "$(plaibox init-shell)"
    """
    click.echo(shell_init_script())
