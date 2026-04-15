# Plaibox App

Native macOS app for managing plaibox projects. Built with Tauri 2.x.

## Prerequisites

- [Rust](https://rustup.rs/) (stable)
- Node.js 18+
- `plaibox` CLI installed and configured
- Tauri CLI: `cargo install tauri-cli --version "^2"`

## Development

```bash
cd plaibox-app
npm install
cargo tauri dev
```

Press `Cmd+Option+I` in the app to open devtools.

## Build

```bash
cargo tauri build
```

The built app will be in `src-tauri/target/release/bundle/`.

## Features

### Three-panel layout
- **Sidebar** — project list grouped by space (sandbox/projects/archive), with filter and private project indicators
- **Terminal** — full xterm.js terminal with PTY backend, multiple tabs per project, proper UTF-8 handling
- **Notes** — per-project scratchpad (`.plaibox-notes.md`), auto-saves with debounce, resizable panel

### AI session integration
- **Resume** button appears when a previous Claude/Codex session is detected
- **Claude/Codex** launch buttons when no session exists
- Action buttons auto-prefix commands with `!` when inside an AI session

### Project lifecycle
- **Action bar** with contextual buttons (Promote, Archive, Delete) that type CLI commands into the terminal
- **+ New** button with inline description input
- **Sync** button runs `plaibox sync pull`
- **Filesystem watcher** keeps the sidebar and action bar current when metadata changes on disk

### Notes
- Auto-save with 500ms debounce
- Quick-add input (press Enter to append with timestamp)
- "Make Note" button appears on terminal text selection to capture to notes

### State persistence
- Last-opened project restored on app launch

## Architecture

- **Rust backend** reads plaibox YAML metadata directly for fast display
- **Mutations** (new, promote, archive, etc.) invoke the `plaibox` CLI via the terminal PTY
- **Terminal** uses xterm.js + portable-pty with UTF-8 aware reading
- **Notes** stored as `.plaibox-notes.md` in each project directory
- **Filesystem watcher** (notify crate) monitors sandbox/projects/archive for metadata changes
- **App state** persisted in `~/.plaibox/app-state.yaml`

## Tests

```bash
cd src-tauri && cargo test
```

11 tests covering project metadata parsing, notes read/write/append, and app state persistence.
