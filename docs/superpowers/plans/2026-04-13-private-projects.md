# Private Projects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `private` flag to plaibox projects that prevents code from being pushed to any remote while still syncing metadata across devices.

**Architecture:** A `private: true` field in `.plaibox.yaml` gates all code-push paths (`push_sandbox_branch` in `new`, `gh repo create` in `promote`). Metadata continues to sync normally via `auto_push`. A new `unprivate` command removes the flag and retroactively pushes code. The `private` field is propagated to the sync repo so remote machines know the project is private.

**Tech Stack:** Python, Click, PyYAML, subprocess (git)

---

## File Structure

- **Modify:** `src/plaibox/cli.py` — Add `--private` flag to `new`, guard `promote` for private projects, update `ls` display, add `unprivate` command, update `_clone_remote_project` for private projects
- **Modify:** `src/plaibox/sync.py` — Add `private` field to `auto_push` sync metadata
- **Modify:** `tests/test_cli.py` — Tests for all private project behaviors
- **Modify:** `tests/test_sync.py` — Test that `auto_push` includes `private` field

---

### Task 1: `plaibox new --private` skips sandbox push

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/plaibox/cli.py:28-107`

- [ ] **Step 1: Write the failing test for `new --private`**

In `tests/test_cli.py`, add:

```python
def test_new_private_sets_flag_and_skips_sandbox_push(tmp_path, monkeypatch):
    """Private projects should have private: true in metadata and skip sandbox push."""
    root = tmp_path / "plaibox"
    root.mkdir()
    (root / "sandbox").mkdir()
    (root / "projects").mkdir()
    (root / "archive").mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(cli, ["new", "secret research", "--private", "--config", str(config_path)])

    assert result.exit_code == 0

    # Should have created the project
    sandbox_dirs = list((root / "sandbox").iterdir())
    assert len(sandbox_dirs) == 1

    # Metadata should have private: true
    meta = yaml.safe_load((sandbox_dirs[0] / ".plaibox.yaml").read_text())
    assert meta["private"] is True
    assert meta["description"] == "secret research"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py::test_new_private_sets_flag_and_skips_sandbox_push -v`
Expected: FAIL — `new` command doesn't accept `--private` flag

- [ ] **Step 3: Write test that sync-enabled private project skips sandbox push**

In `tests/test_cli.py`, add:

```python
def test_new_private_with_sync_skips_sandbox_push(tmp_path, monkeypatch):
    """When sync is enabled, private projects should NOT push code to sandbox repo."""
    import subprocess

    root = tmp_path / "plaibox"
    root.mkdir()
    (root / "sandbox").mkdir()
    (root / "projects").mkdir()
    (root / "archive").mkdir()

    # Create a bare repo to act as sandbox
    sandbox_bare = tmp_path / "sandbox-bare.git"
    subprocess.run(["git", "init", "--bare", str(sandbox_bare)], capture_output=True)

    # Create a bare repo to act as sync repo
    sync_bare = tmp_path / "sync-bare.git"
    subprocess.run(["git", "init", "--bare", str(sync_bare)], capture_output=True)

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
    result = runner.invoke(cli, ["new", "private experiment", "--private", "--config", str(config_path)])

    assert result.exit_code == 0

    # Sandbox repo should have NO branches (code was not pushed)
    ls_result = subprocess.run(
        ["git", "ls-remote", "--heads", str(sandbox_bare)],
        capture_output=True, text=True,
    )
    assert ls_result.stdout.strip() == ""

    # But metadata should NOT have sandbox_repo set
    sandbox_dirs = list((root / "sandbox").iterdir())
    meta = yaml.safe_load((sandbox_dirs[0] / ".plaibox.yaml").read_text())
    assert meta["private"] is True
    assert meta.get("sandbox_repo") is None
    assert meta.get("sandbox_branch") is None
