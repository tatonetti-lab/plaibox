# Plaibox App Design Spec

## Problem

Managing vibe-coded projects in a terminal works but requires mental overhead — remembering which project you were in, scrolling back to find steps, juggling multiple terminal windows for servers. A native macOS app that wraps the existing plaibox CLI with a visual project list, integrated terminal, and notes panel would reduce that friction.

## Solution

A Tauri-based macOS app with three panels: project sidebar, tabbed terminal, and notes scratchpad. The Rust backend reads plaibox metadata directly for fast display and delegates mutations to the existing CLI. Each project gets its own group of terminal tabs (PTYs) that persist while the app is running.

## Architecture

**Stack:** Tauri 2.x (Rust backend + web frontend). Frontend uses vanilla JS with xterm.js for terminal rendering. No heavy framework — the UI is three panels, a list, and a text area.

**"Rust Reads, CLI Writes" pattern:**
- Rust reads `.plaibox.yaml` files and `~/.plaibox/config.yaml` directly for display (project list, metadata, status).
- Rust watches the filesystem for changes so the sidebar updates when metadata changes externally.
- All mutations (new, promote, archive, delete, sync, unprivate) invoke the `plaibox` CLI as a subprocess — specifically by typing the command into the project's active terminal PTY so the user sees output and can respond to prompts.
- After a mutation command completes, Rust re-reads metadata to update the UI.

**Project structure:**

```
plaibox-app/
  src-tauri/
    src/
      main.rs         # App entry, window setup
      commands.rs      # Tauri IPC command handlers
      projects.rs      # Read YAML metadata, filesystem watcher
      terminal.rs      # PTY lifecycle management
      notes.rs         # Read/write note files
  src/
    index.html
    app.js
    components/
      sidebar.js       # Project list grouped by space
      terminal.js      # xterm.js wrapper + tab management
      notes.js         # Markdown scratchpad editor
      action-bar.js    # Project name, status, lifecycle buttons
```

## Layout

Three-panel layout:

### Left: Project Sidebar (200px, resizable)

- Projects grouped by space: Sandbox, Projects, Archive
- Each project shows its name; private projects show `*` suffix
- Filter input at top for quick search
- `+ New` and `Sync` buttons at bottom
- Clicking a project switches the terminal and notes panels to that project
- Active project highlighted with accent border

### Center: Terminal Area (flexible width)

- **Tab bar** at top of terminal area. Each project starts with one tab. `+` button adds a new terminal tab within the same project (same directory, same venv).
- Tab labels default to the shell name — e.g., `zsh`, `zsh (2)`, `zsh (3)`. Double-click a tab label to rename it (e.g., `server`, `frontend`).
- **Action bar** above the tab bar: project name + status on the left, contextual lifecycle buttons on the right.
  - Sandbox projects: Promote, Archive
  - Projects: Archive
  - Archive: Delete (active), Promote (restore)
  - Delete is only active for archived projects
- **Terminal** fills remaining space. Full PTY rendered via xterm.js — colors, scrollback, interactive programs all work.
- Action buttons type the corresponding `plaibox` command into the active terminal tab, so output and prompts appear naturally.

### Right: Notes Panel (240px, resizable)

- Per-project freeform markdown scratchpad
- Toggle between edit (raw markdown) and rendered view; defaults to rendered
- Auto-saves on 500ms debounce after edits
- Quick-add input at bottom for appending one-liners
- Notes stored as `.plaibox-notes.md` in the project directory

## Terminal Lifecycle

### Opening a project (first time in session)

1. Rust spawns a new PTY with the user's default shell
2. Working directory set to the project path
3. If project has a `.venv`, the shell's plaibox init-shell integration activates it
4. Frontend connects xterm.js to the PTY stream
5. One tab created initially

### Adding terminal tabs

1. User clicks `+` in the tab bar
2. Rust spawns another PTY with the same project directory and venv
3. Frontend creates a new tab, connects xterm.js to the new PTY
4. All tabs within a project share the same working directory at spawn time

### Switching projects

1. User clicks a different project in the sidebar
2. Frontend disconnects xterm.js from current project's PTY streams
3. Frontend connects to the target project's PTY streams (spawning if first time)
4. All PTYs for the previous project continue running in the background
5. Tab state, scroll position, and running processes preserved

### App launch

1. Rust reads `~/.plaibox/app-state.yaml` for last-opened project
2. Spawns PTY for that project immediately
3. Window renders with that project's terminal ready
4. `app-state.yaml` updated on every project switch

### App quit

1. All PTYs are terminated
2. No session persistence across app restarts (PTY state is ephemeral)
3. `app-state.yaml` retains the last-opened project for next launch

## "Make Note" Feature

1. User selects text in the terminal (click and drag)
2. A floating "Make Note" button appears near the selection
3. Clicking it appends the selected text to the project's `.plaibox-notes.md` with a timestamp:

```markdown
---
*Captured Apr 13, 2026 3:42 PM*

1. Run the preprocessing pipeline
2. Validate output against expected schema
3. Generate the summary report
```

4. Notes panel scrolls to show the new content

## Filesystem Watching

Rust uses `notify` crate to watch:
- `~/plaibox/sandbox/`, `~/plaibox/projects/`, `~/plaibox/archive/` for `.plaibox.yaml` changes
- Debounced to avoid rapid-fire updates during git operations
- On change: re-read affected project metadata, push update to frontend via Tauri event
- Sidebar re-renders affected entries

This ensures the sidebar stays current when plaibox commands run in the terminal, in an external terminal, or when sync pulls in changes.

## State Files

### `~/.plaibox/app-state.yaml`

```yaml
last_project: ~/plaibox/sandbox/2026-04-13_patient-analysis
```

Minimal — just enough to restore last session on launch.

### `.plaibox-notes.md` (per project)

Plain markdown file in the project directory. No special schema. Created on first note write.

## What This Does Not Do

- Does not replace the CLI — all business logic stays in the Python CLI.
- Does not add new plaibox features — the app is a GUI for existing functionality.
- Does not persist terminal sessions across app restarts — PTYs are ephemeral.
- Does not sync notes across machines — notes are local files. They would sync if the project's code syncs (sandbox branch or project remote), but that's incidental, not designed.
- Does not provide a built-in web browser/preview — servers started in terminal tabs are viewed in the user's regular browser.
- Does not support platforms other than macOS — Tauri supports cross-platform, but v1 targets macOS only.
