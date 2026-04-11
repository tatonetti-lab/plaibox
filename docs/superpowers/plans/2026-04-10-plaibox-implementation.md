# Plaibox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that manages the lifecycle of vibe-coded projects through a sandbox/projects/archive model with lightweight YAML metadata.

**Architecture:** A `click`-based CLI that operates on a managed directory tree (`~/plaibox/{sandbox,projects,archive}/`). Each project contains a `.plaibox.yaml` metadata file. Configuration lives at `~/.plaibox/config.yaml`. No database — the filesystem is the data store.

**Tech Stack:** Python 3.10+, click, PyYAML, pytest

---

## File Structure

```
plaibox/
  pyproject.toml                  # Package config, dependencies, entry point
  src/
    plaibox/
      __init__.py                 # Version string
      cli.py                      # Click group and command definitions
      config.py                   # Load/create ~/.plaibox/config.yaml
      metadata.py                 # Read/write .plaibox.yaml files
      project.py                  # Project discovery, tech detection, slug generation
      shell.py                    # Shell integration (init-shell output)
  tests/
    conftest.py                   # Shared fixtures (tmp plaibox root, sample projects)
    test_config.py
    test_metadata.py
    test_project.py
    test_cli.py
    test_shell.py
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/plaibox/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "plaibox"
version = "0.1.0"
description = "Lifecycle manager for vibe-coded projects"
requires-python = ">=3.10"
dependencies = [
    "click>=8.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]

[project.scripts]
plaibox = "plaibox.cli:cli"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Create src/plaibox/__init__.py**

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Install in editable mode and verify**

Run: `pip install -e ".[dev]"`
Then: `plaibox --help`
Expected: Click shows a help message (even if empty, confirms entry point works)

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/plaibox/__init__.py
git commit -m "feat: scaffold plaibox package with click entry point"
```

---

### Task 2: Configuration Module

**Files:**
- Create: `src/plaibox/config.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Create shared test fixtures**

```python
# tests/conftest.py
import pytest
from pathlib import Path


@pytest.fixture
def tmp_plaibox_root(tmp_path):
    """A temporary plaibox root directory with sandbox/projects/archive."""
    root = tmp_path / "plaibox"
    root.mkdir()
    (root / "sandbox").mkdir()
    (root / "projects").mkdir()
    (root / "archive").mkdir()
    return root


@pytest.fixture
def tmp_config_dir(tmp_path):
    """A temporary ~/.plaibox config directory."""
    config_dir = tmp_path / ".plaibox"
    config_dir.mkdir()
    return config_dir
```

- [ ] **Step 2: Write failing tests for config**

```python
# tests/test_config.py
from pathlib import Path
import yaml

from plaibox.config import load_config, DEFAULT_CONFIG


def test_load_config_creates_default_when_missing(tmp_config_dir):
    config_path = tmp_config_dir / "config.yaml"
    config = load_config(config_path)

    assert config["root"] == str(Path.home() / "plaibox")
    assert config["stale_days"] == 30
    assert config_path.exists()


def test_load_config_reads_existing(tmp_config_dir):
    config_path = tmp_config_dir / "config.yaml"
    config_path.write_text(yaml.dump({"root": "/custom/path", "stale_days": 14}))

    config = load_config(config_path)

    assert config["root"] == "/custom/path"
    assert config["stale_days"] == 14


def test_default_config_has_required_keys():
    assert "root" in DEFAULT_CONFIG
    assert "stale_days" in DEFAULT_CONFIG
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'plaibox.config'`

- [ ] **Step 4: Implement config module**

```python
# src/plaibox/config.py
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/plaibox/config.py tests/conftest.py tests/test_config.py
git commit -m "feat: add config module with default creation"
```

---

### Task 3: Metadata Module

**Files:**
- Create: `src/plaibox/metadata.py`
- Create: `tests/test_metadata.py`

- [ ] **Step 1: Write failing tests for metadata**

```python
# tests/test_metadata.py
from pathlib import Path
from datetime import date
import yaml

from plaibox.metadata import read_metadata, write_metadata