```

- [ ] **Step 4: Add `--private` flag to `new` command**

In `src/plaibox/cli.py`, modify the `new` command decorator and function. Add the flag after the existing `--python` flag:

```python
@cli.command()
@click.argument("description", required=False)
@click.option("--python", "create_venv", is_flag=True, help="Create a Python virtual environment (.venv).")
@click.option("--private", is_flag=True, help="Mark project as private (code never pushed to remotes).")
@click.option("--config", "config_path", default=None, help="Path to config file.")
def new(description: str | None, create_venv: bool, private: bool, config_path: str | None):
```

In the metadata dict construction (after `"tech": []`), add:

```python
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
```

In the sync section, wrap the sandbox push in a private check. Replace the existing sync block (lines ~76-106) with:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py::test_new_private_sets_flag_and_skips_sandbox_push tests/test_cli.py::test_new_private_with_sync_skips_sandbox_push -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: add --private flag to plaibox new"
```

---

### Task 2: Propagate `private` field in sync metadata

**Files:**
- Modify: `src/plaibox/sync.py:217-246`
- Modify: `tests/test_sync.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_sync.py`, add:

```python
def test_auto_push_includes_private_field(tmp_path):
    """auto_push should include private field in sync metadata when present."""
    import subprocess

    # Set up a bare repo as sync remote
    bare = tmp_path / "sync-bare.git"
    subprocess.run(["git", "init", "--bare", str(bare)], capture_output=True)

    sync_config = {
        "repo": str(bare),
        "sandbox_repos": [],
        "sandbox_branch_limit": 50,
        "machine_name": "test-machine",
    }

    config_dir = tmp_path / "config"
    config_dir.mkdir()

    auto_push(
        project_id="abc123",
        local_meta={
            "name": "secret",
            "description": "secret project",
            "status": "sandbox",
            "created": "2026-04-13",
            "tags": [],
            "tech": [],
            "private": True,
        },
        space="sandbox",
        remote=None,
        sandbox_repo=None,
        sync_config=sync_config,
        config_dir=config_dir,
    )

    # Read the pushed metadata
    repo_path = config_dir / "sync-repo"
    meta_file = repo_path / "projects" / "abc123.yaml"
    assert meta_file.exists()
    meta = yaml.safe_load(meta_file.read_text())
    assert meta["private"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sync.py::test_auto_push_includes_private_field -v`
Expected: FAIL — `private` key not in sync metadata

- [ ] **Step 3: Add `private` field to `auto_push`**

In `src/plaibox/sync.py`, in the `auto_push` function, add `private` to the `sync_meta` dict. After the `"machine"` line:

```python
        sync_meta = {
            "name": local_meta.get("name", ""),
            "description": local_meta.get("description", ""),
            "status": local_meta.get("status", ""),
            "created": local_meta.get("created", ""),
            "tags": local_meta.get("tags", []),
            "tech": local_meta.get("tech", []),
            "private": local_meta.get("private", False),
            "remote": remote,
            "space": space,
            "sandbox_repo": sandbox_repo,
            "updated": datetime.now().isoformat(timespec="seconds"),
            "machine": sync_config["machine_name"],
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sync.py::test_auto_push_includes_private_field -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/sync.py tests/test_sync.py
git commit -m "feat: propagate private field in sync metadata"
```

---

