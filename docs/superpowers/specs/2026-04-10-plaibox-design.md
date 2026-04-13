# Plaibox Design Spec

## Problem

Vibe coding tools (Claude Code, Codex) make project creation frictionless, but that same frictionlessness creates sprawl: folders accumulate with no descriptions, no status tracking, and no lifecycle management. Over time you can't tell what a project is, what state it's in, or whether it's safe to delete. The problem compounds as creation velocity increases.

This affects both the immediate personal use case and a future platform goal at Cedars-Sinai, where non-coders would use vibe coding tools and face the same sprawl problem at larger scale.

## Solution

Plaibox ("playbox") is a CLI tool that manages the lifecycle of vibe-coded projects. It provides:

1. **Managed creation** — every project is born with a timestamp, description, and metadata
2. **Two-space model** — a sandbox for experiments and a projects space for graduated work
3. **Explicit lifecycle** — projects move through sandbox, project, and archived stages
4. **Discoverability** — browse, search, and triage projects from the command line

## Directory Structure

```
~/plaibox/
  sandbox/                              # ephemeral, vibe-coded experiments
    2026-04-10_dashboard-idea/
    2026-04-08_api-prototype/
  projects/                             # graduated, maintained projects
    patient-tracker/
    lab-dashboard/
  archive/                              # done with, but recoverable
    2026-03-15_old-experiment/
```

- **Sandbox** projects use a `YYYY-MM-DD_slug` naming convention so you can tell what they are and when they were created from the folder name alone.
- **Promoted** projects get a clean name chosen by the user (no date prefix).
- **Archived** projects are moved out of sight but not deleted.

## Metadata: `.plaibox.yaml`

Every project gets a `.plaibox.yaml` file at creation:

```yaml
name: dashboard-for-tracking-lab-results
description: Dashboard for tracking lab results
status: sandbox          # sandbox | project | archived
created: 2026-04-10
tags: []                 # user-defined, optional
tech: []                 # auto-detected (e.g., [python, react])
session: claude --resume abc123  # AI session resume command (auto-captured)
```

Design decisions:

- **Minimal required fields:** `name`, `description`, `status`, `created`. Tags and tech are optional.
- **Tech auto-detection:** Detected by scanning for manifest files (`package.json`, `requirements.txt`, `pyproject.toml`, `Cargo.toml`, etc.) on `plaibox ls` or `plaibox promote`, not at creation time (the folder is empty then).
- **Status is source of truth:** Folder location and yaml status stay in sync. The yaml makes metadata portable if projects are moved manually.
- **Human-editable:** YAML format so users can hand-edit if they want.

## CLI Commands

### Creating

- `plaibox new "dashboard for tracking lab results"` — creates a sandbox project with timestamped folder, initializes git, writes `.plaibox.yaml` and `.gitignore`, and prints the project path (shell function from `plaibox init-shell` handles the `cd`).
- `plaibox new "ml experiment" --python` — same as above, but also creates a `.venv` virtual environment.
- If the description is omitted, plaibox prompts for one.

### Browsing

- `plaibox ls` — lists all projects across all spaces with ID, status, created/modified dates, name, description, and tech stack.
- `plaibox ls sandbox` — filter to a specific space.
- `plaibox ls --stale` — show sandbox projects untouched for 30+ days.

### Lifecycle

- `plaibox promote` (run from inside a project) — moves from sandbox to projects, prompts for a clean name, updates `.plaibox.yaml`. Offers to create a GitHub repo via `gh repo create`.
- `plaibox archive` (run from inside a project) — moves to archive, updates status.
- `plaibox delete` — permanently removes an archived project. Safety constraint: can only delete from archive, not directly from sandbox or projects.

### Navigation

- `plaibox open <name>` — scored fuzzy matching against project names and descriptions (exact > prefix > substring > word-boundary initials > subsequence). Also supports lookup by project ID. Shell function handles `cd` and auto-activates `.venv` if present.
- `plaibox exit` — cd back to previous directory and deactivate any active venv.

### Importing & Scanning

- `plaibox import [path]` — moves an existing project directory into plaibox. Prompts for description and sandbox/project placement. Supports `--project` flag to skip sandbox. Preserves existing `.plaibox.yaml` if present. Auto-detects Python projects and offers to create a `.venv`.
- `plaibox scan <directory>` — walks a directory one level deep and interactively triages each subdirectory: `[i]mport / [s]kip / [n]ever`. Skips hidden directories, existing plaibox projects, and previously ignored paths. Supports `--git-only` to filter to directories with git repos. Ignored paths persist in `~/.plaibox/scan-ignore`.

### Triage

- `plaibox tidy` — lists sandbox projects older than a configurable threshold (default 30 days) and interactively asks the user to promote, archive, or skip each one.

### AI Session Tracking

- `plaibox claude` / `plaibox codex` — wraps the AI tool with `script` to capture terminal output. Automatically extracts and saves the session resume command on exit. Activates `.venv` before launching so the AI tool inherits the correct Python environment.
- `plaibox session` — shows the saved resume command for the current project. `plaibox session --save <cmd>` saves one manually.
- On `plaibox open`, the saved session resume command is displayed automatically, with a hint to use `plaibox claude` for auto-tracking.

### Python Virtual Environments

Managed automatically via shell integration:
- `plaibox new --python` creates a `.venv` in the new project.
- `plaibox open` / `plaibox new` / `plaibox import` auto-activate `.venv` if one exists and deactivate any previously active venv.
- `plaibox exit` deactivates the venv.
- `plaibox claude` / `plaibox codex` activate the venv before launching.

## Configuration

Config lives at `~/.plaibox/config.yaml`:

```yaml
root: ~/plaibox              # root directory for all plaibox-managed projects
stale_days: 30               # threshold for --stale flag and tidy command
```

## Implementation

- **Language:** Python 3.10+
- **CLI framework:** click
- **Installation:** `pipx install -e .` for global use, `pip install -e ".[dev]"` for development
- **Git:** Automatically initialized on `plaibox new`, `plaibox import`, and `plaibox scan` so every project has version history from birth
- **Fuzzy matching:** Scored multi-tier matching (exact > prefix > substring > word-boundary initials > subsequence) plus project ID lookup. No external dependencies.
- **`.gitignore`:** Auto-generated on `plaibox new` and `plaibox import` with common OS, editor, Python, and Node entries. Existing `.gitignore` files are preserved.
- **No database:** The filesystem and `.plaibox.yaml` files are the data store
- **No web UI:** CLI only
- **No cloud/sync:** Local only

## Future Extension Points

These are not yet built but the design intentionally does not block them:

- **Claude Code integration** — a hook or slash command so `plaibox new` can be triggered from within a Claude Code session.
- **Web dashboard** — a local web UI for browsing and searching projects visually. The `.plaibox.yaml` files make this straightforward since all metadata is already on disk.
- **Cedars platform version** — the same sandbox-to-project-to-archive lifecycle with a web UI, multi-user support, and managed cloud environments instead of local folders.
- **Semantic search** — embed project descriptions and README content so `plaibox open` can match by meaning, not just string similarity. Useful once you have dozens of projects and can't remember exact names. Could use a local embedding model or API-based embeddings with a lightweight vector index stored alongside the plaibox root.

The key architectural decision enabling all of these: metadata lives in the project directory (`.plaibox.yaml`), not in a central database. Any tool can read/write project state without coupling to the plaibox CLI.
