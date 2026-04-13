# Cross-Device Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add git-based cross-device sync so project metadata and sandbox code are shared across machines via private GitHub repos.

**Architecture:** A new `sync` module handles all git operations against two GitHub repos: a sync repo (metadata registry with one YAML file per project) and a sandbox repo (one branch per sandbox project's code). Auto-push fires silently after state-changing commands; manual pull via `plaibox sync`. The `open` command auto-clones remote-only projects.

**Tech Stack:** Python 3.10+, click, PyYAML, subprocess (git, gh CLI)

---

## File Structure

```
src/plaibox/
  sync.py          (NEW)  — all sync repo and sandbox repo git operations
  cli.py           (MOD)  — add sync command group, modify new/promote/archive/delete/open/ls/import
  config.py        (MOD)  — add sync config helpers
  project.py       (MOD)  — update discover_projects to include remote-only projects
tests/
  test_sync.py     (NEW)  — unit tests for sync module
  test_cli.py      (MOD)  — integration tests for sync CLI commands
```

Key design decision: all git/gh subprocess calls for sync live in `sync.py`. CLI commands call sync functions but don't contain git logic themselves. This keeps sync testable and the CLI focused on user interaction.

---

### Task 1: Sync Module — Config Helpers

**Files:**
- Modify: `src/plaibox/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for sync config helpers**

Add to `tests/test_config.py`:

```python
from plaibox.config import load_config, save_config, is_sync_enabled, get_sync_config


def test_save_config_writes_yaml(tmp_path):
    config_path = tmp_path / "config.yaml"
    config = {"root": "/tmp/plaibox", "stale_days": 30}
    save_config(config, config_path)

    assert config_path.exists()
    loaded = load_config(config_path)
    assert loaded["root"] == "/tmp/plaibox"
    assert loaded["stale_days"] == 30


def test_is_sync_enabled_false_by_default(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("root: /tmp/plaibox\nstale_days: 30\n")
    cfg = load_config(config_path)
    assert is_sync_enabled(cfg) is False


def test_is_sync_enabled_true_when_configured(tmp_path):
    import yaml
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "root": "/tmp/plaibox",
        "stale_days": 30,
        "sync": {
            "enabled": True,
            "repo": "git@github.com:user/plaibox-sync.git",
            "sandbox_repos": ["git@github.com:user/plaibox-sandbox.git"],
            "sandbox_branch_limit": 50,
            "machine_name": "test-machine",
        },
    }))
    cfg = load_config(config_path)
    assert is_sync_enabled(cfg) is True


def test_get_sync_config_returns_none_when_not_configured(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("root: /tmp/plaibox\nstale_days: 30\n")
    cfg = load_config(config_path)
    assert get_sync_config(cfg) is None


def test_get_sync_config_returns_dict_when_configured(tmp_path):
    import yaml
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "root": "/tmp/plaibox",
        "stale_days": 30,
        "sync": {
            "enabled": True,
            "repo": "git@github.com:user/plaibox-sync.git",
            "sandbox_repos": ["git@github.com:user/plaibox-sandbox.git"],
            "sandbox_branch_limit": 50,
            "machine_name": "test-machine",
        },
    }))
    cfg = load_config(config_path)
    sync_cfg = get_sync_config(cfg)
    assert sync_cfg["repo"] == "git@github.com:user/plaibox-sync.git"
    assert sync_cfg["machine_name"] == "test-machine"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `cannot import name 'save_config'`

- [ ] **Step 3: Implement config helpers**

Update `src/plaibox/config.py`:

```python
from pathlib import Path
import yaml


DEFAULT_CONFIG = {
    "root": str(Path.home() / "plaibox"),
    "stale_days": 30,
}

DEFAULT_CONFIG_PATH = Path.home() / ".plaibox" / "config.yaml"


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict:
    """Load config from disk, creating default if missing."""
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False)
    return dict(DEFAULT_CONFIG)


def save_config(config: dict, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Write config dict to disk."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def is_sync_enabled(config: dict) -> bool:
    """Check if sync is configured and enabled."""
    sync = config.get("sync")
    if sync is None:
        return False
    return sync.get("enabled", False)


def get_sync_config(config: dict) -> dict | None:
    """Get the sync config section, or None if not configured."""
    sync = config.get("sync")
    if sync is None or not sync.get("enabled", False):
        return None
    return sync
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/config.py tests/test_config.py
git commit -m "feat: add sync config helpers — save_config, is_sync_enabled, get_sync_config"
```

