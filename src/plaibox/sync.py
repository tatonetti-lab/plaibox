# src/plaibox/sync.py
import subprocess
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
