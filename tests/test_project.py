from pathlib import Path
from datetime import date
import yaml

from plaibox.project import slugify, make_sandbox_dirname, detect_tech, discover_projects


def test_slugify_basic():
    assert slugify("Dashboard for tracking lab results") == "dashboard-for-tracking-lab-results"


def test_slugify_special_chars():
    assert slugify("My app! (v2)") == "my-app-v2"


def test_slugify_extra_hyphens():
    assert slugify("hello   world") == "hello-world"


def test_make_sandbox_dirname():
    result = make_sandbox_dirname("Dashboard idea", date(2026, 4, 10))
    assert result == "2026-04-10_dashboard-idea"


def test_detect_tech_python(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask")
    assert "python" in detect_tech(tmp_path)


def test_detect_tech_node(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    assert "node" in detect_tech(tmp_path)


def test_detect_tech_multiple(tmp_path):
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / "package.json").write_text("{}")
    tech = detect_tech(tmp_path)
    assert "python" in tech
    assert "node" in tech


def test_detect_tech_empty(tmp_path):
    assert detect_tech(tmp_path) == []


def test_discover_projects(tmp_plaibox_root):
    # Create a sandbox project with metadata
    proj = tmp_plaibox_root / "sandbox" / "2026-04-10_test-project"
    proj.mkdir()
    meta = {"name": "test-project", "description": "A test", "status": "sandbox",
            "created": "2026-04-10", "tags": [], "tech": []}
    (proj / ".plaibox.yaml").write_text(yaml.dump(meta))

    projects = discover_projects(tmp_plaibox_root)
    assert len(projects) == 1
    assert projects[0]["meta"]["name"] == "test-project"
    assert projects[0]["space"] == "sandbox"
    assert projects[0]["path"] == proj


def test_discover_projects_multiple_spaces(tmp_plaibox_root):
    # Sandbox project
    sb = tmp_plaibox_root / "sandbox" / "2026-04-10_experiment"
    sb.mkdir()
    (sb / ".plaibox.yaml").write_text(yaml.dump(
        {"name": "experiment", "description": "An experiment", "status": "sandbox",
         "created": "2026-04-10", "tags": [], "tech": []}
    ))

    # Promoted project
    pj = tmp_plaibox_root / "projects" / "real-app"
    pj.mkdir()
    (pj / ".plaibox.yaml").write_text(yaml.dump(
        {"name": "real-app", "description": "A real app", "status": "project",
         "created": "2026-04-01", "tags": [], "tech": []}
    ))

    projects = discover_projects(tmp_plaibox_root)
    assert len(projects) == 2
    spaces = {p["space"] for p in projects}
    assert spaces == {"sandbox", "projects"}