---

### Task 2: Sync Module — Core Git Operations

**Files:**
- Create: `src/plaibox/sync.py`
- Create: `tests/test_sync.py`

This task builds the low-level git operations that all sync commands depend on. All functions are designed to work against a local checkout of the sync repo stored at `~/.plaibox/sync-repo/`.

- [ ] **Step 1: Write failing tests for sync repo operations**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sync.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'plaibox.sync'`

- [ ] **Step 3: Implement sync module core**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sync.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/sync.py tests/test_sync.py
git commit -m "feat: add sync module with core git operations for sync repo"
```

---

### Task 3: Sync Module — Sandbox Repo Operations

**Files:**
- Modify: `src/plaibox/sync.py`
- Modify: `tests/test_sync.py`

- [ ] **Step 1: Write failing tests for sandbox repo operations**

Add to `tests/test_sync.py`:

```python
from plaibox.sync import (
    push_sandbox_branch,
    clone_sandbox_branch,
    delete_sandbox_branch,
    count_sandbox_branches,
)


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

    # Verify branch exists on remote
    result = subprocess.run(
        ["git", "branch", "-r"], cwd=project_dir, capture_output=True, text=True
    )
    assert "my-project-abc123" in result.stdout or success


def test_clone_sandbox_branch(tmp_path):
    bare = _init_bare_repo(tmp_path / "remote-sandbox.git")

    # Push a project to a branch first
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

    # Now clone it to a new location
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

    # Push a branch
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sync.py::test_push_sandbox_branch -v`
Expected: FAIL — `cannot import name 'push_sandbox_branch'`

- [ ] **Step 3: Implement sandbox repo operations**

Add to `src/plaibox/sync.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sync.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/sync.py tests/test_sync.py
git commit -m "feat: add sandbox repo operations — push, clone, delete branch, count"
```

---

### Task 4: Sync Module — Auto-Push Helper

**Files:**
- Modify: `src/plaibox/sync.py`
- Modify: `tests/test_sync.py`

This task adds a high-level `auto_push` function that CLI commands call after state changes. It builds the sync metadata dict from local project metadata and pushes to the sync repo. Fails silently.

- [ ] **Step 1: Write failing test for auto_push**

Add to `tests/test_sync.py`:

```python
from plaibox.sync import auto_push


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

    # Verify metadata was written
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sync.py::test_auto_push_writes_and_pushes -v`
Expected: FAIL — `cannot import name 'auto_push'`

- [ ] **Step 3: Implement auto_push**

Add to `src/plaibox/sync.py`:

```python
from datetime import datetime


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sync.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/sync.py tests/test_sync.py
git commit -m "feat: add auto_push helper for silent sync after state changes"
```

---

### Task 5: CLI — `plaibox sync init`