### Task 3: `plaibox promote` handles private projects

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/plaibox/cli.py:200-279`

- [ ] **Step 1: Write the failing test for private promote**

In `tests/test_cli.py`, add:

```python
def test_promote_private_asks_for_remote_url(tmp_path, monkeypatch):
    """Promoting a private project should ask for a remote URL instead of offering gh repo create."""
    root = tmp_path / "plaibox"
    root.mkdir()
    (root / "sandbox").mkdir()
    (root / "projects").mkdir()
    (root / "archive").mkdir()

    # Create a private sandbox project
    project_dir = root / "sandbox" / "2026-04-13_secret-analysis"
    project_dir.mkdir(parents=True)
    import subprocess
    subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)

    meta = {
        "id": "priv01",
        "name": "secret-analysis",
        "description": "secret analysis",
        "status": "sandbox",
        "created": "2026-04-13",
        "private": True,
        "tags": [],
        "tech": [],
    }
    (project_dir / ".plaibox.yaml").write_text(yaml.dump(meta))

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    # Provide project name, then press Enter to skip remote URL
    result = runner.invoke(
        cli, ["promote", "--dir", str(project_dir), "--config", str(config_path)],
        input="secret-analysis\n\n",
    )

    assert result.exit_code == 0
    assert "This project is private" in result.output
    assert (root / "projects" / "secret-analysis").exists()

    # Metadata should still be private
    new_meta = yaml.safe_load((root / "projects" / "secret-analysis" / ".plaibox.yaml").read_text())
    assert new_meta["private"] is True
    assert new_meta.get("remote") is None


def test_promote_private_with_remote_url(tmp_path, monkeypatch):
    """Promoting a private project with a remote URL should set the remote."""
    root = tmp_path / "plaibox"
    root.mkdir()
    (root / "sandbox").mkdir()
    (root / "projects").mkdir()
    (root / "archive").mkdir()

    project_dir = root / "sandbox" / "2026-04-13_secret-analysis"
    project_dir.mkdir(parents=True)
    import subprocess
    subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)

    meta = {
        "id": "priv02",
        "name": "secret-analysis",
        "description": "secret analysis",
        "status": "sandbox",
        "created": "2026-04-13",
        "private": True,
        "tags": [],
        "tech": [],
    }
    (project_dir / ".plaibox.yaml").write_text(yaml.dump(meta))

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    # Create a bare repo to act as the institutional remote
    remote_bare = tmp_path / "institutional-remote.git"
    subprocess.run(["git", "init", "--bare", str(remote_bare)], capture_output=True)

    runner = CliRunner()
    # Provide project name, then the remote URL
    result = runner.invoke(
        cli, ["promote", "--dir", str(project_dir), "--config", str(config_path)],
        input=f"secret-analysis\n{remote_bare}\n",
    )

    assert result.exit_code == 0

    new_meta = yaml.safe_load((root / "projects" / "secret-analysis" / ".plaibox.yaml").read_text())
    assert new_meta["private"] is True
    assert new_meta["remote"] == str(remote_bare)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py::test_promote_private_asks_for_remote_url tests/test_cli.py::test_promote_private_with_remote_url -v`
Expected: FAIL — promote shows "Create a GitHub repo?" instead of the private-specific prompt

- [ ] **Step 3: Modify `promote` to handle private projects**

In `src/plaibox/cli.py`, replace the "Offer to create a GitHub repo" block (lines ~244-266) with:

```python
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
                repo_url = result.stdout.strip()
                meta["remote"] = repo_url
                write_metadata(new_path, meta)
                click.echo(f"GitHub repo created: {repo_url}")
            else:
                click.echo(f"Failed to create repo: {result.stderr.strip()}", err=True)
                click.echo("You can create one later with: gh repo create")
        else:
            click.echo("Skipped. You can add a remote later with: gh repo create")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py::test_promote_private_asks_for_remote_url tests/test_cli.py::test_promote_private_with_remote_url -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: private projects get alternate remote prompt on promote"
```

---

### Task 4: `plaibox ls` shows private indicator

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/plaibox/cli.py:109-178`

- [ ] **Step 1: Write the failing test**

In `tests/test_cli.py`, add:

