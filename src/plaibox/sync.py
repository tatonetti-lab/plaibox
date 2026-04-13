# src/plaibox/sync.py
import subprocess
from datetime import datetime
from pathlib import Path

import yaml


def get_sync_repo_path(config_dir: Path) -> Path:
    """Return the local path where the sync repo is cloned."""
    return config_dir / "sync-repo"


def ensure_sync_repo_cloned(sync_config: dict, config_dir: Path) -> Path:
    """Clone the sync repo if not already present. Returns the local repo path."""
    repo_path = get_sync_repo_path(config_dir)
    if (repo_path / ".git").exists():
        return repo_path

    repo_url = sync_config["repo"]
    result = subprocess.run(
        ["git", "clone", repo_url, str(repo_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        # Empty repo — init locally and set remote
        repo_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", repo_url],
            cwd=repo_path, capture_output=True,
        )

    # Ensure projects/ directory exists
    (repo_path / "projects").mkdir(exist_ok=True)
    return repo_path


def push_project_meta(project_id: str, meta: dict, repo_path: Path) -> bool:
    """Write a project's metadata to the sync repo and push. Returns True on success."""
    projects_dir = repo_path / "projects"
    projects_dir.mkdir(exist_ok=True)

    meta_file = projects_dir / f"{project_id}.yaml"
    with open(meta_file, "w") as f:
        yaml.dump(meta, f, default_flow_style=False, sort_keys=False)

    subprocess.run(["git", "add", str(meta_file)], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"update {project_id}"],
        cwd=repo_path, capture_output=True,
    )
    result = subprocess.run(
        ["git", "push", "-u", "origin", "HEAD"],
        cwd=repo_path, capture_output=True,
    )
    return result.returncode == 0


def pull_sync_repo(repo_path: Path) -> bool:
    """Pull latest from the sync repo remote. Returns True on success."""
    result = subprocess.run(
        ["git", "pull", "--rebase", "origin", "HEAD"],
        cwd=repo_path, capture_output=True,
    )
    return result.returncode == 0


def read_remote_projects(repo_path: Path) -> list[dict]:
    """Read all project metadata files from the local sync repo checkout."""
    projects_dir = repo_path / "projects"
    if not projects_dir.exists():
        return []

    results = []
    for f in sorted(projects_dir.iterdir()):
        if not f.name.endswith(".yaml"):
            continue
        project_id = f.stem
        with open(f) as fh:
            meta = yaml.safe_load(fh)
        results.append({"id": project_id, "meta": meta})
    return results


def remove_project_meta(project_id: str, repo_path: Path) -> bool:
    """Remove a project's metadata from the sync repo and push. Returns True on success."""
    meta_file = repo_path / "projects" / f"{project_id}.yaml"
    if not meta_file.exists():
        return True

    subprocess.run(["git", "rm", str(meta_file)], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"remove {project_id}"],
        cwd=repo_path, capture_output=True,
    )
    result = subprocess.run(
        ["git", "push", "origin", "HEAD"],
        cwd=repo_path, capture_output=True,
    )
    return result.returncode == 0


def push_sandbox_branch(project_dir: Path, sandbox_repo_url: str, branch_name: str) -> bool:
    """Push a project's code to a branch in the sandbox repo. Returns True on success."""
    # Add sandbox remote if not present
    result = subprocess.run(
        ["git", "remote", "get-url", "sandbox"],
        cwd=project_dir, capture_output=True, text=True,
    )
    if result.returncode != 0:
        subprocess.run(
            ["git", "remote", "add", "sandbox", sandbox_repo_url],
            cwd=project_dir, capture_output=True,
        )
    else:
        subprocess.run(
            ["git", "remote", "set-url", "sandbox", sandbox_repo_url],
            cwd=project_dir, capture_output=True,
        )

    result = subprocess.run(
        ["git", "push", "sandbox", f"HEAD:{branch_name}"],
        cwd=project_dir, capture_output=True,
    )
    return result.returncode == 0


def clone_sandbox_branch(sandbox_repo_url: str, branch_name: str, dest: Path) -> bool:
    """Clone a single branch from the sandbox repo. Returns True on success."""
    result = subprocess.run(
        ["git", "clone", "--branch", branch_name, "--single-branch", sandbox_repo_url, str(dest)],
        capture_output=True,
    )
    return result.returncode == 0


def delete_sandbox_branch(sandbox_repo_url: str, branch_name: str) -> bool:
    """Delete a branch from the sandbox repo remote. Returns True on success."""
    result = subprocess.run(
        ["git", "push", sandbox_repo_url, "--delete", branch_name],
        capture_output=True,
    )
    return result.returncode == 0


def count_sandbox_branches(sandbox_repo_url: str) -> int:
    """Count the number of branches on the sandbox repo remote."""
    result = subprocess.run(
        ["git", "ls-remote", "--heads", sandbox_repo_url],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return 0
    lines = [l for l in result.stdout.strip().splitlines() if l]
    return len(lines)


def get_active_sandbox_repo(sync_config: dict) -> str | None:
    """Get the currently active sandbox repo URL.

    Returns the last repo in the list (newest). Returns None if no sandbox repos configured.
    """
    repos = sync_config.get("sandbox_repos", [])
    if not repos:
        return None
    return repos[-1]


def needs_sandbox_rotation(sync_config: dict) -> bool:
    """Check if the active sandbox repo has exceeded the branch limit."""
    repo = get_active_sandbox_repo(sync_config)
    if repo is None:
        return False
    limit = sync_config.get("sandbox_branch_limit", 50)
    return count_sandbox_branches(repo) >= limit


def auto_push(
    project_id: str,
    local_meta: dict,
    space: str,
    remote: str | None,
    sandbox_repo: str | None,
    sync_config: dict,
    config_dir: Path,
) -> None:
    """Push project metadata to the sync repo. Fails silently."""
    try:
        repo_path = ensure_sync_repo_cloned(sync_config, config_dir)
        pull_sync_repo(repo_path)

        sync_meta = {
            "name": local_meta.get("name", ""),
            "description": local_meta.get("description", ""),
            "status": local_meta.get("status", ""),
            "created": local_meta.get("created", ""),
            "tags": local_meta.get("tags", []),
            "tech": local_meta.get("tech", []),
            "remote": remote,
            "space": space,
            "sandbox_repo": sandbox_repo,
            "updated": datetime.now().isoformat(timespec="seconds"),
            "machine": sync_config["machine_name"],
        }
        push_project_meta(project_id, sync_meta, repo_path)
    except Exception:
        pass  # Silent failure — offline is fine