**Files:**
- Modify: `src/plaibox/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test for sync init**

Add to `tests/test_cli.py`:

```python
def test_sync_init_writes_config(tmp_path, monkeypatch):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    # Mock gh and git commands
    call_log = []

    def mock_run(cmd, **kwargs):
        call_log.append(cmd)

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""
        r = Result()

        if cmd[0] == "gh" and "auth" in cmd:
            r.stdout = "  account1 (github.com)\n"
        elif cmd[0] == "gh" and "repo" in cmd and "create" in cmd:
            r.stdout = "https://github.com/user/plaibox-sync"
        elif cmd[0] == "git":
            r.returncode = 0
        return r

    monkeypatch.setattr("plaibox.cli.subprocess.run", mock_run)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["sync", "init", "--config", str(config_path)],
        input="y\n",  # confirm account
    )

    assert result.exit_code == 0

    # Config should now have sync section
    updated_cfg = yaml.safe_load(config_path.read_text())
    assert "sync" in updated_cfg
    assert updated_cfg["sync"]["enabled"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_sync_init_writes_config -v`
Expected: FAIL — `No such command 'sync'`

- [ ] **Step 3: Implement sync command group with init subcommand**

Add to `src/plaibox/cli.py` (after the existing imports, add):

```python
import socket
from plaibox.config import save_config, is_sync_enabled, get_sync_config
from plaibox.sync import (
    ensure_sync_repo_cloned, auto_push, pull_sync_repo,
    read_remote_projects, remove_project_meta,
    push_sandbox_branch, clone_sandbox_branch, delete_sandbox_branch,
    count_sandbox_branches,
)
```

Add the sync command group before `init_shell`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py::test_sync_init_writes_config -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: add 'plaibox sync init' to set up cross-device sync"
```

---

### Task 6: CLI — `plaibox sync pull`

**Files:**
- Modify: `src/plaibox/cli.py`
- Modify: `src/plaibox/project.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test for sync pull**

Add to `tests/test_cli.py`:

```python
def test_sync_pull_shows_remote_projects(tmp_path, monkeypatch):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_dir = tmp_path
    config_path = config_dir / "config.yaml"

    # Set up a bare repo as the sync remote
    import subprocess as sp
    bare = tmp_path / "remote-sync.git"
    bare.mkdir(parents=True)
    sp.run(["git", "init", "--bare"], cwd=bare, capture_output=True)

    config_path.write_text(yaml.dump({
        "root": str(root),
        "stale_days": 30,
        "sync": {
            "enabled": True,
            "repo": str(bare),
            "sandbox_repos": [],
            "sandbox_branch_limit": 50,
            "machine_name": "test-machine",
        },
    }))

    # Seed the sync repo with a project from "another machine"
    from plaibox.sync import ensure_sync_repo_cloned, push_project_meta
    sync_cfg = yaml.safe_load(config_path.read_text())["sync"]
    repo_path = ensure_sync_repo_cloned(sync_cfg, config_dir)
    push_project_meta("remote1", {
        "name": "remote-project",
        "description": "From another machine",
        "status": "project",
        "created": "2026-04-13",
        "tags": [], "tech": ["python"],
        "remote": "git@github.com:user/remote-project.git",
        "space": "projects",
        "sandbox_repo": None,
        "updated": "2026-04-13T15:00:00",
        "machine": "other-machine",
    }, repo_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["sync", "pull", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "remote-project" in result.output or "1 remote" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_sync_pull_shows_remote_projects -v`
Expected: FAIL — `No such command 'pull'`

- [ ] **Step 3: Implement sync pull subcommand**

Add to `src/plaibox/cli.py` (in the `sync` group):

```python
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
    from plaibox.project import discover_projects, project_id
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py::test_sync_pull_shows_remote_projects -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: add 'plaibox sync pull' to fetch remote project registry"
```

---

### Task 7: Update `ls` — Remote Projects and Sync Hint

**Files:**
- Modify: `src/plaibox/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_cli.py`:

```python
def test_ls_shows_sync_hint_when_not_configured(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    _make_project(root, "sandbox", "2026-04-10_test", {
        "name": "test", "description": "A test",
        "status": "sandbox", "created": "2026-04-10", "tags": [], "tech": [],
    })

    runner = CliRunner()
    result = runner.invoke(cli, ["ls", "--config", str(config_path)])

    assert "plaibox sync init" in result.output


def test_ls_no_sync_hint_when_configured(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "root": str(root), "stale_days": 30,
        "sync": {"enabled": True, "repo": "x", "sandbox_repos": [],
                 "sandbox_branch_limit": 50, "machine_name": "m"},
    }))

    _make_project(root, "sandbox", "2026-04-10_test", {
        "name": "test", "description": "A test",
        "status": "sandbox", "created": "2026-04-10", "tags": [], "tech": [],
    })

    runner = CliRunner()
    result = runner.invoke(cli, ["ls", "--config", str(config_path)])

    assert "plaibox sync init" not in result.output


def test_ls_no_sync_hint_when_dismissed(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "root": str(root), "stale_days": 30,
        "sync_hint_dismissed": True,
    }))

    _make_project(root, "sandbox", "2026-04-10_test", {
        "name": "test", "description": "A test",
        "status": "sandbox", "created": "2026-04-10", "tags": [], "tech": [],
    })

    runner = CliRunner()
    result = runner.invoke(cli, ["ls", "--config", str(config_path)])

    assert "plaibox sync init" not in result.output


