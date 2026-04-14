# Plaibox App

Native macOS app for managing plaibox projects. Built with Tauri.

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

## Build

```bash
cargo tauri build
```

The built app will be in `src-tauri/target/release/bundle/`.

## Architecture

- **Rust backend** reads plaibox YAML metadata directly for fast display
- **Mutations** (new, promote, archive, etc.) invoke the `plaibox` CLI in the terminal
- **Terminal** uses xterm.js + PTY for full shell integration
- **Notes** stored as `.plaibox-notes.md` in each project directory
- **Filesystem watcher** keeps the sidebar current when metadata changes
