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
        input="cool-app\n"
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

    # Promote
    result = runner.invoke(
        cli, ["promote", "--dir", project_path, *cfg_flag],
        input="my-real-app\n"
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


def test_init_shell_outputs_function():
    runner = CliRunner()
    result = runner.invoke(cli, ["init-shell"])
    assert result.exit_code == 0
    assert "plaibox()" in result.output or "function plaibox" in result.output