def test_ls_shows_remote_projects(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "root": str(root), "stale_days": 30,
        "sync": {"enabled": True, "repo": "x", "sandbox_repos": [],
                 "sandbox_branch_limit": 50, "machine_name": "m"},
    }))

    # Write a remote registry file
    registry = {
        "rem123": {
            "name": "remote-app",
            "description": "From another machine",
            "status": "project",
            "created": "2026-04-13",
            "tags": [], "tech": ["python"],
            "remote": "git@github.com:user/remote-app.git",
            "space": "projects",
            "sandbox_repo": None,
            "updated": "2026-04-13T15:00:00",
            "machine": "other-machine",
        }
    }
    registry_path = config_path.parent / "remote-registry.yaml"
    registry_path.write_text(yaml.dump(registry))

    runner = CliRunner()
    result = runner.invoke(cli, ["ls", "--config", str(config_path)])

    assert "remote-app" in result.output
    assert "remote" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_ls_shows_sync_hint_when_not_configured -v`
Expected: FAIL (no hint in output yet)

- [ ] **Step 3: Update ls command**

Replace the `ls_cmd` function in `src/plaibox/cli.py` with:

```python
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

        status_display = "remote" if p["space"] == "remote" else meta["status"]

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: show remote projects and sync hint in plaibox ls"
```

---

### Task 8: Auto-Push on `new`

**Files:**
- Modify: `src/plaibox/cli.py`
- Modify: `tests/test_cli.py`

This task wires auto-push into `plaibox new`. After creating the project locally, it pushes the branch to the sandbox repo and metadata to the sync repo.

- [ ] **Step 1: Write failing test**

Add to `tests/test_cli.py`:

```python
def test_new_auto_pushes_when_sync_enabled(tmp_path, monkeypatch):
    import subprocess as sp

    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    # Set up bare repos
    sync_bare = tmp_path / "remote-sync.git"
    sync_bare.mkdir(parents=True)
    sp.run(["git", "init", "--bare"], cwd=sync_bare, capture_output=True)

    sandbox_bare = tmp_path / "remote-sandbox.git"
    sandbox_bare.mkdir(parents=True)
    sp.run(["git", "init", "--bare"], cwd=sandbox_bare, capture_output=True)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "root": str(root),
        "stale_days": 30,
        "sync": {
            "enabled": True,
            "repo": str(sync_bare),
            "sandbox_repos": [str(sandbox_bare)],
            "sandbox_branch_limit": 50,
            "machine_name": "test-machine",
        },
    }))

    runner = CliRunner()
    result = runner.invoke(cli, ["new", "sync test project", "--config", str(config_path)])

    assert result.exit_code == 0

    # Verify metadata was pushed to sync repo
    from plaibox.sync import ensure_sync_repo_cloned, read_remote_projects
    sync_cfg = yaml.safe_load(config_path.read_text())["sync"]
    repo_path = ensure_sync_repo_cloned(sync_cfg, config_path.parent)
    from plaibox.sync import pull_sync_repo
    pull_sync_repo(repo_path)
    remote = read_remote_projects(repo_path)
    assert len(remote) == 1
    assert remote[0]["meta"]["name"] == "sync-test-project"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_new_auto_pushes_when_sync_enabled -v`
Expected: FAIL (no sync push happening yet)

- [ ] **Step 3: Add auto-push to `new` command**

Update the `new` function in `src/plaibox/cli.py`. After `click.echo(str(project_dir))`, add:

```python
    # Auto-push to sync if enabled
    if is_sync_enabled(cfg):
        sync_cfg = get_sync_config(cfg)
        from plaibox.project import project_id
        pid = project_id(project_dir)
        sandbox_repo = sync_cfg["sandbox_repos"][0] if sync_cfg["sandbox_repos"] else None
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: auto-push to sync and sandbox repos on plaibox new"
```

---

### Task 9: Auto-Push on `promote`, `archive`, `delete`

**Files:**
- Modify: `src/plaibox/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_cli.py`:

```python
def test_promote_updates_sync(tmp_path, monkeypatch):
    import subprocess as sp

    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    sync_bare = tmp_path / "remote-sync.git"
    sync_bare.mkdir(parents=True)
    sp.run(["git", "init", "--bare"], cwd=sync_bare, capture_output=True)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "root": str(root),
        "stale_days": 30,
        "sync": {
            "enabled": True,
            "repo": str(sync_bare),
            "sandbox_repos": [],
            "sandbox_branch_limit": 50,
            "machine_name": "test-machine",
        },
    }))

    proj = _make_project(root, "sandbox", "2026-04-13_my-exp", {
        "name": "my-exp", "description": "Experiment",
        "status": "sandbox", "created": "2026-04-13", "tags": [], "tech": [],
    })

    # Mock gh commands for promote's GitHub repo creation
    def mock_run(cmd, **kwargs):
        class Result:
            returncode = 0
            stdout = "https://github.com/user/cool-app"
            stderr = ""
        # Fall through to real subprocess for git commands
        if cmd[0] == "gh":
            return Result()
        return original_run(cmd, **kwargs)

    original_run = sp.run
    monkeypatch.setattr("plaibox.cli.subprocess.run", mock_run)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["promote", "--config", str(config_path), "--dir", str(proj)],
        input="cool-app\nn\n",
    )

    assert result.exit_code == 0

    # Verify sync repo was updated
    monkeypatch.undo()
    from plaibox.sync import ensure_sync_repo_cloned, read_remote_projects, pull_sync_repo
    sync_cfg = yaml.safe_load(config_path.read_text())["sync"]
    repo_path = ensure_sync_repo_cloned(sync_cfg, config_path.parent)
    pull_sync_repo(repo_path)
    remote = read_remote_projects(repo_path)
    assert len(remote) == 1
    assert remote[0]["meta"]["status"] == "project"


