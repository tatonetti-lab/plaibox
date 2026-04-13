from pathlib import Path
from datetime import date
import yaml

from plaibox.project import slugify, make_sandbox_dirname, detect_tech, discover_projects, project_id, fuzzy_score, fuzzy_match, write_gitignore


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
    assert "id" in projects[0]
    assert len(projects[0]["id"]) == 6


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


# --- fuzzy matching tests ---


def test_fuzzy_score_exact():
    assert fuzzy_score("dashboard", "dashboard") == 100


def test_fuzzy_score_prefix():
    assert fuzzy_score("dash", "dashboard") == 80


def test_fuzzy_score_substring():
    assert fuzzy_score("board", "dashboard") == 60


def test_fuzzy_score_word_boundary():
    # "ld" matches initials of "lab-dashboard"
    assert fuzzy_score("ld", "lab-dashboard") == 40


def test_fuzzy_score_subsequence():
    # "dshb" chars appear in order in "dashboard"
    assert fuzzy_score("dshb", "dashboard") == 20


def test_fuzzy_score_no_match():
    assert fuzzy_score("xyz", "dashboard") == 0


def test_fuzzy_score_ranking():
    """Exact > prefix > substring > word boundary > subsequence."""
    assert fuzzy_score("lab", "lab") > fuzzy_score("lab", "lab-dashboard")
    assert fuzzy_score("lab", "lab-dashboard") > fuzzy_score("lab", "my-lab-thing")
    assert fuzzy_score("lab", "my-lab-thing") > fuzzy_score("ld", "lab-dashboard")


def test_fuzzy_match_returns_ranked(tmp_plaibox_root):
    # Create projects with different match quality
    for name, desc in [
        ("lab-dashboard", "Dashboard for lab results"),
        ("my-lab", "Lab experiment tracker"),
        ("dashboard", "Main dashboard"),
    ]:
        d = tmp_plaibox_root / "sandbox" / f"2026-04-10_{name}"
        d.mkdir()
        (d / ".plaibox.yaml").write_text(yaml.dump({
            "name": name, "description": desc,
            "status": "sandbox", "created": "2026-04-10", "tags": [], "tech": [],
        }))

    projects = discover_projects(tmp_plaibox_root)
    matches = fuzzy_match("lab", projects)

    assert len(matches) == 2  # "dashboard" shouldn't match "lab"
    # "my-lab" has "lab" as a substring in name (score 60)
    # "lab-dashboard" has "lab" as a prefix in name (score 80)
    assert matches[0]["meta"]["name"] == "lab-dashboard"
    assert matches[1]["meta"]["name"] == "my-lab"


def test_fuzzy_match_subsequence_finds_typos(tmp_plaibox_root):
    d = tmp_plaibox_root / "sandbox" / "2026-04-10_patient-tracker"
    d.mkdir()
    (d / ".plaibox.yaml").write_text(yaml.dump({
        "name": "patient-tracker", "description": "Track patients",
        "status": "sandbox", "created": "2026-04-10", "tags": [], "tech": [],
    }))

    projects = discover_projects(tmp_plaibox_root)
    matches = fuzzy_match("pttrk", projects)  # subsequence of "patient-tracker"
    assert len(matches) == 1
    assert matches[0]["meta"]["name"] == "patient-tracker"


# --- gitignore tests ---


def test_write_gitignore_creates_file(tmp_path):
    write_gitignore(tmp_path)
    gitignore = tmp_path / ".gitignore"
    assert gitignore.exists()
    content = gitignore.read_text()
    assert ".venv/" in content
    assert "__pycache__/" in content
    assert "node_modules/" in content
    assert ".DS_Store" in content


def test_write_gitignore_preserves_existing(tmp_path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("my-custom-ignore\n")
    write_gitignore(tmp_path)
    assert gitignore.read_text() == "my-custom-ignore\n"