METADATA_FILENAME = ".plaibox.yaml"


def test_write_metadata_creates_file(tmp_path):
    meta = {
        "name": "test-project",
        "description": "A test project",
        "status": "sandbox",
        "created": "2026-04-10",
        "tags": [],
        "tech": [],
    }
    write_metadata(tmp_path, meta)

    written = yaml.safe_load((tmp_path / METADATA_FILENAME).read_text())
    assert written["name"] == "test-project"
    assert written["status"] == "sandbox"


def test_read_metadata_returns_dict(tmp_path):
    meta = {
        "name": "test-project",
        "description": "A test project",
        "status": "sandbox",
        "created": "2026-04-10",
        "tags": [],
        "tech": [],
    }
    (tmp_path / METADATA_FILENAME).write_text(yaml.dump(meta))

    result = read_metadata(tmp_path)
    assert result["name"] == "test-project"
    assert result["description"] == "A test project"


def test_read_metadata_returns_none_when_missing(tmp_path):
    result = read_metadata(tmp_path)
    assert result is None


def test_write_metadata_overwrites_existing(tmp_path):
    meta_v1 = {"name": "old", "description": "Old", "status": "sandbox",
                "created": "2026-04-10", "tags": [], "tech": []}
    meta_v2 = {"name": "new", "description": "New", "status": "project",
                "created": "2026-04-10", "tags": [], "tech": []}

    write_metadata(tmp_path, meta_v1)
    write_metadata(tmp_path, meta_v2)

    result = read_metadata(tmp_path)
    assert result["name"] == "new"
    assert result["status"] == "project"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_metadata.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'plaibox.metadata'`

- [ ] **Step 3: Implement metadata module**

```python
# src/plaibox/metadata.py
from pathlib import Path
import yaml


METADATA_FILENAME = ".plaibox.yaml"


def write_metadata(project_dir: Path, meta: dict) -> None:
    """Write metadata dict to .plaibox.yaml in the given directory."""
    path = project_dir / METADATA_FILENAME
    with open(path, "w") as f:
        yaml.dump(meta, f, default_flow_style=False, sort_keys=False)


def read_metadata(project_dir: Path) -> dict | None:
    """Read .plaibox.yaml from the given directory. Returns None if missing."""
    path = project_dir / METADATA_FILENAME
    if not path.exists():
        return None
    with open(path) as f:
        return yaml.safe_load(f)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_metadata.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/metadata.py tests/test_metadata.py
git commit -m "feat: add metadata read/write for .plaibox.yaml"
```

---

### Task 4: Project Discovery & Utilities

**Files:**
- Create: `src/plaibox/project.py`
- Create: `tests/test_project.py`

- [ ] **Step 1: Write failing tests for slug generation**

```python
# tests/test_project.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'plaibox.project'`

- [ ] **Step 3: Implement slug generation**

```python
# src/plaibox/project.py
import re
from datetime import date
from pathlib import Path

from plaibox.metadata import read_metadata


def slugify(text: str) -> str:
    """Convert text to a URL/filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    return text.strip("-")


def make_sandbox_dirname(description: str, created: date | None = None) -> str:
    """Generate a sandbox directory name: YYYY-MM-DD_slug."""
    if created is None:
        created = date.today()
    slug = slugify(description)
    return f"{created.isoformat()}_{slug}"
```

- [ ] **Step 4: Run slug tests to verify they pass**

Run: `pytest tests/test_project.py::test_slugify_basic tests/test_project.py::test_slugify_special_chars tests/test_project.py::test_slugify_extra_hyphens tests/test_project.py::test_make_sandbox_dirname -v`
Expected: 4 passed

- [ ] **Step 5: Write failing tests for tech detection and project discovery**

Add to `tests/test_project.py`:

```python
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
```

- [ ] **Step 6: Run new tests to verify they fail**

Run: `pytest tests/test_project.py::test_detect_tech_python tests/test_project.py::test_discover_projects -v`
Expected: FAIL — `cannot import name 'detect_tech'`

- [ ] **Step 7: Implement tech detection and discovery**