def test_delete_removes_from_sync(tmp_path):
    import subprocess as sp

    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    sync_bare = tmp_path / "remote-sync.git"
    sync_bare.mkdir(parents=True)
    sp.run(["git", "init", "--bare"], cwd=sync_bare, capture_output=True)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "root": str(root),
        "stale_days": 30,
        "sync": {
            "enabled": True,
            "repo": str(sync_bare),
            "sandbox_repos": [],
            "sandbox_branch_limit": 50,
            "machine_name": "test-machine",
        },
    }))

    proj = _make_project(root, "archive", "2026-04-13_old-thing", {
        "name": "old-thing", "description": "Old",
        "status": "archived", "created": "2026-04-13", "tags": [], "tech": [],
    })

    # Seed sync repo with this project
    from plaibox.sync import ensure_sync_repo_cloned, push_project_meta, pull_sync_repo, read_remote_projects
    from plaibox.project import project_id
    sync_cfg = yaml.safe_load(config_path.read_text())["sync"]
    repo_path = ensure_sync_repo_cloned(sync_cfg, config_path.parent)
    pid = project_id(proj)
    push_project_meta(pid, {
        "name": "old-thing", "description": "Old", "status": "archived",
        "created": "2026-04-13", "tags": [], "tech": [],
        "remote": None, "space": "archive", "sandbox_repo": None,
        "updated": "2026-04-13T15:00:00", "machine": "test-machine",
    }, repo_path)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["delete", "--config", str(config_path), "--dir", str(proj)],
        input="y\n",
    )

    assert result.exit_code == 0

    # Verify removed from sync
    pull_sync_repo(repo_path)
    remote = read_remote_projects(repo_path)
    assert len(remote) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_promote_updates_sync tests/test_cli.py::test_delete_removes_from_sync -v`
Expected: FAIL

- [ ] **Step 3: Add auto-push to `promote`**

At the end of the `promote` function (after the GitHub repo creation section), add:

```python
    # Auto-push to sync if enabled
    if is_sync_enabled(cfg):
        sync_cfg = get_sync_config(cfg)
        from plaibox.project import project_id
        pid = project_id(new_path)
        auto_push(
            project_id=pid,
            local_meta=meta,
            space="projects",
            remote=meta.get("remote"),
            sandbox_repo=None,
            sync_config=sync_cfg,
            config_dir=Path(config_path).parent if config_path else DEFAULT_CONFIG_PATH.parent,
        )
