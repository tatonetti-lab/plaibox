# tests/test_cli.py
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from click.testing import CliRunner
import yaml

from plaibox.cli import cli


def test_new_creates_sandbox_project(tmp_path, monkeypatch):
    root = tmp_path / "plaibox"
    root.mkdir()
    (root / "sandbox").mkdir()
    (root / "projects").mkdir()
    (root / "archive").mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(cli, ["new", "my test project", "--config", str(config_path)])

    assert result.exit_code == 0

    # Should have created a directory in sandbox
    sandbox_dirs = list((root / "sandbox").iterdir())
    assert len(sandbox_dirs) == 1

    project_dir = sandbox_dirs[0]
    assert "my-test-project" in project_dir.name

    # Should have .plaibox.yaml
    meta = yaml.safe_load((project_dir / ".plaibox.yaml").read_text())
    assert meta["description"] == "my test project"
    assert meta["status"] == "sandbox"

    # Should have initialized git
    assert (project_dir / ".git").exists()

    # Should print the path
    assert str(project_dir) in result.output


def test_new_prompts_when_no_description(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    (root / "sandbox").mkdir()
    (root / "projects").mkdir()
    (root / "archive").mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(cli, ["new", "--config", str(config_path)],
                           input="prompted project\n")

    assert result.exit_code == 0
    sandbox_dirs = list((root / "sandbox").iterdir())
    assert len(sandbox_dirs) == 1
    assert "prompted-project" in sandbox_dirs[0].name


def _make_project(root, space, dirname, meta):
    """Helper to create a project with metadata in a given space."""
    project_dir = root / space / dirname
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / ".plaibox.yaml").write_text(yaml.dump(meta))
    return project_dir