Add to `src/plaibox/project.py`:

```python
TECH_MARKERS = {
    "requirements.txt": "python",
    "pyproject.toml": "python",
    "setup.py": "python",
    "Pipfile": "python",
    "package.json": "node",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "Gemfile": "ruby",
    "pom.xml": "java",
    "build.gradle": "java",
}


def detect_tech(project_dir: Path) -> list[str]:
    """Detect tech stack by scanning for known manifest files."""
    found = set()
    for filename, tech in TECH_MARKERS.items():
        if (project_dir / filename).exists():
            found.add(tech)
    return sorted(found)


def discover_projects(root: Path) -> list[dict]:
    """Find all plaibox-managed projects across sandbox/projects/archive."""
    results = []
    for space in ("sandbox", "projects", "archive"):
        space_dir = root / space
        if not space_dir.exists():
            continue
        for child in sorted(space_dir.iterdir()):
            if not child.is_dir():
                continue
            meta = read_metadata(child)
            if meta is None:
                continue
            results.append({"path": child, "space": space, "meta": meta})
    return results
```

- [ ] **Step 8: Run all project tests to verify they pass**

Run: `pytest tests/test_project.py -v`
Expected: 8 passed

- [ ] **Step 9: Commit**

```bash
git add src/plaibox/project.py tests/test_project.py
git commit -m "feat: add project utilities — slugify, tech detection, discovery"
```

---

### Task 5: CLI — `plaibox new`

**Files:**
- Create: `src/plaibox/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for `plaibox new`**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — `cannot import name 'cli'`

- [ ] **Step 3: Implement CLI skeleton and `new` command**

```python
# src/plaibox/cli.py
import subprocess
from datetime import date
from pathlib import Path

import click
import yaml

from plaibox.config import load_config, DEFAULT_CONFIG_PATH
from plaibox.metadata import write_metadata
from plaibox.project import slugify, make_sandbox_dirname


@click.group()
def cli():
    """Plaibox — lifecycle manager for vibe-coded projects."""
    pass


@cli.command()
@click.argument("description", required=False)
@click.option("--config", "config_path", default=None, help="Path to config file.")
def new(description: str | None, config_path: str | None):
    """Create a new sandbox project."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    root = Path(cfg["root"]).expanduser()

    if not description:
        description = click.prompt("Project description")

    today = date.today()
    dirname = make_sandbox_dirname(description, today)
    project_dir = root / "sandbox" / dirname
    project_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "name": slugify(description),
        "description": description,
        "status": "sandbox",
        "created": today.isoformat(),
        "tags": [],
        "tech": [],
    }
    write_metadata(project_dir, meta)

    subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)

    click.echo(str(project_dir))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: 2 passed

- [ ] **Step 5: Manual smoke test**

Run: `plaibox new "test from cli"`
Expected: Prints a path like `/Users/nicholas/plaibox/sandbox/2026-04-10_test-from-cli`

- [ ] **Step 6: Commit**

```bash
git add src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: add 'plaibox new' command"
```

---

### Task 6: CLI — `plaibox ls`

**Files:**
- Modify: `src/plaibox/cli.py`
- Modify: `src/plaibox/project.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for `plaibox ls`**

Add to `tests/test_cli.py`:

```python
import os
from datetime import date, timedelta


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
    old_time = (date.today() - timedelta(days=60)).strftime("%Y%m%d0000")
    os.utime(old_dir, (0, (date.today() - timedelta(days=60)).timestamp()))

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_ls_shows_all_projects tests/test_cli.py::test_ls_filters_by_space tests/test_cli.py::test_ls_stale_flag -v`
Expected: FAIL — `No such command 'ls'`

- [ ] **Step 3: Implement `ls` command**

Add to `src/plaibox/cli.py`:

```python
from datetime import date, timedelta

from plaibox.project import discover_projects, detect_tech


@cli.command("ls")
@click.argument("space", required=False, type=click.Choice(["sandbox", "projects", "archive"]))
@click.option("--stale", is_flag=True, help="Show only sandbox projects older than stale_days.")
@click.option("--config", "config_path", default=None, help="Path to config file.")
def ls_cmd(space: str | None, stale: bool, config_path: str | None):
    """List projects."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    root = Path(cfg["root"]).expanduser()
    stale_days = cfg["stale_days"]

    projects = discover_projects(root)

    if space:
        projects = [p for p in projects if p["space"] == space]

    if stale:
        projects = [p for p in projects if p["space"] == "sandbox"]
        cutoff = date.today() - timedelta(days=stale_days)
        projects = [p for p in projects if _last_modified(p["path"]) < cutoff]

    if not projects:
        click.echo("No projects found.")
        return

    for p in projects:
        tech = detect_tech(p["path"])
        tech_str = f" [{', '.join(tech)}]" if tech else ""
        click.echo(f"  {p['meta']['status']:8s}  {p['meta']['name']:30s}  {p['meta']['description']}{tech_str}")


