# Plaibox

CLI tool that manages the lifecycle of vibe-coded projects. Organizes work into sandbox, projects, and archive spaces with lightweight YAML metadata. Auto-tracks AI coding sessions from Claude Code and Codex. Find, promote, triage, and clean up projects without fighting your workflow.

## Install

Requires Python 3.10+.

```bash
# Clone the repo
git clone git@github.com:tatonetti-lab/plaibox.git
cd plaibox

# Install globally with pipx (recommended)
brew install pipx
pipx install -e . --python python3.12

# Or install in a venv for development
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Shell integration

Add this to your `~/.zshrc` or `~/.bashrc` to enable auto-cd and session tracking:

```bash
eval "$(plaibox init-shell)"
```

Then restart your shell or run `source ~/.zshrc`.

## Usage

### Create a new project

```bash
plaibox new "dashboard for lab results"
# Creates ~/plaibox/sandbox/2026-04-10_dashboard-for-lab-results/
# Initializes git, writes metadata, and cd's you in

plaibox new "ml experiment" --python
# Same as above, but also creates a .venv and auto-activates it
```

### List your projects

```bash
plaibox ls                # all projects
plaibox ls sandbox        # just sandbox
plaibox ls --stale        # sandbox projects untouched for 30+ days
```

### Open an existing project

```bash
plaibox open dashboard    # fuzzy match by name or description
plaibox open a1b2c3       # or by ID from plaibox ls
```

### Promote to a real project

```bash
plaibox promote
# Prompts for a clean name, moves to ~/plaibox/projects/
# Optionally creates a GitHub repo via gh cli
```

### Archive and delete

```bash
plaibox archive           # move to archive
plaibox delete            # permanently remove (only works from archive)
```

### Tidy up stale projects

```bash
plaibox tidy
# Walks through stale sandbox projects interactively:
# [p]romote / [a]rchive / [s]kip
```

### Scan existing project directories

```bash
plaibox scan ~/Projects
# Walks through each subdirectory interactively:
# [i]mport / [s]kip / [n]ever
# "never" remembers the choice so future scans skip it

plaibox scan ~/Projects --git-only
# Only show directories that contain a git repo
```

### AI session tracking

Use `plaibox claude` or `plaibox codex` instead of calling the tools directly. Plaibox wraps the session and automatically captures the resume command when you exit.

```bash
plaibox claude            # launches claude, captures session on exit
plaibox codex             # same for codex

# Next time you open the project:
plaibox open my-project
# Resume session: claude --resume abc123
```

### Import an existing project

```bash
plaibox import ~/Projects/old-thing
# Prompts for description, sandbox vs project, moves it in
# Auto-detects Python projects and offers to create a .venv

plaibox import ~/Projects/old-thing --project
# Import directly as a project (skip sandbox)
```

### Return to previous directory

```bash
plaibox exit              # cd back to where you were before open/new
```

### Python virtual environments

Plaibox manages `.venv` automatically when using shell integration:

- `plaibox new --python` creates a `.venv` in the new project
- `plaibox open` / `plaibox new` / `plaibox import` auto-activate `.venv` if one exists
- `plaibox exit` deactivates the venv
- `plaibox claude` / `plaibox codex` activate the venv before launching, so AI tools install packages in the right place

### Cross-device sync

Sync your project registry across machines using a private GitHub repo:

```bash
# Set up sync (creates GitHub repos, one-time)
plaibox sync init

# After making changes, metadata is auto-pushed
plaibox new "my experiment"    # auto-syncs to registry

# On your other machine, pull the latest
plaibox sync pull

# Open a project that only exists on the other machine
plaibox open my-experiment     # offers to clone it
```

Sync is opt-in — plaibox works exactly the same without it. Sandbox project code is stored as branches in a shared repo; promoted projects use their own dedicated GitHub repos.

## Project structure

```
~/plaibox/
  sandbox/                # ephemeral experiments (YYYY-MM-DD_slug/)
  projects/               # graduated, maintained projects
  archive/                # done with, but recoverable
```

Each project contains a `.plaibox.yaml` metadata file:

```yaml
name: my-project
description: Dashboard for tracking lab results
status: sandbox
created: '2026-04-10'
tags: []
tech: [python]
session: claude --resume abc123
```

## Configuration

Config lives at `~/.plaibox/config.yaml`:

```yaml
root: ~/plaibox       # where projects live
stale_days: 30        # threshold for --stale and tidy
```

## Development

```bash
git clone git@github.com:tatonetti-lab/plaibox.git
cd plaibox
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```
