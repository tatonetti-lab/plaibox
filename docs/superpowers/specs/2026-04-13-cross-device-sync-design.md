# Cross-Device Sync Design Spec

## Problem

Plaibox manages projects on a single machine, but developers often work across multiple devices (e.g., work laptop and personal machine). Without cross-device support, you lose visibility into what projects exist on the other machine and have to manually set up each project again.

## Solution

A git-based sync layer that shares project metadata across machines via a private GitHub repo. Sandbox project code is stored as branches in a shared sandbox repo. Promoted projects use their own dedicated repos. The sync layer is opt-in and additive — plaibox works exactly as before without it.

## Architecture

Three pieces work together:

1. **Sync repo** (`plaibox-sync`) — private GitHub repo containing metadata-only YAML files. One file per project, keyed by stable project ID.
2. **Sandbox repo** (`plaibox-sandbox`) — private GitHub repo where each sandbox project is stored as a branch. When branch count exceeds a threshold (default 50), a new sandbox repo is created (`plaibox-sandbox-2`, etc.).
3. **Project repos** — individual GitHub repos for promoted projects (already exists via `plaibox promote`).

```
GitHub:
  plaibox-sync/                  # metadata registry
    projects/
      a1b2c3.yaml
      d4e5f6.yaml
  plaibox-sandbox/               # sandbox code (one branch per project)
    branch: experiment-a1b2c3
    branch: dashboard-d4e5f6
  patient-tracker/               # promoted project (own repo)
```

Locally, nothing changes about directory structure — `~/plaibox/{sandbox,projects,archive}/` stays the same.

## Sync Repo Structure

Each project gets one YAML file in the sync repo, named by project ID:

```yaml
name: patient-tracker
description: Track patient outcomes
status: project
created: '2026-04-10'
tags: []
tech: [python]
remote: https://github.com/tatonetti-lab/patient-tracker
space: projects
sandbox_repo: null
updated: '2026-04-13T14:30:00'
machine: work-macbook
```

For sandbox projects, `remote` is null and `sandbox_repo` points to which sandbox repo holds the branch:

```yaml
name: experiment
description: Quick API experiment
status: sandbox
created: '2026-04-13'
tags: []
tech: [python]
remote: null
sandbox_repo: git@github.com:username/plaibox-sandbox.git
updated: '2026-04-13T15:00:00'
machine: work-macbook
```

## CLI Commands

### Setup

- `plaibox sync init` — creates the sync repo and first sandbox repo on GitHub via `gh`. Prompts to confirm which GitHub account to use (shows output of `gh auth status`). Stores repo URLs in `~/.plaibox/config.yaml` under the `sync` key. Sets `machine_name` from hostname.

### Day-to-day

- `plaibox sync` — manual pull. Fetches the sync repo, updates local registry with changes from other machines. New remote-only projects appear in `plaibox ls` with a `remote` status indicator.
- Auto-push happens silently after any state-changing command (`new`, `promote`, `archive`, `delete`, `import`, `scan` imports). If the push fails (e.g., offline), it silently skips — next successful push catches up.

### Changes to Existing Commands

- **`plaibox new`** — after creating locally, pushes the project to a branch in the sandbox repo (branch name: `<slug>-<id>`), and pushes metadata to the sync repo.
- **`plaibox open`** — if the project only exists on the remote, offers to clone it. For sandbox projects, clones the branch from the sandbox repo. For promoted projects, clones from the project's own repo.
- **`plaibox promote`** — creates the dedicated GitHub repo (as today), pushes code there, deletes the branch from the sandbox repo, updates the sync repo with the new remote URL.
- **`plaibox archive`** / **`plaibox delete`** — updates the sync repo. On delete, also cleans up the sandbox branch if one exists.
- **`plaibox ls`** — shows remote-only projects with a `remote` status indicator so you know they exist but aren't cloned locally.

### Sync Hint

When sync is not configured, `plaibox ls` shows a one-line hint at the bottom:

```
Tip: Use plaibox across devices with 'plaibox sync init'
```

This stops showing once sync is configured or the user dismisses it. Dismissal is tracked via `sync_hint_dismissed: true` in config.

## Config Changes

`~/.plaibox/config.yaml` gains a `sync` key after `plaibox sync init`:

```yaml
root: ~/plaibox
stale_days: 30
sync:
  enabled: true
  repo: git@github.com:username/plaibox-sync.git
  sandbox_repos:
    - git@github.com:username/plaibox-sandbox.git
  sandbox_branch_limit: 50
  machine_name: work-macbook
```

The `sync` key is absent until `plaibox sync init` is run. All existing behavior continues to work without it. The feature is purely opt-in.

## Conflict Resolution

**Metadata conflicts:** Last-write-wins based on the `updated` timestamp. True conflicts are rare since one person typically works on one machine at a time.

**Offline behavior:** Auto-push fails silently. Everything works locally as before. Next successful push catches up.

**Sandbox repo rotation:** When `plaibox new` is about to push to the sandbox repo, it checks the branch count. If over `sandbox_branch_limit` (default 50), it creates a new sandbox repo (`plaibox-sandbox-2`) and uses that for new projects. Each project's registry entry tracks which sandbox repo it belongs to.

**Remote-only projects:** Show in `plaibox ls` with `remote` status. `plaibox open` offers to clone. If no git remote is available (edge case), plaibox reports the project exists on the other machine but can't be cloned.

**Deletion across machines:** `plaibox delete` marks the project as deleted in the sync repo and removes the registry file. On the other machine, `plaibox sync` removes it from the local registry (the "remote" entry disappears from `plaibox ls`). If the project also exists locally on that machine (i.e., it was previously cloned), the local directory is left untouched — plaibox prints a warning ("project X was deleted on <machine>, local copy still exists") and the user can archive or delete it themselves.

## What This Does Not Do

- Does not sync untracked files, local config, or `.venv` directories — only git-tracked code and plaibox metadata.
- Does not support real-time sync or continuous background syncing — push is automatic but pull is manual.
- Does not support multiple users — this is single-user, multi-device.
- Does not replace git workflows — the project's own git remote is still where real collaboration happens.