```python
def test_ls_shows_private_indicator_for_local_project(tmp_path):
    """Local private projects should show [private] suffix in ls output."""
    root = tmp_path / "plaibox"
    root.mkdir()
    (root / "sandbox").mkdir()
    (root / "projects").mkdir()
    (root / "archive").mkdir()

    project_dir = root / "sandbox" / "2026-04-13_secret"
    project_dir.mkdir()
    meta = {
        "id": "sec001",
        "name": "secret",
        "description": "secret project",
        "status": "sandbox",
        "created": "2026-04-13",
        "private": True,
        "tags": [],
        "tech": [],
    }
    (project_dir / ".plaibox.yaml").write_text(yaml.dump(meta))

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(cli, ["ls", "--config", str(config_path)])

    assert result.exit_code == 0
    # Should show the private indicator in the status
    assert "private" in result.output.lower()


def test_ls_shows_private_for_remote_private_project(tmp_path):
    """Remote private projects with no code should show 'private' status."""
    root = tmp_path / "plaibox"
    root.mkdir()
    (root / "sandbox").mkdir()
    (root / "projects").mkdir()
    (root / "archive").mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "root": str(root),
        "stale_days": 30,
        "sync": {
            "enabled": True,
            "repo": "unused",
            "sandbox_repos": [],
            "sandbox_branch_limit": 50,
            "machine_name": "test",
        },
    }))

    # Write remote registry with a private project
    registry = {
        "prv001": {
            "name": "patient-data",
            "description": "Patient analysis",
            "status": "sandbox",
            "created": "2026-04-13",
            "private": True,
            "remote": None,
            "sandbox_repo": None,
            "machine": "other-machine",
            "tags": [],
            "tech": [],
        }
    }
    registry_path = tmp_path / "remote-registry.yaml"
    registry_path.write_text(yaml.dump(registry))

    runner = CliRunner()
    result = runner.invoke(cli, ["ls", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "private" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py::test_ls_shows_private_indicator_for_local_project tests/test_cli.py::test_ls_shows_private_for_remote_private_project -v`
Expected: FAIL — `ls` doesn't know about the `private` field

- [ ] **Step 3: Update `ls_cmd` to show private indicators**

In `src/plaibox/cli.py`, in the `ls_cmd` function, modify the `status_display` logic (around line 163). Replace:

```python
        status_display = "remote" if p["space"] == "remote" else meta["status"]
```

With:

```python
        if p["space"] == "remote" and meta.get("private") and not meta.get("remote") and not meta.get("sandbox_repo"):
            status_display = "private"
        elif p["space"] == "remote":
            status_display = "remote"
        elif meta.get("private"):
            status_display = meta["status"] + "*"
        else:
            status_display = meta["status"]
```

The `*` suffix indicates a local private project (e.g., `sandbox*`). Remote private projects with no code show `private` as their status.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py::test_ls_shows_private_indicator_for_local_project tests/test_cli.py::test_ls_shows_private_for_remote_private_project -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: show private indicator in plaibox ls"
```

---

### Task 5: `plaibox open` handles private remote projects

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/plaibox/cli.py:445-516`

- [ ] **Step 1: Write the failing test**

In `tests/test_cli.py`, add:

```python
def test_open_private_remote_no_code_shows_message(tmp_path):
    """Opening a private remote project with no code should show a message, not offer to clone."""
    root = tmp_path / "plaibox"
    root.mkdir()
    (root / "sandbox").mkdir()
    (root / "projects").mkdir()
    (root / "archive").mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "root": str(root),
        "stale_days": 30,
        "sync": {
            "enabled": True,
            "repo": "unused",
            "sandbox_repos": [],
            "sandbox_branch_limit": 50,
            "machine_name": "test",
        },
    }))

    # Write remote registry with a private project (no code available)
    registry = {
        "prv001": {
            "name": "patient-data",
            "description": "Patient analysis",
            "status": "sandbox",
            "created": "2026-04-13",
            "private": True,
            "remote": None,
            "sandbox_repo": None,
            "machine": "work-macbook",
            "tags": [],
            "tech": [],
        }
    }
    registry_path = tmp_path / "remote-registry.yaml"
    registry_path.write_text(yaml.dump(registry))

    runner = CliRunner()
    result = runner.invoke(cli, ["open", "patient-data", "--config", str(config_path)])

    assert result.exit_code == 1
    assert "private" in result.output.lower()
    assert "work-macbook" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py::test_open_private_remote_no_code_shows_message -v`
