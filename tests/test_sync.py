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
    push_sandbox_branch,
    clone_sandbox_branch,
    delete_sandbox_branch,
    count_sandbox_branches,
    auto_push,
    get_active_sandbox_repo,
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


def test_push_sandbox_branch(tmp_path):
    bare = _init_bare_repo(tmp_path / "remote-sandbox.git")
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)
    (project_dir / "main.py").write_text("print('hello')")
    subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=project_dir, capture_output=True,
        env={**__import__("os").environ, "GIT_AUTHOR_NAME": "test",
             "GIT_AUTHOR_EMAIL": "t@t.com", "GIT_COMMITTER_NAME": "test",
             "GIT_COMMITTER_EMAIL": "t@t.com"},
    )

    success = push_sandbox_branch(project_dir, bare, "my-project-abc123")
    assert success is True


def test_clone_sandbox_branch(tmp_path):
    bare = _init_bare_repo(tmp_path / "remote-sandbox.git")

    source = tmp_path / "source-project"
    source.mkdir()
    subprocess.run(["git", "init"], cwd=source, capture_output=True)
    (source / "app.py").write_text("print('app')")
    subprocess.run(["git", "add", "."], cwd=source, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=source, capture_output=True,
        env={**__import__("os").environ, "GIT_AUTHOR_NAME": "test",
             "GIT_AUTHOR_EMAIL": "t@t.com", "GIT_COMMITTER_NAME": "test",
             "GIT_COMMITTER_EMAIL": "t@t.com"},
    )
    push_sandbox_branch(source, bare, "app-def456")

    dest = tmp_path / "cloned-project"
    success = clone_sandbox_branch(bare, "app-def456", dest)

    assert success is True
    assert (dest / "app.py").exists()
    assert (dest / ".git").exists()


def test_delete_sandbox_branch(tmp_path):
    bare = _init_bare_repo(tmp_path / "remote-sandbox.git")

    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init"], cwd=source, capture_output=True)
    (source / "file.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=source, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=source, capture_output=True,
        env={**__import__("os").environ, "GIT_AUTHOR_NAME": "test",
             "GIT_AUTHOR_EMAIL": "t@t.com", "GIT_COMMITTER_NAME": "test",
             "GIT_COMMITTER_EMAIL": "t@t.com"},
    )
    push_sandbox_branch(source, bare, "temp-branch")

    success = delete_sandbox_branch(bare, "temp-branch")
    assert success is True


def test_count_sandbox_branches(tmp_path):
    bare = _init_bare_repo(tmp_path / "remote-sandbox.git")

    assert count_sandbox_branches(bare) == 0

    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init"], cwd=source, capture_output=True)
    (source / "file.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=source, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=source, capture_output=True,
        env={**__import__("os").environ, "GIT_AUTHOR_NAME": "test",
             "GIT_AUTHOR_EMAIL": "t@t.com", "GIT_COMMITTER_NAME": "test",
             "GIT_COMMITTER_EMAIL": "t@t.com"},
    )
    push_sandbox_branch(source, bare, "branch-1")

    assert count_sandbox_branches(bare) == 1


def test_auto_push_writes_and_pushes(tmp_path):
    bare = _init_bare_repo(tmp_path / "remote-sync.git")
    config_dir = tmp_path / ".plaibox"
    config_dir.mkdir()
    sync_cfg = _make_sync_config(tmp_path, bare)
    repo_path = ensure_sync_repo_cloned(sync_cfg, config_dir)

    local_meta = {
        "name": "my-app",
        "description": "My application",
        "status": "sandbox",
        "created": "2026-04-13",
        "tags": [],
        "tech": ["python"],
    }

    auto_push(
        project_id="abc123",
        local_meta=local_meta,
        space="sandbox",
        remote=None,
        sandbox_repo="git@github.com:user/plaibox-sandbox.git",
        sync_config=sync_cfg,
        config_dir=config_dir,
    )

    project_file = repo_path / "projects" / "abc123.yaml"
    assert project_file.exists()
    saved = yaml.safe_load(project_file.read_text())
    assert saved["name"] == "my-app"
    assert saved["machine"] == "test-machine"
    assert saved["space"] == "sandbox"
    assert saved["sandbox_repo"] == "git@github.com:user/plaibox-sandbox.git"
    assert "updated" in saved


def test_auto_push_silent_on_failure(tmp_path):
    """auto_push should not raise even if the remote is unreachable."""
    config_dir = tmp_path / ".plaibox"
    config_dir.mkdir()
    sync_cfg = {
        "enabled": True,
        "repo": "/nonexistent/repo.git",
        "sandbox_repos": [],
        "sandbox_branch_limit": 50,
        "machine_name": "test-machine",
    }

    # Should not raise
    auto_push(
        project_id="abc123",
        local_meta={"name": "x", "description": "x", "status": "sandbox",
                     "created": "2026-04-13", "tags": [], "tech": []},
        space="sandbox",
        remote=None,
        sandbox_repo=None,
        sync_config=sync_cfg,
        config_dir=config_dir,
    )


def test_get_active_sandbox_repo_returns_first(tmp_path):
    sync_cfg = {
        "sandbox_repos": ["git@github.com:user/plaibox-sandbox.git"],
        "sandbox_branch_limit": 50,
    }
    result = get_active_sandbox_repo(sync_cfg)
    assert result == "git@github.com:user/plaibox-sandbox.git"


def test_get_active_sandbox_repo_returns_none_when_empty():
    sync_cfg = {"sandbox_repos": [], "sandbox_branch_limit": 50}
    result = get_active_sandbox_repo(sync_cfg)
    assert result is None
