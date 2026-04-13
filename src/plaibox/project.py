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


def fuzzy_score(query: str, text: str) -> int:
    """Score how well query matches text. Higher is better, 0 means no match.

    Scoring tiers:
      - Exact match: 100
      - Prefix match: 80
      - Substring match: 60
      - Word-boundary match (all query chars start words): 40
      - Subsequence match (chars appear in order): 20
    """
    q = query.lower()
    t = text.lower()

    if q == t:
        return 100
    if t.startswith(q):
        return 80
    if q in t:
        return 60

    # Word-boundary match: each char in query starts a word in text
    words = re.split(r"[-_ ]+", t)
    word_initials = [w[0] for w in words if w]
    qi = 0
    for initial in word_initials:
        if qi < len(q) and initial == q[qi]:
            qi += 1
    if qi == len(q):
        return 40

    # Subsequence match: chars appear in order anywhere in text
    qi = 0
    for ch in t:
        if qi < len(q) and ch == q[qi]:
            qi += 1
    if qi == len(q):
        return 20

    return 0


def fuzzy_match(query: str, projects: list[dict]) -> list[dict]:
    """Score and rank projects by fuzzy match against name and description."""
    scored = []
    for p in projects:
        name = p["meta"].get("name", "")
        desc = p["meta"].get("description", "")
        name_score = fuzzy_score(query, name)
        desc_score = fuzzy_score(query, desc)
        best = max(name_score, desc_score)
        if best > 0:
            scored.append((best, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored]


GITIGNORE_BASE = """\
# OS
.DS_Store
Thumbs.db

# Editors
.idea/
.vscode/
*.swp
*.swo

# Environments
.env
.venv/
venv/

# Python
__pycache__/
*.pyc
*.egg-info/
dist/
build/

# Node
node_modules/

# Logs
*.log
"""


def write_gitignore(project_dir: Path) -> None:
    """Write a .gitignore if one doesn't exist yet."""
    gitignore = project_dir / ".gitignore"
    if gitignore.exists():
        return
    gitignore.write_text(GITIGNORE_BASE)


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