Expected: FAIL — current code shows generic "no remote URL" message

- [ ] **Step 3: Update `_clone_remote_project` for private projects**

In `src/plaibox/cli.py`, in `_clone_remote_project`, replace the early-exit check (lines ~454-456):

```python
    if not remote_url and not sandbox_repo:
        click.echo(f"Project '{name}' exists on {meta.get('machine', 'another machine')} but has no remote URL.", err=True)
        raise SystemExit(1)
```

With:

```python
    if not remote_url and not sandbox_repo:
        if meta.get("private"):
            click.echo(f"Project '{name}' is private on {meta.get('machine', 'another machine')}. No remote code available.", err=True)
        else:
            click.echo(f"Project '{name}' exists on {meta.get('machine', 'another machine')} but has no remote URL.", err=True)
        raise SystemExit(1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py::test_open_private_remote_no_code_shows_message -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: show private-specific message when opening private remote project"
```

---

### Task 6: `plaibox unprivate` command

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/plaibox/cli.py`

- [ ] **Step 1: Write the failing test for basic unprivate**

In `tests/test_cli.py`, add:

```python
def test_unprivate_removes_flag(tmp_path):
    """unprivate should remove private: true from metadata."""
    root = tmp_path / "plaibox"
    root.mkdir()
    (root / "sandbox").mkdir()
    (root / "projects").mkdir()
    (root / "archive").mkdir()

    project_dir = root / "sandbox" / "2026-04-13_secret"
    project_dir.mkdir(parents=True)
    import subprocess
    subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)

    meta = {
        "id": "sec001",
        "name": "secret",
        "description": "secret project",
        "status": "sandbox",
        "created": "2026-04-13",
        "private": True,
        "tags": [],
        "tech": [],
    }
    (project_dir / ".plaibox.yaml").write_text(yaml.dump(meta))

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(cli, ["unprivate", "--dir", str(project_dir), "--config", str(config_path)])

    assert result.exit_code == 0

    new_meta = yaml.safe_load((project_dir / ".plaibox.yaml").read_text())
    assert new_meta.get("private") is not True


