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
