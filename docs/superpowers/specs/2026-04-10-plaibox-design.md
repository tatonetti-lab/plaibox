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
```

Design decisions:

- **Minimal required fields:** `name`, `description`, `status`, `created`. Tags and tech are optional.
- **Tech auto-detection:** Detected by scanning for manifest files (`package.json`, `requirements.txt`, `pyproject.toml`, `Cargo.toml`, etc.) on `plaibox ls` or `plaibox promote`, not at creation time (the folder is empty then).
- **Status is source of truth:** Folder location and yaml status stay in sync. The yaml makes metadata portable if projects are moved manually.
- **Human-editable:** YAML format so users can hand-edit if they want.

## CLI Commands

### Creating

- `plaibox new "dashboard for tracking lab results"` — creates a sandbox project with timestamped folder, initializes git, writes `.plaibox.yaml`, and prints the project path (shell function from `plaibox init-shell` handles the `cd`).
- If the description is omitted, plaibox prompts for one.

### Browsing

- `plaibox ls` — lists all projects across all spaces with status, description, and last-modified date.
- `plaibox ls sandbox` — filter to a specific space.
- `plaibox ls --stale` — show sandbox projects untouched for 30+ days.

### Lifecycle

- `plaibox promote` (run from inside a project) — moves from sandbox to projects, prompts for a clean name, updates `.plaibox.yaml`.
- `plaibox archive` (run from inside a project) — moves to archive, updates status.
- `plaibox delete` — permanently removes an archived project. Safety constraint: can only delete from archive, not directly from sandbox or projects.

### Navigation

- `plaibox open <name>` — fuzzy matches against project names and descriptions, prints the path to the match. To enable `cd` behavior, users add a shell function (provided by `plaibox init-shell`) that wraps the CLI and changes directory automatically.

### Triage

- `plaibox tidy` — lists sandbox projects older than a configurable threshold (default 30 days) and interactively asks the user to promote, archive, or skip each one.

## Configuration

Config lives at `~/.plaibox/config.yaml`:

```yaml
root: ~/plaibox              # root directory for all plaibox-managed projects
stale_days: 30               # threshold for --stale flag and tidy command
```

## Implementation

- **Language:** Python
- **CLI framework:** `click` or `typer`
- **Installation:** `pip install -e .` for local development
- **Git:** Automatically initialized on `plaibox new` so every project has version history from birth
- **Fuzzy matching:** Simple substring/prefix matching on name + description for `plaibox open` (no heavy dependencies)
- **No database:** The filesystem and `.plaibox.yaml` files are the data store
- **No web UI:** CLI only for v1
- **No cloud/sync:** Local only for v1

## What This Is Not (v1 Scope Boundaries)

- No Claude Code hooks or integrations
- No web dashboard
- No multi-user support
- No cloud environments
- No retroactive scanning of existing project directories

## Future Extension Points

These are not built in v1 but the design intentionally does not block them:

- **Claude Code integration** — a hook or slash command so `plaibox new` can be triggered from within a Claude Code session.
- **Web dashboard** — a local web UI for browsing and searching projects visually. The `.plaibox.yaml` files make this straightforward since all metadata is already on disk.
- **Cedars platform version** — the same sandbox-to-project-to-archive lifecycle with a web UI, multi-user support, and managed cloud environments instead of local folders.
- **Retroactive scan** — `plaibox scan ~/Projects` to catalog and import existing projects.
- **Semantic search** — embed project descriptions and README content so `plaibox open` can match by meaning, not just string similarity. Useful once you have dozens of projects and can't remember exact names. Could use a local embedding model or API-based embeddings with a lightweight vector index stored alongside the plaibox root.

The key architectural decision enabling all of these: metadata lives in the project directory (`.plaibox.yaml`), not in a central database. Any tool can read/write project state without coupling to the plaibox CLI.
