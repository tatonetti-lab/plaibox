# Private Projects Design Spec

## Problem

Some projects handle sensitive data (e.g., patient records) where pushing code to a public service like GitHub introduces a risk of data exposure. Plaibox's cross-device sync pushes code to GitHub in two ways: sandbox branches and promoted project repos. We need a way to opt a project out of all code sync while still participating in metadata sync.

## Solution

A `private: true` flag in project metadata (`.plaibox.yaml`). When set, plaibox never pushes the project's code to any remote. Metadata still syncs so other machines know the project exists. The flag can be set at creation time and later removed (private to public) but not added after creation (since code may have already been pushed).

## Metadata

Local `.plaibox.yaml` gains an optional `private` field:

```yaml
name: patient-analysis
description: Analyze patient outcome records
status: sandbox
created: '2026-04-13'
private: true
tags: []
tech: [python]
```

The sync repo metadata also includes the `private` field:

```yaml
name: patient-analysis
description: Analyze patient outcome records
status: sandbox
private: true
space: sandbox
sandbox_repo: null
remote: null
machine: work-macbook
updated: '2026-04-13T16:00:00'
```

`sandbox_repo` and `remote` are both null for private projects that haven't been explicitly given a remote.

## Code Path Guards

Four places currently interact with code remotes. Each is guarded:

### 1. `plaibox new --private`

Adds `--private` flag to `plaibox new`. When set:
- Writes `private: true` to `.plaibox.yaml`
- Skips `push_sandbox_branch` entirely
- Auto-pushes metadata to the sync repo as normal, with `sandbox_repo: null`

### 2. `auto_push` (metadata only)

No change needed. `auto_push` only pushes metadata to the sync repo, never code. The `sandbox_repo` field in the sync metadata is null for private projects.

### 3. `plaibox promote`

For private projects, instead of offering `gh repo create`:
- Displays: "This project is private. Enter a remote URL (or press Enter to skip):"
- If the user enters a URL, plaibox adds it as the git remote and pushes code there
- If they skip, the project moves to `projects/` locally with no remote
- The sync repo metadata updates with the new status and remote URL (if provided)

### 4. `plaibox open` (remote clone)

When a remote machine tries to open a private project that has no `sandbox_repo` or `remote`:
- Displays: "Project 'patient-analysis' is private on work-macbook. No remote code available."
- Does not offer to clone

If the project has a `remote` URL (set during promote), cloning works normally from that URL.

## Changing Privacy

### Private to public: `plaibox unprivate`

Run from within the project directory:
1. Removes `private: true` from `.plaibox.yaml`
2. If the project is a sandbox and sync is enabled, retroactively pushes code to the sandbox repo (same flow as `plaibox new` would have done)
3. Auto-pushes updated metadata to the sync repo with `sandbox_repo` now populated

After this, the project behaves like any normal project.

### Public to private: not supported

Code may have already been pushed to the sandbox repo or a project remote. There is no automated way to recall pushed code, so this direction is intentionally unsupported. Users who need to make a project private after the fact must manually clean up remotes.

## Display

### `plaibox ls`

Local private projects show their normal status (`sandbox`, `project`, etc.) with a lock icon or `[private]` suffix. Remote private projects with no code available show `private` as their status — indicating they exist on another machine but can't be cloned.

### Sync hint

No changes to the sync hint behavior.

## What This Does Not Do

- Does not encrypt or protect local files — private only means "don't push code to remotes."
- Does not prevent the user from manually pushing code with git commands.
- Does not support making a public project private after code has been pushed.
- Does not add any authentication or access control — this is about preventing accidental exposure, not enforcing security policy.