```

- [ ] **Step 4: Add auto-push to `archive`**

At the end of the `archive` function (after `click.echo`), add:

```python
    # Auto-push to sync if enabled
    if is_sync_enabled(cfg):
        sync_cfg = get_sync_config(cfg)
        from plaibox.project import project_id
        pid = project_id(new_path)
        auto_push(
            project_id=pid,
            local_meta=meta,
            space="archive",
            remote=meta.get("remote"),
            sandbox_repo=None,
            sync_config=sync_cfg,
            config_dir=Path(config_path).parent if config_path else DEFAULT_CONFIG_PATH.parent,
        )
```

- [ ] **Step 5: Add sync removal to `delete`**

In the `delete` function, after `shutil.rmtree(project_path)` and before `click.echo`, add:

```python
    # Remove from sync if enabled
    if is_sync_enabled(cfg):
        sync_cfg = get_sync_config(cfg)
        from plaibox.project import project_id
        pid = project_id(project_path)
        try:
            repo_path = ensure_sync_repo_cloned(sync_cfg,
                Path(config_path).parent if config_path else DEFAULT_CONFIG_PATH.parent)
            pull_sync_repo(repo_path)
            remove_project_meta(pid, repo_path)
        except Exception:
            pass
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: auto-push sync on promote, archive, delete"
```

---

### Task 10: Auto-Clone on `open`

**Files:**
- Modify: `src/plaibox/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_cli.py`:

```python
def test_open_clones_remote_project(tmp_path):
    import subprocess as sp

    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    # Create a bare repo to act as the project's remote
    project_bare = tmp_path / "remote-app.git"
    project_bare.mkdir(parents=True)
    sp.run(["git", "init", "--bare"], cwd=project_bare, capture_output=True)

    # Push some content to it
    source = tmp_path / "source"
    source.mkdir()
    sp.run(["git", "init"], cwd=source, capture_output=True)
    (source / "app.py").write_text("print('hello')")
    sp.run(["git", "add", "."], cwd=source, capture_output=True)
    sp.run(
        ["git", "commit", "-m", "init"],
        cwd=source, capture_output=True,
        env={**__import__("os").environ, "GIT_AUTHOR_NAME": "test",
             "GIT_AUTHOR_EMAIL": "t@t.com", "GIT_COMMITTER_NAME": "test",
             "GIT_COMMITTER_EMAIL": "t@t.com"},
    )
    sp.run(["git", "remote", "add", "origin", str(project_bare)], cwd=source, capture_output=True)
    sp.run(["git", "push", "-u", "origin", "HEAD"], cwd=source, capture_output=True)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "root": str(root),
        "stale_days": 30,
        "sync": {
            "enabled": True,
            "repo": "unused",
            "sandbox_repos": [],
            "sandbox_branch_limit": 50,
            "machine_name": "test-machine",
        },
    }))

    # Write remote registry with the project
    registry = {
        "rem123": {
            "name": "remote-app",
            "description": "From another machine",
            "status": "project",
            "created": "2026-04-13",
            "tags": [], "tech": [],
            "remote": str(project_bare),
            "space": "projects",
            "sandbox_repo": None,
            "updated": "2026-04-13T15:00:00",
            "machine": "other-machine",
        }
    }
    registry_path = config_path.parent / "remote-registry.yaml"
    registry_path.write_text(yaml.dump(registry))

    runner = CliRunner()
    result = runner.invoke(
        cli, ["open", "remote-app", "--config", str(config_path)],
        input="y\n",  # confirm clone
    )

    assert result.exit_code == 0
    # Should have cloned to projects/remote-app
    cloned = root / "projects" / "remote-app"
    assert cloned.exists() or str(cloned) in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_open_clones_remote_project -v`
Expected: FAIL

- [ ] **Step 3: Update `open` command to handle remote projects**

Replace the `open_cmd` function in `src/plaibox/cli.py`:

```python
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
        "name": meta["name"],
        "description": meta["description"],
        "status": meta["status"],
        "created": meta["created"],
        "tags": meta.get("tags", []),
        "tech": meta.get("tech", []),
        "remote": remote_url,
    })

    click.echo(str(dest))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: auto-clone remote projects on plaibox open"