def test_unprivate_not_private_shows_error(tmp_path):
    """unprivate on a non-private project should show an error."""
    root = tmp_path / "plaibox"
    root.mkdir()
    (root / "sandbox").mkdir()
    (root / "projects").mkdir()
    (root / "archive").mkdir()

    project_dir = root / "sandbox" / "2026-04-13_public"
    project_dir.mkdir(parents=True)
    import subprocess
    subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)

    meta = {
        "id": "pub001",
        "name": "public",
        "description": "public project",
        "status": "sandbox",
        "created": "2026-04-13",
        "tags": [],
        "tech": [],
    }
    (project_dir / ".plaibox.yaml").write_text(yaml.dump(meta))

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(cli, ["unprivate", "--dir", str(project_dir), "--config", str(config_path)])

    assert result.exit_code == 1
    assert "not private" in result.output.lower() or "not marked as private" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py::test_unprivate_removes_flag tests/test_cli.py::test_unprivate_not_private_shows_error -v`
Expected: FAIL — `unprivate` command doesn't exist

- [ ] **Step 3: Write test for unprivate with sync retroactive push**

In `tests/test_cli.py`, add:

```python
def test_unprivate_with_sync_pushes_sandbox_branch(tmp_path):
    """unprivate with sync enabled should retroactively push code to sandbox repo."""
    import subprocess

    root = tmp_path / "plaibox"
    root.mkdir()
    (root / "sandbox").mkdir()
    (root / "projects").mkdir()
    (root / "archive").mkdir()

    # Create a bare repo to act as sandbox
    sandbox_bare = tmp_path / "sandbox-bare.git"
    subprocess.run(["git", "init", "--bare", str(sandbox_bare)], capture_output=True)

    # Create a bare repo to act as sync repo
    sync_bare = tmp_path / "sync-bare.git"
    subprocess.run(["git", "init", "--bare", str(sync_bare)], capture_output=True)

    project_dir = root / "sandbox" / "2026-04-13_secret"
    project_dir.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)

    meta = {
        "id": "sec001",
        "name": "secret",
        "description": "secret project",
        "status": "sandbox",
        "created": "2026-04-13",
        "private": True,
        "tags": [],
        "tech": [],
    }
    (project_dir / ".plaibox.yaml").write_text(yaml.dump(meta))

    # Create an initial commit so there's something to push
    subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=project_dir, capture_output=True)

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
    result = runner.invoke(cli, ["unprivate", "--dir", str(project_dir), "--config", str(config_path)])

    assert result.exit_code == 0

    # Sandbox repo should now have a branch
    ls_result = subprocess.run(
        ["git", "ls-remote", "--heads", str(sandbox_bare)],
        capture_output=True, text=True,
    )
    assert ls_result.stdout.strip() != ""

    # Local metadata should have sandbox_repo and sandbox_branch set
    new_meta = yaml.safe_load((project_dir / ".plaibox.yaml").read_text())
    assert new_meta.get("sandbox_repo") == str(sandbox_bare)
    assert new_meta.get("sandbox_branch") is not None
    assert new_meta.get("private") is not True
```

- [ ] **Step 4: Implement `unprivate` command**

In `src/plaibox/cli.py`, add the `unprivate` command. Place it after the `delete` command (around line 368):

```python
@cli.command()
@click.option("--config", "config_path", default=None, help="Path to config file.")
@click.option("--dir", "project_dir", default=".", help="Project directory.")
def unprivate(config_path: str | None, project_dir: str):
    """Remove private flag from a project, enabling code sync."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    project_path = Path(project_dir).resolve()

    meta = read_metadata(project_path)
    if meta is None:
        click.echo("Error: not a plaibox project (no .plaibox.yaml found).", err=True)
        raise SystemExit(1)

    if not meta.get("private"):
        click.echo("Error: project is not marked as private.", err=True)
        raise SystemExit(1)

    # Remove private flag
    del meta["private"]
    write_metadata(project_path, meta)

    # Retroactively push to sandbox repo if sync enabled and project is a sandbox
    if is_sync_enabled(cfg) and meta["status"] == "sandbox":
        sync_cfg = get_sync_config(cfg)
        from plaibox.sync import get_active_sandbox_repo
        sandbox_repo = get_active_sandbox_repo(sync_cfg)

        if sandbox_repo:
            pid = meta.get("id", "")
            branch_name = f"{slugify(meta['description'])}-{pid}"
            push_sandbox_branch(project_path, sandbox_repo, branch_name)

            meta["sandbox_repo"] = sandbox_repo
            meta["sandbox_branch"] = branch_name
            write_metadata(project_path, meta)

            click.echo(f"Code pushed to sandbox repo (branch: {branch_name}).")

        # Update sync metadata
        pid = meta.get("id", "")
        auto_push(
            project_id=pid,
            local_meta=meta,
            space="sandbox",
            remote=meta.get("remote"),
            sandbox_repo=meta.get("sandbox_repo"),
            sync_config=sync_cfg,
            config_dir=Path(config_path).parent if config_path else DEFAULT_CONFIG_PATH.parent,
        )

    click.echo("Project is no longer private.")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py::test_unprivate_removes_flag tests/test_cli.py::test_unprivate_not_private_shows_error tests/test_cli.py::test_unprivate_with_sync_pushes_sandbox_branch -v`
Expected: PASS

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: add plaibox unprivate command"
```
