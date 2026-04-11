# tests/test_cli.py
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