def _last_modified(path: Path) -> date:
    """Get the last modification date of a directory."""
    import os
    mtime = os.path.getmtime(path)
    return date.fromtimestamp(mtime)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: add 'plaibox ls' with space filter and --stale flag"
```

---

### Task 7: CLI — `plaibox promote`

**Files:**
- Modify: `src/plaibox/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for `plaibox promote`**

Add to `tests/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_promote_moves_to_projects tests/test_cli.py::test_promote_rejects_non_sandbox -v`
Expected: FAIL — `No such command 'promote'`

- [ ] **Step 3: Implement `promote` command**

Add to `src/plaibox/cli.py`:

```python
import shutil

from plaibox.metadata import read_metadata, write_metadata


@cli.command()
@click.option("--config", "config_path", default=None, help="Path to config file.")
@click.option("--dir", "project_dir", default=".", help="Project directory to promote.")
def promote(config_path: str | None, project_dir: str):
    """Promote a sandbox project to projects."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    root = Path(cfg["root"]).expanduser()
    project_path = Path(project_dir).resolve()

    meta = read_metadata(project_path)
    if meta is None:
        click.echo("Error: not a plaibox project (no .plaibox.yaml found).", err=True)
        raise SystemExit(1)

    if meta["status"] != "sandbox":
        click.echo("Error: can only promote sandbox projects.", err=True)
        raise SystemExit(1)

    new_name = click.prompt("Project name")
    new_path = root / "projects" / new_name

    if new_path.exists():
        click.echo(f"Error: {new_path} already exists.", err=True)
        raise SystemExit(1)

    shutil.move(str(project_path), str(new_path))

    meta["status"] = "project"
    meta["name"] = new_name
    write_metadata(new_path, meta)

    click.echo(f"Promoted to {new_path}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: add 'plaibox promote' command"
```

---

### Task 8: CLI — `plaibox archive` and `plaibox delete`

**Files:**
- Modify: `src/plaibox/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for archive and delete**

Add to `tests/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_archive_moves_to_archive tests/test_cli.py::test_delete_removes_archived_project tests/test_cli.py::test_delete_rejects_non_archived -v`
Expected: FAIL — `No such command 'archive'`

- [ ] **Step 3: Implement archive command**

Add to `src/plaibox/cli.py`:

```python
@cli.command()
@click.option("--config", "config_path", default=None, help="Path to config file.")
@click.option("--dir", "project_dir", default=".", help="Project directory to archive.")
def archive(config_path: str | None, project_dir: str):
    """Archive a project."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    root = Path(cfg["root"]).expanduser()
    project_path = Path(project_dir).resolve()

    meta = read_metadata(project_path)
    if meta is None:
        click.echo("Error: not a plaibox project (no .plaibox.yaml found).", err=True)
        raise SystemExit(1)

    new_path = root / "archive" / project_path.name

    if new_path.exists():
        click.echo(f"Error: {new_path} already exists in archive.", err=True)
        raise SystemExit(1)

    shutil.move(str(project_path), str(new_path))

    meta["status"] = "archived"
    write_metadata(new_path, meta)

    click.echo(f"Archived to {new_path}")
```

- [ ] **Step 4: Implement delete command**

Add to `src/plaibox/cli.py`:

```python
@cli.command()
@click.option("--config", "config_path", default=None, help="Path to config file.")
@click.option("--dir", "project_dir", default=".", help="Project directory to delete.")
def delete(config_path: str | None, project_dir: str):
    """Permanently delete an archived project."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    project_path = Path(project_dir).resolve()

    meta = read_metadata(project_path)
    if meta is None:
        click.echo("Error: not a plaibox project (no .plaibox.yaml found).", err=True)
        raise SystemExit(1)

    if meta["status"] != "archived":
        click.echo("Error: can only delete archived projects. Archive it first.", err=True)
        raise SystemExit(1)

    if not click.confirm(f"Permanently delete '{meta['name']}'?"):
        click.echo("Cancelled.")
        return

    shutil.rmtree(project_path)
    click.echo(f"Deleted {meta['name']}.")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: 10 passed