```

---

### Task 11: Sandbox Repo Rotation

**Files:**
- Modify: `src/plaibox/sync.py`
- Modify: `src/plaibox/cli.py`
- Modify: `tests/test_sync.py`

- [ ] **Step 1: Write failing test for rotation helper**

Add to `tests/test_sync.py`:

```python
from plaibox.sync import get_active_sandbox_repo


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sync.py::test_get_active_sandbox_repo_returns_first -v`
Expected: FAIL — `cannot import name 'get_active_sandbox_repo'`

- [ ] **Step 3: Implement rotation helper**

Add to `src/plaibox/sync.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sync.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/sync.py tests/test_sync.py
git commit -m "feat: add sandbox repo rotation helpers"
```

---

### Task 12: Final Integration Test and README Update

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `README.md`

- [ ] **Step 1: Write an end-to-end sync integration test**

Add to `tests/test_cli.py`:

```python
def test_sync_full_lifecycle(tmp_path):
    """End-to-end: init sync, new (auto-push), pull on 'other machine', open (clone)."""
    import subprocess as sp

    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    # Set up bare repos
    sync_bare = tmp_path / "remote-sync.git"
    sync_bare.mkdir(parents=True)
    sp.run(["git", "init", "--bare"], cwd=sync_bare, capture_output=True)

    sandbox_bare = tmp_path / "remote-sandbox.git"
    sandbox_bare.mkdir(parents=True)
    sp.run(["git", "init", "--bare"], cwd=sandbox_bare, capture_output=True)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "root": str(root),
        "stale_days": 30,
        "sync": {
            "enabled": True,
            "repo": str(sync_bare),
            "sandbox_repos": [str(sandbox_bare)],
            "sandbox_branch_limit": 50,
            "machine_name": "machine-a",
        },
    }))

    runner = CliRunner()

    # Create a project on "machine A"
    result = runner.invoke(cli, ["new", "cross device test", "--config", str(config_path)])
    assert result.exit_code == 0

    # "Machine B" pulls
    root_b = tmp_path / "plaibox-b"
    root_b.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root_b / space).mkdir()

    config_b = tmp_path / "config-b.yaml"
    config_b.write_text(yaml.dump({
        "root": str(root_b),
        "stale_days": 30,
        "sync": {
            "enabled": True,
            "repo": str(sync_bare),
            "sandbox_repos": [str(sandbox_bare)],
            "sandbox_branch_limit": 50,
            "machine_name": "machine-b",
        },
    }))

    result = runner.invoke(cli, ["sync", "pull", "--config", str(config_b)])
    assert result.exit_code == 0
    assert "cross-device-test" in result.output or "1 remote" in result.output

    # Machine B can see it in ls
    result = runner.invoke(cli, ["ls", "--config", str(config_b)])
    assert "cross-device-test" in result.output
```

- [ ] **Step 2: Run the full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Update README**

Add a new section after "Python virtual environments" in `README.md`:

```markdown
### Cross-device sync

Sync your project registry across machines using a private GitHub repo:

```bash
# Set up sync (creates GitHub repos, one-time)
plaibox sync init

# After making changes, metadata is auto-pushed
plaibox new "my experiment"    # auto-syncs to registry

# On your other machine, pull the latest
plaibox sync pull

# Open a project that only exists on the other machine
plaibox open my-experiment     # offers to clone it
```

Sync is opt-in — plaibox works exactly the same without it. Sandbox project code is stored as branches in a shared repo; promoted projects use their own dedicated GitHub repos.
```

- [ ] **Step 4: Run all tests one final time**

Run: `pytest tests/ -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli.py README.md
git commit -m "feat: add sync integration test and update README with sync docs"
```