def test_ls_shows_all_projects(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    _make_project(root, "sandbox", "2026-04-10_experiment", {
        "name": "experiment", "description": "An experiment",
        "status": "sandbox", "created": "2026-04-10", "tags": [], "tech": [],
    })
    _make_project(root, "projects", "real-app", {
        "name": "real-app", "description": "A real app",
        "status": "project", "created": "2026-04-01", "tags": [], "tech": [],
    })

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(cli, ["ls", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "experiment" in result.output
    assert "real-app" in result.output
    assert "plaibox open" in result.output  # footer reminder


def test_ls_filters_by_space(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    _make_project(root, "sandbox", "2026-04-10_experiment", {
        "name": "experiment", "description": "An experiment",
        "status": "sandbox", "created": "2026-04-10", "tags": [], "tech": [],
    })
    _make_project(root, "projects", "real-app", {
        "name": "real-app", "description": "A real app",
        "status": "project", "created": "2026-04-01", "tags": [], "tech": [],
    })

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(cli, ["ls", "sandbox", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "experiment" in result.output
    assert "real-app" not in result.output


def test_ls_stale_flag(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    old_dir = _make_project(root, "sandbox", "2026-03-01_old-thing", {
        "name": "old-thing", "description": "An old experiment",
        "status": "sandbox", "created": "2026-03-01", "tags": [], "tech": [],
    })
    # Set modification time to 60 days ago
    old_date = datetime.combine(date.today() - timedelta(days=60), datetime.min.time())
    os.utime(old_dir, (old_date.timestamp(), old_date.timestamp()))

    _make_project(root, "sandbox", "2026-04-10_new-thing", {
        "name": "new-thing", "description": "A new experiment",
        "status": "sandbox", "created": "2026-04-10", "tags": [], "tech": [],
    })

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(cli, ["ls", "--stale", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "old-thing" in result.output
    assert "new-thing" not in result.output


def test_promote_moves_to_projects(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    proj = _make_project(root, "sandbox", "2026-04-10_my-experiment", {
        "name": "my-experiment", "description": "An experiment",
        "status": "sandbox", "created": "2026-04-10", "tags": [], "tech": [],
    })

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(
        cli, ["promote", "--config", str(config_path), "--dir", str(proj)],
        input="cool-app\nn\n"  # name, then decline GitHub repo
    )

    assert result.exit_code == 0

    # Should have moved to projects/cool-app
    new_dir = root / "projects" / "cool-app"
    assert new_dir.exists()
    assert not proj.exists()

    # Metadata should be updated
    meta = yaml.safe_load((new_dir / ".plaibox.yaml").read_text())
    assert meta["status"] == "project"
    assert meta["name"] == "cool-app"
    assert "You can add a remote later" in result.output


def test_promote_rejects_non_sandbox(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    proj = _make_project(root, "projects", "already-promoted", {
        "name": "already-promoted", "description": "Already a project",
        "status": "project", "created": "2026-04-01", "tags": [], "tech": [],
    })

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(
        cli, ["promote", "--config", str(config_path), "--dir", str(proj)]
    )

    assert result.exit_code != 0 or "only promote sandbox" in result.output.lower()


def test_archive_moves_to_archive(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    proj = _make_project(root, "sandbox", "2026-04-10_throwaway", {
        "name": "throwaway", "description": "A throwaway",
        "status": "sandbox", "created": "2026-04-10", "tags": [], "tech": [],
    })

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(
        cli, ["archive", "--config", str(config_path), "--dir", str(proj)]
    )

    assert result.exit_code == 0
    assert not proj.exists()

    archived = list((root / "archive").iterdir())
    assert len(archived) == 1

    meta = yaml.safe_load((archived[0] / ".plaibox.yaml").read_text())
    assert meta["status"] == "archived"


def test_delete_removes_archived_project(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    proj = _make_project(root, "archive", "2026-04-10_old-stuff", {
        "name": "old-stuff", "description": "Old stuff",
        "status": "archived", "created": "2026-04-10", "tags": [], "tech": [],
    })

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(
        cli, ["delete", "--config", str(config_path), "--dir", str(proj)],
        input="y\n"
    )

    assert result.exit_code == 0
    assert not proj.exists()


def test_delete_rejects_non_archived(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    proj = _make_project(root, "sandbox", "2026-04-10_active", {
        "name": "active", "description": "Still active",
        "status": "sandbox", "created": "2026-04-10", "tags": [], "tech": [],
    })

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(
        cli, ["delete", "--config", str(config_path), "--dir", str(proj)]
    )

    assert result.exit_code != 0 or "only delete archived" in result.output.lower()


def test_open_finds_by_name(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    proj = _make_project(root, "projects", "lab-dashboard", {
        "name": "lab-dashboard", "description": "Dashboard for lab results",
        "status": "project", "created": "2026-04-01", "tags": [], "tech": [],
    })

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(cli, ["open", "lab", "--config", str(config_path)])

    assert result.exit_code == 0
    assert str(proj) in result.output


def test_open_finds_by_description(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    proj = _make_project(root, "sandbox", "2026-04-10_xyz", {
        "name": "xyz", "description": "Tracking patient outcomes",
        "status": "sandbox", "created": "2026-04-10", "tags": [], "tech": [],
    })

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(cli, ["open", "patient", "--config", str(config_path)])

    assert result.exit_code == 0
    assert str(proj) in result.output


def test_open_no_match(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(cli, ["open", "nonexistent", "--config", str(config_path)])

    assert "no project" in result.output.lower() or result.exit_code != 0


def test_tidy_prompts_for_stale_projects(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    old_proj = _make_project(root, "sandbox", "2026-03-01_old-experiment", {
        "name": "old-experiment", "description": "An old experiment",
        "status": "sandbox", "created": "2026-03-01", "tags": [], "tech": [],
    })
    # Make it look old
    old_date = datetime.combine(date.today() - timedelta(days=60), datetime.min.time())
    os.utime(old_proj, (old_date.timestamp(), old_date.timestamp()))

    _make_project(root, "sandbox", "2026-04-10_fresh", {
        "name": "fresh", "description": "A fresh project",
        "status": "sandbox", "created": "2026-04-10", "tags": [], "tech": [],
    })

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    # Choose "skip" for the stale project
    result = runner.invoke(
        cli, ["tidy", "--config", str(config_path)],
        input="s\n"
    )

    assert result.exit_code == 0
    assert "old-experiment" in result.output
    # Fresh project should not appear in tidy
    assert "fresh" not in result.output


def test_tidy_archive_action(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    old_proj = _make_project(root, "sandbox", "2026-03-01_stale-thing", {
        "name": "stale-thing", "description": "A stale project",
        "status": "sandbox", "created": "2026-03-01", "tags": [], "tech": [],
    })
    old_date = datetime.combine(date.today() - timedelta(days=60), datetime.min.time())
    os.utime(old_proj, (old_date.timestamp(), old_date.timestamp()))

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    # Choose "archive"
    result = runner.invoke(
        cli, ["tidy", "--config", str(config_path)],
        input="a\n"
    )

    assert result.exit_code == 0
    assert not old_proj.exists()
    assert (root / "archive" / "2026-03-01_stale-thing").exists()


def test_full_lifecycle(tmp_path):
    """End-to-end: new -> ls -> promote -> archive -> delete."""
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    cfg_flag = ["--config", str(config_path)]

    # Create
    result = runner.invoke(cli, ["new", "lifecycle test", *cfg_flag])
    assert result.exit_code == 0
    project_path = result.output.strip()
    assert Path(project_path).exists()

    # List — should appear as sandbox
    result = runner.invoke(cli, ["ls", *cfg_flag])
    assert "lifecycle-test" in result.output
    assert "sandbox" in result.output

    # Promote (decline GitHub repo)
    result = runner.invoke(
        cli, ["promote", "--dir", project_path, *cfg_flag],
        input="my-real-app\nn\n"
    )
    assert result.exit_code == 0
    promoted_path = root / "projects" / "my-real-app"
    assert promoted_path.exists()

    # List — should appear as project
    result = runner.invoke(cli, ["ls", *cfg_flag])
    assert "my-real-app" in result.output
    assert "project" in result.output

    # Archive
    result = runner.invoke(
        cli, ["archive", "--dir", str(promoted_path), *cfg_flag]
    )
    assert result.exit_code == 0

    # Delete
    archived_path = root / "archive" / "my-real-app"
    result = runner.invoke(
        cli, ["delete", "--dir", str(archived_path), *cfg_flag],
        input="y\n"
    )
    assert result.exit_code == 0
    assert not archived_path.exists()


def test_session_save_and_show(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    proj = _make_project(root, "sandbox", "2026-04-10_my-proj", {
        "name": "my-proj", "description": "My project",
        "status": "sandbox", "created": "2026-04-10", "tags": [], "tech": [],
    })

    runner = CliRunner()

    # Save a session
    result = runner.invoke(cli, ["session", "--save", "claude --resume abc123", "--dir", str(proj)])
    assert result.exit_code == 0
    assert "Session saved" in result.output

    # Show the session
    result = runner.invoke(cli, ["session", "--dir", str(proj)])
    assert result.exit_code == 0
    assert "claude --resume abc123" in result.output

    # Verify it's in the yaml
    meta = yaml.safe_load((proj / ".plaibox.yaml").read_text())
    assert meta["session"] == "claude --resume abc123"


def test_session_no_session(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    proj = _make_project(root, "sandbox", "2026-04-10_empty", {
        "name": "empty", "description": "No session",
        "status": "sandbox", "created": "2026-04-10", "tags": [], "tech": [],
    })

    runner = CliRunner()
    result = runner.invoke(cli, ["session", "--dir", str(proj)])
    assert result.exit_code == 0
    assert "No session saved" in result.output


def test_open_finds_by_id(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    proj = _make_project(root, "projects", "my-app", {
        "name": "my-app", "description": "My application",
        "status": "project", "created": "2026-04-01", "tags": [], "tech": [],
    })

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    # First get the ID from ls output
    runner = CliRunner()
    ls_result = runner.invoke(cli, ["ls", "--config", str(config_path)])
    # Extract the 6-char ID from the output (first non-space token on the data line)
    for line in ls_result.output.splitlines():
        if "my-app" in line and "ID" not in line:
            proj_id = line.strip().split()[0]
            break

    result = runner.invoke(cli, ["open", proj_id, "--config", str(config_path)])
    assert result.exit_code == 0
    assert str(proj) in result.output


def test_init_shell_outputs_function():
    runner = CliRunner()
    result = runner.invoke(cli, ["init-shell"])
    assert result.exit_code == 0
    assert "plaibox()" in result.output or "function plaibox" in result.output


def test_new_creates_gitignore(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(cli, ["new", "test gitignore", "--config", str(config_path)])

    assert result.exit_code == 0
    project_path = Path(result.output.strip())
    gitignore = project_path / ".gitignore"
    assert gitignore.exists()
    assert ".venv/" in gitignore.read_text()


def test_open_fuzzy_subsequence(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    proj = _make_project(root, "projects", "patient-tracker", {
        "name": "patient-tracker", "description": "Track patient outcomes",
        "status": "project", "created": "2026-04-01", "tags": [], "tech": [],
    })

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    # "pttrk" is a subsequence of "patient-tracker"
    result = runner.invoke(cli, ["open", "pttrk", "--config", str(config_path)])

    assert result.exit_code == 0
    assert str(proj) in result.output


def test_open_fuzzy_word_initials(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    proj = _make_project(root, "projects", "lab-dashboard", {
        "name": "lab-dashboard", "description": "Dashboard for lab results",
        "status": "project", "created": "2026-04-01", "tags": [], "tech": [],
    })

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    # "ld" matches word initials of "lab-dashboard"
    result = runner.invoke(cli, ["open", "ld", "--config", str(config_path)])

    assert result.exit_code == 0
    assert str(proj) in result.output


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
        elif cmd[0] == "gh" and "repo" in cmd and "view" in cmd:
            r.stdout = "git@github.com:user/plaibox-sync.git"
        elif cmd[0] == "git" and cmd[1] == "clone":
            # Simulate empty repo that can't be cloned yet
            r.returncode = 128
            r.stderr = "Repository is empty"
        elif cmd[0] == "git":
            r.returncode = 0
        return r

    monkeypatch.setattr("plaibox.cli.subprocess.run", mock_run)
    monkeypatch.setattr("plaibox.sync.subprocess.run", mock_run)

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


# --- import command tests ---


def test_import_to_sandbox(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    # Create a project outside of plaibox
    external = tmp_path / "my-external-project"
    external.mkdir()
    (external / "main.py").write_text("print('hello')")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["import", str(external), "--config", str(config_path)],
        input="A cool external project\ns\n",  # description, then sandbox
    )

    assert result.exit_code == 0
    assert not external.exists()  # original moved

    # Should exist in sandbox with date prefix
    sandbox_dirs = list((root / "sandbox").iterdir())
    assert len(sandbox_dirs) == 1
    new_dir = sandbox_dirs[0]
    assert "a-cool-external-project" in new_dir.name

    # Should have metadata
    meta = yaml.safe_load((new_dir / ".plaibox.yaml").read_text())
    assert meta["status"] == "sandbox"
    assert meta["description"] == "A cool external project"

    # Should have preserved original files
    assert (new_dir / "main.py").exists()

    # Should print the new path
    assert str(new_dir) in result.output


def test_import_to_project(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    external = tmp_path / "my-app"
    external.mkdir()
    (external / "index.js").write_text("console.log('hi')")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["import", str(external), "--config", str(config_path)],
        input="My application\np\nmy-cool-app\n",  # description, project, name
    )

    assert result.exit_code == 0
    assert not external.exists()

    new_dir = root / "projects" / "my-cool-app"
    assert new_dir.exists()

    meta = yaml.safe_load((new_dir / ".plaibox.yaml").read_text())
    assert meta["status"] == "project"
    assert meta["name"] == "my-cool-app"


def test_import_with_project_flag(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    external = tmp_path / "my-app"
    external.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["import", str(external), "--project", "--config", str(config_path)],
        input="My application\nmy-app\n",  # description, name
    )

    assert result.exit_code == 0
    assert (root / "projects" / "my-app").exists()


def test_import_preserves_existing_metadata(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    # Create external project with existing .plaibox.yaml
    external = tmp_path / "already-tagged"
    external.mkdir()
    existing_meta = {
        "name": "already-tagged",
        "description": "Was already tracked",
        "status": "sandbox",
        "created": "2026-01-15",
        "tags": ["important"],
        "tech": ["python"],
    }
    (external / ".plaibox.yaml").write_text(yaml.dump(existing_meta))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["import", str(external), "--config", str(config_path)],
        input="s\n",  # sandbox (no description prompt since metadata exists)
    )

    assert result.exit_code == 0
    sandbox_dirs = list((root / "sandbox").iterdir())
    assert len(sandbox_dirs) == 1

    meta = yaml.safe_load((sandbox_dirs[0] / ".plaibox.yaml").read_text())
    assert meta["tags"] == ["important"]
    assert meta["created"] == "2026-01-15"


def test_import_rejects_path_inside_plaibox(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    # Try to import something already inside plaibox root
    inside = root / "sandbox" / "2026-04-10_already-here"
    inside.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["import", str(inside), "--config", str(config_path)],
    )

    assert result.exit_code != 0 or "already inside" in result.output.lower()


def test_import_rejects_nonexistent_path(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["import", str(tmp_path / "nope"), "--config", str(config_path)],
    )

    assert result.exit_code != 0 or "does not exist" in result.output.lower()


def test_import_inits_git_if_missing(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    external = tmp_path / "no-git"
    external.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["import", str(external), "--config", str(config_path)],
        input="A project without git\ns\n",
    )

    assert result.exit_code == 0
    sandbox_dirs = list((root / "sandbox").iterdir())
    new_dir = sandbox_dirs[0]
    assert (new_dir / ".git").exists()


def test_new_with_python_flag_creates_venv(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(cli, ["new", "python experiment", "--python", "--config", str(config_path)])

    assert result.exit_code == 0
    project_path = Path(result.output.strip())
    assert (project_path / ".venv").exists()
    assert (project_path / ".venv" / "bin" / "activate").exists()

    meta = yaml.safe_load((project_path / ".plaibox.yaml").read_text())
    assert "python" in meta["tech"]


def test_new_without_python_flag_no_venv(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    runner = CliRunner()
    result = runner.invoke(cli, ["new", "plain project", "--config", str(config_path)])

    assert result.exit_code == 0
    project_path = Path(result.output.strip())
    assert not (project_path / ".venv").exists()


def test_import_offers_venv_for_python_project(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    external = tmp_path / "py-project"
    external.mkdir()
    (external / "pyproject.toml").write_text("[project]\nname = 'test'\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["import", str(external), "--config", str(config_path)],
        input="A python project\ns\ny\n",  # description, sandbox, yes to venv
    )

    assert result.exit_code == 0
    sandbox_dirs = list((root / "sandbox").iterdir())
    new_dir = sandbox_dirs[0]
    assert (new_dir / ".venv").exists()


def test_import_skip_venv_for_python_project(tmp_path):
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    external = tmp_path / "py-project"
    external.mkdir()
    (external / "requirements.txt").write_text("flask\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["import", str(external), "--config", str(config_path)],
        input="A python project\ns\nn\n",  # description, sandbox, no to venv
    )

    assert result.exit_code == 0
    sandbox_dirs = list((root / "sandbox").iterdir())
    new_dir = sandbox_dirs[0]
    assert not (new_dir / ".venv").exists()


def test_import_preserves_existing_git(tmp_path):
    import subprocess

    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    external = tmp_path / "has-git"
    external.mkdir()
    subprocess.run(["git", "init"], cwd=external, capture_output=True)
    (external / "file.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=external, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init", "--allow-empty"],
        cwd=external,
        capture_output=True,
        env={**__import__("os").environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@test.com",
             "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@test.com"},
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["import", str(external), "--config", str(config_path)],
        input="Has git already\ns\n",
    )

    assert result.exit_code == 0
    sandbox_dirs = list((root / "sandbox").iterdir())
    new_dir = sandbox_dirs[0]
    assert (new_dir / ".git").exists()

    # Verify git history was preserved
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=new_dir, capture_output=True, text=True
    )
    assert "init" in log.stdout


# --- scan command tests ---


def _setup_scan_env(tmp_path):
    """Helper to set up plaibox root, config, and a scan directory with projects."""
    root = tmp_path / "plaibox"
    root.mkdir()
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"root": str(root), "stale_days": 30}))

    scan_dir = tmp_path / "Projects"
    scan_dir.mkdir()

    return root, config_path, scan_dir


def test_scan_import_project(tmp_path):
    root, config_path, scan_dir = _setup_scan_env(tmp_path)

    proj = scan_dir / "my-app"
    proj.mkdir()
    (proj / "main.py").write_text("print('hi')")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["scan", str(scan_dir), "--config", str(config_path)],
        input="i\nMy cool app\ns\n",  # import, description, sandbox
    )

    assert result.exit_code == 0
    assert "Imported" in result.output
    assert not proj.exists()

    sandbox_dirs = list((root / "sandbox").iterdir())
    assert len(sandbox_dirs) == 1
    assert "my-cool-app" in sandbox_dirs[0].name


def test_scan_skip_project(tmp_path):
    root, config_path, scan_dir = _setup_scan_env(tmp_path)

    proj = scan_dir / "skip-me"
    proj.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["scan", str(scan_dir), "--config", str(config_path)],
        input="s\n",
    )

    assert result.exit_code == 0
    assert "Skipped" in result.output
    assert proj.exists()  # still there


def test_scan_never_persists(tmp_path):
    root, config_path, scan_dir = _setup_scan_env(tmp_path)

    proj = scan_dir / "ignore-me"
    proj.mkdir()

    runner = CliRunner()

    # First scan: choose "never"
    result = runner.invoke(
        cli,
        ["scan", str(scan_dir), "--config", str(config_path)],
        input="n\n",
    )

    assert result.exit_code == 0
    assert "Ignored permanently" in result.output
    assert proj.exists()

    # Verify ignore file was written
    ignore_path = config_path.parent / "scan-ignore"
    assert ignore_path.exists()
    assert str(proj.resolve()) in ignore_path.read_text()

    # Second scan: project should not appear
    result = runner.invoke(
        cli,
        ["scan", str(scan_dir), "--config", str(config_path)],
    )

    assert "No new projects found" in result.output


def test_scan_git_only_flag(tmp_path):
    import subprocess as sp

    root, config_path, scan_dir = _setup_scan_env(tmp_path)

    # Project with git
    git_proj = scan_dir / "has-git"
    git_proj.mkdir()
    sp.run(["git", "init"], cwd=git_proj, capture_output=True)

    # Project without git
    no_git_proj = scan_dir / "no-git"
    no_git_proj.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["scan", str(scan_dir), "--git-only", "--config", str(config_path)],
        input="s\n",
    )

    assert result.exit_code == 0
    assert "has-git" in result.output
    assert "no-git" not in result.output


def test_scan_skips_hidden_dirs(tmp_path):
    root, config_path, scan_dir = _setup_scan_env(tmp_path)

    hidden = scan_dir / ".hidden-thing"
    hidden.mkdir()
    visible = scan_dir / "visible-thing"
    visible.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["scan", str(scan_dir), "--config", str(config_path)],
        input="s\n",
    )

    assert "hidden-thing" not in result.output
    assert "visible-thing" in result.output


def test_scan_skips_existing_plaibox_projects(tmp_path):
    root, config_path, scan_dir = _setup_scan_env(tmp_path)

    # A directory that already has .plaibox.yaml
    already_managed = scan_dir / "already-managed"
    already_managed.mkdir()
    (already_managed / ".plaibox.yaml").write_text(yaml.dump({
        "name": "already-managed", "description": "test",
        "status": "sandbox", "created": "2026-04-10", "tags": [], "tech": [],
    }))

    # A directory without metadata
    new_proj = scan_dir / "new-proj"
    new_proj.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["scan", str(scan_dir), "--config", str(config_path)],
        input="s\n",
    )

    assert "already-managed" not in result.output
    assert "new-proj" in result.output


def test_scan_empty_directory(tmp_path):
    root, config_path, scan_dir = _setup_scan_env(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["scan", str(scan_dir), "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert "No new projects found" in result.output


def test_scan_multiple_projects(tmp_path):
    root, config_path, scan_dir = _setup_scan_env(tmp_path)

    (scan_dir / "app-one").mkdir()
    (scan_dir / "app-two").mkdir()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["scan", str(scan_dir), "--config", str(config_path)],
        input="i\nFirst app\ns\ns\n",  # import first, skip second
    )

    assert result.exit_code == 0
    assert "Imported 1 project." in result.output
    assert not (scan_dir / "app-one").exists()
    assert (scan_dir / "app-two").exists()


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
    from plaibox.sync import ensure_sync_repo_cloned, read_remote_projects, pull_sync_repo
    sync_cfg = yaml.safe_load(config_path.read_text())["sync"]
    repo_path = ensure_sync_repo_cloned(sync_cfg, config_path.parent)
    pull_sync_repo(repo_path)
    remote = read_remote_projects(repo_path)
    assert len(remote) == 1
    assert remote[0]["meta"]["name"] == "sync-test-project"


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

    # Should have created a directory in sandbox
    sandbox_dirs = list((root / "sandbox").iterdir())
    assert len(sandbox_dirs) == 1

    # Metadata should have private: true
    meta = yaml.safe_load((sandbox_dirs[0] / ".plaibox.yaml").read_text())
    assert meta["private"] is True
    assert meta["description"] == "secret research"


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
    # Should show the private indicator (asterisk) in the status
    assert "sandbox*" in result.output.lower()


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