- [ ] **Step 6: Commit**

```bash
git add src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: add 'plaibox archive' and 'plaibox delete' commands"
```

---

### Task 9: CLI — `plaibox open`

**Files:**
- Modify: `src/plaibox/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for `plaibox open`**

Add to `tests/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_open_finds_by_name tests/test_cli.py::test_open_finds_by_description tests/test_cli.py::test_open_no_match -v`
Expected: FAIL — `No such command 'open'`

- [ ] **Step 3: Implement `open` command**

Add to `src/plaibox/cli.py`:

```python
@cli.command("open")
@click.argument("query")
@click.option("--config", "config_path", default=None, help="Path to config file.")
def open_cmd(query: str, config_path: str | None):
    """Find a project by name or description and print its path."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    root = Path(cfg["root"]).expanduser()

    projects = discover_projects(root)
    query_lower = query.lower()

    matches = []
    for p in projects:
        name = p["meta"].get("name", "").lower()
        desc = p["meta"].get("description", "").lower()
        if query_lower in name or query_lower in desc:
            matches.append(p)

    if not matches:
        click.echo(f"No project matching '{query}'.")
        raise SystemExit(1)

    if len(matches) == 1:
        click.echo(str(matches[0]["path"]))
        return

    click.echo(f"Multiple matches for '{query}':")
    for i, m in enumerate(matches, 1):
        click.echo(f"  {i}. {m['meta']['name']} — {m['meta']['description']}")

    choice = click.prompt("Which one?", type=int)
    if 1 <= choice <= len(matches):
        click.echo(str(matches[choice - 1]["path"]))
    else:
        click.echo("Invalid choice.")
        raise SystemExit(1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: add 'plaibox open' with fuzzy matching"
```

---

### Task 10: CLI — `plaibox tidy`

**Files:**
- Modify: `src/plaibox/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test for `plaibox tidy`**

Add to `tests/test_cli.py`:

```python
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
    os.utime(old_proj, (0, (date.today() - timedelta(days=60)).timestamp()))

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
    os.utime(old_proj, (0, (date.today() - timedelta(days=60)).timestamp()))

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_tidy_prompts_for_stale_projects tests/test_cli.py::test_tidy_archive_action -v`
Expected: FAIL — `No such command 'tidy'`

- [ ] **Step 3: Implement `tidy` command**

Add to `src/plaibox/cli.py`:

```python
@cli.command()
@click.option("--config", "config_path", default=None, help="Path to config file.")
def tidy(config_path: str | None):
    """Interactively triage stale sandbox projects."""
    cfg = load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    root = Path(cfg["root"]).expanduser()
    stale_days = cfg["stale_days"]

    projects = discover_projects(root)
    cutoff = date.today() - timedelta(days=stale_days)

    stale = [
        p for p in projects
        if p["space"] == "sandbox" and _last_modified(p["path"]) < cutoff
    ]

    if not stale:
        click.echo("No stale sandbox projects. Nice!")
        return

    click.echo(f"Found {len(stale)} stale sandbox project(s):\n")

    for p in stale:
        meta = p["meta"]
        click.echo(f"  {meta['name']} — {meta['description']}")
        click.echo(f"  Created: {meta['created']}  |  Last modified: {_last_modified(p['path'])}")
        action = click.prompt("  [p]romote / [a]rchive / [s]kip", type=click.Choice(["p", "a", "s"]))

        if action == "p":
            new_name = click.prompt("  Project name")
            new_path = root / "projects" / new_name
            if new_path.exists():
                click.echo(f"  Error: {new_path} already exists. Skipping.")
                continue
            shutil.move(str(p["path"]), str(new_path))
            meta["status"] = "project"
            meta["name"] = new_name
            write_metadata(new_path, meta)
            click.echo(f"  Promoted to {new_path}\n")
        elif action == "a":
            new_path = root / "archive" / p["path"].name
            shutil.move(str(p["path"]), str(new_path))
            meta["status"] = "archived"
            write_metadata(new_path, meta)
            click.echo(f"  Archived.\n")
        else:
            click.echo(f"  Skipped.\n")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: 15 passed

- [ ] **Step 5: Commit**

```bash
git add src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: add 'plaibox tidy' for interactive stale project triage"
```

---

### Task 11: Shell Integration — `plaibox init-shell`

**Files:**
- Create: `src/plaibox/shell.py`
- Create: `tests/test_shell.py`
- Modify: `src/plaibox/cli.py`

- [ ] **Step 1: Write failing tests for shell integration**

```python
# tests/test_shell.py
from plaibox.shell import shell_init_script


def test_shell_init_script_contains_function():
    script = shell_init_script()
    assert "plaibox()" in script or "function plaibox" in script


def test_shell_init_script_handles_new():
    script = shell_init_script()
    assert "new" in script


def test_shell_init_script_handles_open():
    script = shell_init_script()
    assert "open" in script
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_shell.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'plaibox.shell'`

- [ ] **Step 3: Implement shell module**

```python
# src/plaibox/shell.py

def shell_init_script() -> str:
    """Return a shell function that wraps the plaibox CLI to enable cd behavior."""
    return '''\
plaibox() {
    if [ "$1" = "new" ] || [ "$1" = "open" ]; then
        local output
        output=$(command plaibox "$@")
        local exit_code=$?
        if [ $exit_code -eq 0 ] && [ -d "$output" ]; then
            cd "$output"
        else
            echo "$output"
        fi
    else
        command plaibox "$@"
    fi
}
'''
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_shell.py -v`
Expected: 3 passed

- [ ] **Step 5: Add `init-shell` CLI command**

Add to `src/plaibox/cli.py`:

```python
from plaibox.shell import shell_init_script


@cli.command("init-shell")
def init_shell():
    """Print shell function for cd integration. Add to your .zshrc/.bashrc:

    eval "$(plaibox init-shell)"
    """
    click.echo(shell_init_script())
```

- [ ] **Step 6: Write a CLI test for init-shell**

Add to `tests/test_cli.py`:

```python
def test_init_shell_outputs_function():
    runner = CliRunner()
    result = runner.invoke(cli, ["init-shell"])
    assert result.exit_code == 0
    assert "plaibox()" in result.output or "function plaibox" in result.output
```

- [ ] **Step 7: Run all tests to verify they pass**

Run: `pytest -v`
Expected: All tests pass (19 total)

- [ ] **Step 8: Commit**

```bash
git add src/plaibox/shell.py tests/test_shell.py src/plaibox/cli.py tests/test_cli.py
git commit -m "feat: add 'plaibox init-shell' for cd integration"
```

---

### Task 12: Final Integration Test & Cleanup

**Files:**
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write an end-to-end integration test**

Add to `tests/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run the full test suite**

Run: `pytest -v`
Expected: All tests pass (20 total)

- [ ] **Step 3: Run plaibox --help and verify all commands are listed**

Run: `plaibox --help`
Expected: Shows commands: `archive`, `delete`, `init-shell`, `ls`, `new`, `open`, `promote`, `tidy`

- [ ] **Step 4: Commit**

```bash
git add tests/test_cli.py
git commit -m "test: add end-to-end lifecycle integration test"
```
