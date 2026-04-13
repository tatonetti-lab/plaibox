# tests/test_sync.py
import subprocess
import yaml
from pathlib import Path
from datetime import datetime

from plaibox.sync import (
    get_sync_repo_path,
    ensure_sync_repo_cloned,
    push_project_meta,
    pull_sync_repo,
    read_remote_projects,
    remove_project_meta,
)


def _init_bare_repo(path: Path) -> str:
    """Create a bare git repo to act as a fake remote."""
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "--bare"], cwd=path, capture_output=True)
    return str(path)


def _make_sync_config(tmp_path, bare_repo_url):
    """Build a sync config dict pointing at a local bare repo."""
    return {
        "enabled": True,
        "repo": bare_repo_url,
        "sandbox_repos": [],
        "sandbox_branch_limit": 50,
        "machine_name": "test-machine",
    }


def test_get_sync_repo_path(tmp_path):
    config_dir = tmp_path / ".plaibox"
    config_dir.mkdir()
    result = get_sync_repo_path(config_dir)
    assert result == config_dir / "sync-repo"


def test_ensure_sync_repo_cloned(tmp_path):
    bare = _init_bare_repo(tmp_path / "remote-sync.git")
    config_dir = tmp_path / ".plaibox"
    config_dir.mkdir()
    sync_cfg = _make_sync_config(tmp_path, bare)

    repo_path = ensure_sync_repo_cloned(sync_cfg, config_dir)

    assert repo_path.exists()
    assert (repo_path / ".git").exists()


def test_push_project_meta(tmp_path):
    bare = _init_bare_repo(tmp_path / "remote-sync.git")
    config_dir = tmp_path / ".plaibox"
    config_dir.mkdir()
    sync_cfg = _make_sync_config(tmp_path, bare)
    repo_path = ensure_sync_repo_cloned(sync_cfg, config_dir)

    meta = {
        "name": "test-project",
        "description": "A test",
        "status": "sandbox",
        "created": "2026-04-13",
        "tags": [],
        "tech": ["python"],
        "remote": None,
        "space": "sandbox",
        "sandbox_repo": None,
        "updated": "2026-04-13T15:00:00",
        "machine": "test-machine",
    }
    push_project_meta("abc123", meta, repo_path)

    # Verify the file exists in the repo
    project_file = repo_path / "projects" / "abc123.yaml"
    assert project_file.exists()
    saved = yaml.safe_load(project_file.read_text())
    assert saved["name"] == "test-project"


def test_read_remote_projects(tmp_path):
    bare = _init_bare_repo(tmp_path / "remote-sync.git")
    config_dir = tmp_path / ".plaibox"
    config_dir.mkdir()
    sync_cfg = _make_sync_config(tmp_path, bare)
    repo_path = ensure_sync_repo_cloned(sync_cfg, config_dir)

    # Push two projects
    for pid, name in [("abc123", "project-a"), ("def456", "project-b")]:
        push_project_meta(pid, {
            "name": name, "description": f"Desc {name}",
            "status": "sandbox", "created": "2026-04-13",
            "tags": [], "tech": [], "remote": None,
            "space": "sandbox", "sandbox_repo": None,
            "updated": "2026-04-13T15:00:00", "machine": "test-machine",
        }, repo_path)

    projects = read_remote_projects(repo_path)
    assert len(projects) == 2
    ids = {p["id"] for p in projects}
    assert ids == {"abc123", "def456"}


def test_remove_project_meta(tmp_path):
    bare = _init_bare_repo(tmp_path / "remote-sync.git")
    config_dir = tmp_path / ".plaibox"
    config_dir.mkdir()
    sync_cfg = _make_sync_config(tmp_path, bare)
    repo_path = ensure_sync_repo_cloned(sync_cfg, config_dir)

    push_project_meta("abc123", {
        "name": "doomed", "description": "Will be deleted",
        "status": "sandbox", "created": "2026-04-13",
        "tags": [], "tech": [], "remote": None,
        "space": "sandbox", "sandbox_repo": None,
        "updated": "2026-04-13T15:00:00", "machine": "test-machine",
    }, repo_path)

    remove_project_meta("abc123", repo_path)

    assert not (repo_path / "projects" / "abc123.yaml").exists()
    projects = read_remote_projects(repo_path)
    assert len(projects) == 0
