import hashlib
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


def project_id(project_path: Path) -> str:
    """Generate a short stable ID from the project path."""
    h = hashlib.sha1(str(project_path).encode()).hexdigest()
    return h[:6]


def ensure_spaces(root: Path) -> None:
    """Ensure sandbox/projects/archive directories exist."""
    for space in ("sandbox", "projects", "archive"):
        (root / space).mkdir(parents=True, exist_ok=True)


def discover_projects(root: Path) -> list[dict]:
    """Find all plaibox-managed projects across sandbox/projects/archive."""
    ensure_spaces(root)
    results = []
    for space in ("sandbox", "projects", "archive"):
        space_dir = root / space
        for child in sorted(space_dir.iterdir()):
            if not child.is_dir():
                continue
            meta = read_metadata(child)
            if meta is None:
                continue
            results.append({
                "path": child,
                "space": space,
                "meta": meta,
                "id": project_id(child),
            })
    return results
