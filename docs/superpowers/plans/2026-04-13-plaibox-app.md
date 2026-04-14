# Plaibox App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a native macOS app with Tauri that provides a three-panel interface (project sidebar, tabbed terminal, notes scratchpad) wrapping the existing plaibox CLI.

**Architecture:** Tauri 2.x app with Rust backend reading plaibox YAML metadata directly for display and delegating mutations to the `plaibox` CLI via PTY. Frontend uses vanilla JS with xterm.js for terminal rendering. "Rust Reads, CLI Writes" pattern — fast structured reads, no logic duplication for writes.

**Tech Stack:** Tauri 2.x, Rust (serde_yaml, notify, portable-pty), xterm.js, vanilla JS/CSS

---

## File Structure

```
plaibox-app/                           # New directory alongside existing plaibox
├── src-tauri/
│   ├── Cargo.toml                     # Rust dependencies
│   ├── tauri.conf.json                # Tauri window/app config
│   ├── capabilities/
│   │   └── default.json               # Tauri permission capabilities
│   ├── src/
│   │   ├── main.rs                    # App entry point
│   │   ├── lib.rs                     # Module declarations, Tauri setup
│   │   ├── projects.rs                # Read .plaibox.yaml and config, list projects
│   │   ├── watcher.rs                 # Filesystem watcher for metadata changes
│   │   ├── terminal.rs                # PTY spawn/multiplex/resize/IO
│   │   ├── notes.rs                   # Read/write .plaibox-notes.md files
│   │   └── state.rs                   # App state persistence (last project)
│   └── tests/
│       ├── projects_test.rs           # Unit tests for metadata parsing
│       ├── notes_test.rs              # Unit tests for note read/write
│       └── state_test.rs              # Unit tests for app state
├── src/
│   ├── index.html                     # App shell — three-panel layout
│   ├── styles.css                     # All app styles
│   ├── app.js                         # App initialization, IPC bridge
│   ├── sidebar.js                     # Project list rendering
│   ├── terminal.js                    # xterm.js wrapper + tab management
│   ├── action-bar.js                  # Project name, status, lifecycle buttons
│   └── notes.js                       # Markdown note editor + "Make Note"
├── package.json                       # JS dependencies (xterm.js)
└── README.md                          # Build and run instructions
```

---

### Task 1: Scaffold Tauri App

**Files:**
- Create: `plaibox-app/src-tauri/Cargo.toml`
- Create: `plaibox-app/src-tauri/tauri.conf.json`
- Create: `plaibox-app/src-tauri/capabilities/default.json`
- Create: `plaibox-app/src-tauri/src/main.rs`
- Create: `plaibox-app/src-tauri/src/lib.rs`
- Create: `plaibox-app/src/index.html`
- Create: `plaibox-app/src/styles.css`
- Create: `plaibox-app/src/app.js`
- Create: `plaibox-app/package.json`

- [ ] **Step 1: Install Tauri CLI**

Run:
```bash
cargo install tauri-cli --version "^2"
```

Expected: `tauri-cli` binary available as `cargo tauri`.

- [ ] **Step 2: Create project directory and package.json**

Create `plaibox-app/package.json`:

```json
{
  "name": "plaibox-app",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "tauri": "cargo tauri"
  },
  "dependencies": {
    "@xterm/xterm": "^5.5.0",
    "@xterm/addon-fit": "^0.10.0"
  }
}
```

Run:
```bash
cd plaibox-app && npm install
```

- [ ] **Step 3: Create Cargo.toml**

Create `plaibox-app/src-tauri/Cargo.toml`:

```toml
[package]
name = "plaibox-app"
version = "0.1.0"
edition = "2021"

[dependencies]
tauri = { version = "2", features = [] }
tauri-build = { version = "2", features = [] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
serde_yaml = "0.9"
notify = { version = "7", features = ["macos_fsevent"] }
portable-pty = "0.8"
dirs = "6"
chrono = "0.4"

[build-dependencies]
tauri-build = { version = "2", features = [] }
```

Create `plaibox-app/src-tauri/build.rs`:

```rust
fn main() {
    tauri_build::build()
}
```

- [ ] **Step 4: Create tauri.conf.json**

Create `plaibox-app/src-tauri/tauri.conf.json`:

```json
{
  "$schema": "https://raw.githubusercontent.com/nickel-org/nickel.rs/master/docs/tauri.conf.schema.json",
  "productName": "Plaibox",
  "version": "0.1.0",
  "identifier": "com.plaibox.app",
  "build": {
    "frontendDist": "../src",
    "devUrl": "http://localhost:1420",
    "beforeDevCommand": "",
    "beforeBuildCommand": ""
  },
  "app": {
    "title": "Plaibox",
    "windows": [
      {
        "title": "Plaibox",
        "width": 1200,
        "height": 800,
        "minWidth": 800,
        "minHeight": 500,
        "decorations": true,
        "resizable": true
      }
    ]
  }
}
```

- [ ] **Step 5: Create Tauri capabilities**

Create `plaibox-app/src-tauri/capabilities/default.json`:

```json
{
  "$schema": "https://raw.githubusercontent.com/nickel-org/nickel.rs/master/docs/capability.schema.json",
  "identifier": "default",
  "description": "Default capabilities for plaibox app",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "core:event:default",
    "core:event:allow-emit",
    "core:event:allow-listen"
  ]
}
```

- [ ] **Step 6: Create Rust entry point**

Create `plaibox-app/src-tauri/src/main.rs`:

```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    plaibox_app_lib::run()
}
```

Create `plaibox-app/src-tauri/src/lib.rs`:

```rust
mod projects;
mod notes;
mod state;
mod terminal;
mod watcher;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            projects::list_projects,
            projects::get_config,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

Create stub modules so it compiles:

`plaibox-app/src-tauri/src/projects.rs`:
```rust
use serde::Serialize;

#[derive(Serialize)]
pub struct Project {
    pub id: String,
    pub name: String,
    pub description: String,
    pub status: String,
    pub space: String,
    pub path: String,
    pub private: bool,
}

#[tauri::command]
pub fn list_projects() -> Vec<Project> {
    vec![]
}

#[tauri::command]
pub fn get_config() -> serde_json::Value {
    serde_json::json!({})
}
```

`plaibox-app/src-tauri/src/notes.rs`:
```rust
// Notes module — implemented in Task 9
```

`plaibox-app/src-tauri/src/state.rs`:
```rust
// State module — implemented in Task 11
```

`plaibox-app/src-tauri/src/terminal.rs`:
```rust
// Terminal module — implemented in Task 4
```

`plaibox-app/src-tauri/src/watcher.rs`:
```rust
// Watcher module — implemented in Task 8
```

- [ ] **Step 7: Create frontend shell**

Create `plaibox-app/src/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Plaibox</title>
  <link rel="stylesheet" href="styles.css">
  <link rel="stylesheet" href="node_modules/@xterm/xterm/css/xterm.css">
</head>
<body>
  <div id="app">
    <aside id="sidebar">
      <div id="sidebar-filter">
        <input type="text" id="filter-input" placeholder="Filter projects...">
      </div>
      <div id="project-list"></div>
      <div id="sidebar-actions">
        <button id="btn-new">+ New</button>
        <button id="btn-sync">Sync</button>
      </div>
    </aside>
    <main id="center">
      <div id="action-bar">
        <span id="project-name">No project selected</span>
        <span id="project-status"></span>
        <div id="action-buttons"></div>
      </div>
      <div id="terminal-tabs"></div>
      <div id="terminal-container"></div>
    </main>
    <aside id="notes-panel">
      <div id="notes-header">
        <span>Notes</span>
      </div>
      <div id="notes-content" contenteditable="true"></div>
      <div id="notes-footer">
        <input type="text" id="quick-note" placeholder="Quick note...">
      </div>
    </aside>
  </div>
  <script type="module" src="app.js"></script>
</body>
</html>
```

Create `plaibox-app/src/styles.css`:

```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --bg-dark: #0d0d1a;
  --bg-panel: #1a1a2e;
  --bg-active: #2a2a4a;
  --bg-bar: #1e1e3a;
  --border: #333;
  --text: #ccc;
  --text-bright: #e0e0ff;
  --text-dim: #666;
  --accent: #7c6fff;
  --font-mono: 'SF Mono', 'Menlo', 'Consolas', monospace;
  --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

html, body {
  height: 100%;
  overflow: hidden;
  background: var(--bg-dark);
  color: var(--text);
  font-family: var(--font-sans);
  font-size: 13px;
}

#app {
  display: flex;
  height: 100%;
}

/* Sidebar */
#sidebar {
  width: 200px;
  min-width: 150px;
  background: var(--bg-panel);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
}

#sidebar-filter {
  padding: 10px;
  border-bottom: 1px solid var(--border);
}

#sidebar-filter input {
  width: 100%;
  padding: 6px 8px;
  background: var(--bg-dark);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text);
  font-size: 12px;
  outline: none;
}

#sidebar-filter input:focus {
  border-color: var(--accent);
}

#project-list {
  flex: 1;
  overflow-y: auto;
}

.space-group {
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
}

.space-label {
  padding: 4px 12px;
  font-size: 10px;
  text-transform: uppercase;
  color: var(--text-dim);
  letter-spacing: 0.5px;
}

.project-item {
  padding: 6px 12px;
  color: #aaa;
  cursor: pointer;
  border-left: 3px solid transparent;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
}

.project-item:hover {
  background: rgba(124, 111, 255, 0.1);
}

.project-item.active {
  background: var(--bg-active);
  color: var(--text-bright);
  border-left-color: var(--accent);
}

#sidebar-actions {
  padding: 8px 10px;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 6px;
}

#sidebar-actions button {
  flex: 1;
  padding: 5px;
  background: var(--bg-dark);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text);
  font-size: 11px;
  cursor: pointer;
}

#sidebar-actions button:hover {
  border-color: var(--accent);
}

/* Center */
#center {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

#action-bar {
  padding: 6px 12px;
  background: var(--bg-bar);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 8px;
}

#project-name {
  color: var(--text-bright);
  font-weight: 600;
}

#project-status {
  color: var(--text-dim);
  font-size: 11px;
}

#action-buttons {
  margin-left: auto;
  display: flex;
  gap: 6px;
}

#action-buttons button {
  padding: 3px 10px;
  background: var(--bg-dark);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text);
  font-size: 11px;
  cursor: pointer;
}

#action-buttons button:hover {
  border-color: var(--accent);
}

#action-buttons button:disabled {
  opacity: 0.4;
  cursor: default;
}

/* Terminal tabs */
#terminal-tabs {
  display: flex;
  align-items: center;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border);
  padding: 0 4px;
  min-height: 30px;
}

.term-tab {
  padding: 4px 12px;
  font-size: 11px;
  color: #aaa;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  white-space: nowrap;
}

.term-tab:hover {
  color: var(--text-bright);
}

.term-tab.active {
  color: var(--text-bright);
  border-bottom-color: var(--accent);
}

.term-tab-close {
  margin-left: 6px;
  opacity: 0.4;
  cursor: pointer;
  font-size: 10px;
}

.term-tab-close:hover {
  opacity: 1;
}

#tab-add {
  padding: 4px 8px;
  font-size: 14px;
  color: var(--text-dim);
  cursor: pointer;
  border: none;
  background: none;
}

#tab-add:hover {
  color: var(--text-bright);
}

/* Terminal */
#terminal-container {
  flex: 1;
  position: relative;
  overflow: hidden;
}

#terminal-container .xterm {
  height: 100%;
}

/* Notes panel */
#notes-panel {
  width: 240px;
  min-width: 180px;
  background: var(--bg-panel);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
}

#notes-header {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  font-size: 12px;
  color: #aaa;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

#notes-content {
  flex: 1;
  padding: 12px;
  font-size: 12px;
  color: var(--text);
  line-height: 1.6;
  overflow-y: auto;
  outline: none;
  font-family: var(--font-mono);
  white-space: pre-wrap;
}

#notes-footer {
  padding: 8px 10px;
  border-top: 1px solid var(--border);
}

#notes-footer input {
  width: 100%;
  padding: 6px 8px;
  background: var(--bg-dark);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text);
  font-size: 11px;
  outline: none;
}

#notes-footer input:focus {
  border-color: var(--accent);
}

/* Make Note popup */
#make-note-btn {
  position: absolute;
  display: none;
  padding: 3px 8px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 3px;
  font-size: 11px;
  cursor: pointer;
  z-index: 100;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
}

#make-note-btn:hover {
  background: #6b5ce7;
}
```

Create `plaibox-app/src/app.js`:

```javascript
const { invoke } = window.__TAURI__.core;

async function init() {
  const config = await invoke('get_config');
  const projects = await invoke('list_projects');
  console.log('Config:', config);
  console.log('Projects:', projects);
  document.getElementById('project-name').textContent =
    projects.length > 0 ? 'Select a project' : 'No projects found';
}

window.addEventListener('DOMContentLoaded', init);
```

- [ ] **Step 8: Build and verify the app launches**

Run:
```bash
cd plaibox-app && cargo tauri dev
```

Expected: A window opens titled "Plaibox" showing the three-panel layout with empty sidebar and "No projects found" or "Select a project" text. Close the window.

- [ ] **Step 9: Commit**

```bash
git add plaibox-app/
git commit -m "feat: scaffold Tauri app with three-panel layout"
```

---

### Task 2: Rust Project Metadata Reader

**Files:**
- Create: `plaibox-app/src-tauri/src/projects.rs` (replace stub)
- Create: `plaibox-app/src-tauri/tests/projects_test.rs`
- Modify: `plaibox-app/src-tauri/src/lib.rs`

- [ ] **Step 1: Write tests for config loading**

Create `plaibox-app/src-tauri/tests/projects_test.rs`:

```rust
use std::fs;
use std::path::PathBuf;
use tempfile::TempDir;

// We test the parsing functions directly.
// These are unit tests for the data layer.

#[test]
fn test_parse_config_default() {
    let dir = TempDir::new().unwrap();
    let config_path = dir.path().join("config.yaml");
    fs::write(&config_path, "root: ~/plaibox\nstale_days: 30\n").unwrap();

    let config = plaibox_app_lib::projects::load_config_from_path(&config_path);
    assert_eq!(config.root, shellexpand::tilde("~/plaibox").to_string());
    assert_eq!(config.stale_days, 30);
    assert!(!config.sync_enabled);
}

#[test]
fn test_parse_config_with_sync() {
    let dir = TempDir::new().unwrap();
    let config_path = dir.path().join("config.yaml");
    fs::write(
        &config_path,
        "root: ~/plaibox\nstale_days: 30\nsync:\n  enabled: true\n  repo: git@github.com:user/sync.git\n  machine_name: my-mac\n",
    )
    .unwrap();

    let config = plaibox_app_lib::projects::load_config_from_path(&config_path);
    assert!(config.sync_enabled);
}

#[test]
fn test_parse_project_metadata() {
    let dir = TempDir::new().unwrap();
    let project_dir = dir.path().join("sandbox").join("2026-04-10_my-project");
    fs::create_dir_all(&project_dir).unwrap();
    fs::write(
        project_dir.join(".plaibox.yaml"),
        "id: a1b2c3\nname: my-project\ndescription: A test project\nstatus: sandbox\ncreated: '2026-04-10'\ntags: []\ntech: [python]\n",
    )
    .unwrap();

    let projects = plaibox_app_lib::projects::scan_space(&dir.path().join("sandbox"), "sandbox");
    assert_eq!(projects.len(), 1);
    assert_eq!(projects[0].id, "a1b2c3");
    assert_eq!(projects[0].name, "my-project");
    assert_eq!(projects[0].description, "A test project");
    assert_eq!(projects[0].status, "sandbox");
    assert_eq!(projects[0].space, "sandbox");
    assert!(!projects[0].private);
}

#[test]
fn test_parse_private_project() {
    let dir = TempDir::new().unwrap();
    let project_dir = dir.path().join("sandbox").join("2026-04-13_secret");
    fs::create_dir_all(&project_dir).unwrap();
    fs::write(
        project_dir.join(".plaibox.yaml"),
        "id: x1y2z3\nname: secret\ndescription: Private stuff\nstatus: sandbox\ncreated: '2026-04-13'\nprivate: true\ntags: []\ntech: []\n",
    )
    .unwrap();

    let projects = plaibox_app_lib::projects::scan_space(&dir.path().join("sandbox"), "sandbox");
    assert_eq!(projects.len(), 1);
    assert!(projects[0].private);
}

#[test]
fn test_scan_skips_dirs_without_metadata() {
    let dir = TempDir::new().unwrap();
    let good = dir.path().join("sandbox").join("2026-04-10_good");
    let bad = dir.path().join("sandbox").join("no-metadata");
    fs::create_dir_all(&good).unwrap();
    fs::create_dir_all(&bad).unwrap();
    fs::write(
        good.join(".plaibox.yaml"),
        "id: aaaaaa\nname: good\ndescription: Has metadata\nstatus: sandbox\ncreated: '2026-04-10'\ntags: []\ntech: []\n",
    )
    .unwrap();

    let projects = plaibox_app_lib::projects::scan_space(&dir.path().join("sandbox"), "sandbox");
    assert_eq!(projects.len(), 1);
    assert_eq!(projects[0].name, "good");
}
```

Add `tempfile` and `shellexpand` as dev dependencies in `Cargo.toml`:

```toml
[dev-dependencies]
tempfile = "3"

[dependencies]
# add to existing:
shellexpand = "3"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd plaibox-app/src-tauri && cargo test
```

Expected: Compilation errors — `load_config_from_path`, `scan_space` don't exist yet.

- [ ] **Step 3: Implement projects.rs**

Replace `plaibox-app/src-tauri/src/projects.rs`:

```rust
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

// --- Data types ---

#[derive(Debug, Clone, Serialize)]
pub struct Project {
    pub id: String,
    pub name: String,
    pub description: String,
    pub status: String,
    pub space: String,
    pub path: String,
    pub private: bool,
    pub session: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct AppConfig {
    pub root: String,
    pub stale_days: u32,
    pub sync_enabled: bool,
}

// --- Raw YAML shapes ---

#[derive(Deserialize)]
struct RawConfig {
    root: Option<String>,
    stale_days: Option<u32>,
    sync: Option<RawSyncConfig>,
}

#[derive(Deserialize)]
struct RawSyncConfig {
    enabled: Option<bool>,
}

#[derive(Deserialize)]
struct RawProjectMeta {
    id: Option<String>,
    name: Option<String>,
    description: Option<String>,
    status: Option<String>,
    created: Option<String>,
    private: Option<bool>,
    session: Option<String>,
}

// --- Config loading ---

fn default_config_path() -> PathBuf {
    dirs::home_dir()
        .expect("cannot find home directory")
        .join(".plaibox")
        .join("config.yaml")
}

pub fn load_config_from_path(path: &Path) -> AppConfig {
    let content = fs::read_to_string(path).unwrap_or_default();
    let raw: RawConfig = serde_yaml::from_str(&content).unwrap_or(RawConfig {
        root: None,
        stale_days: None,
        sync: None,
    });

    let root_raw = raw.root.unwrap_or_else(|| "~/plaibox".to_string());
    let root = shellexpand::tilde(&root_raw).to_string();

    AppConfig {
        root,
        stale_days: raw.stale_days.unwrap_or(30),
        sync_enabled: raw.sync.and_then(|s| s.enabled).unwrap_or(false),
    }
}

pub fn load_config() -> AppConfig {
    load_config_from_path(&default_config_path())
}

// --- Project scanning ---

pub fn scan_space(space_dir: &Path, space_name: &str) -> Vec<Project> {
    let mut projects = Vec::new();

    let entries = match fs::read_dir(space_dir) {
        Ok(entries) => entries,
        Err(_) => return projects,
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }

        let meta_path = path.join(".plaibox.yaml");
        let content = match fs::read_to_string(&meta_path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let raw: RawProjectMeta = match serde_yaml::from_str(&content) {
            Ok(m) => m,
            Err(_) => continue,
        };

        let id = match raw.id {
            Some(id) => id,
            None => continue,
        };

        projects.push(Project {
            id,
            name: raw.name.unwrap_or_default(),
            description: raw.description.unwrap_or_default(),
            status: raw.status.unwrap_or_else(|| space_name.to_string()),
            space: space_name.to_string(),
            path: path.to_string_lossy().to_string(),
            private: raw.private.unwrap_or(false),
            session: raw.session,
        });
    }

    projects.sort_by(|a, b| a.name.cmp(&b.name));
    projects
}

pub fn list_all_projects(root: &str) -> Vec<Project> {
    let root_path = PathBuf::from(root);
    let mut all = Vec::new();

    for (dir_name, space_name) in [("sandbox", "sandbox"), ("projects", "projects"), ("archive", "archive")] {
        let space_dir = root_path.join(dir_name);
        all.extend(scan_space(&space_dir, space_name));
    }

    all
}

// --- Tauri commands ---

#[tauri::command]
pub fn list_projects() -> Vec<Project> {
    let config = load_config();
    list_all_projects(&config.root)
}

#[tauri::command]
pub fn get_config() -> AppConfig {
    load_config()
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd plaibox-app/src-tauri && cargo test
```

Expected: All 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add plaibox-app/src-tauri/src/projects.rs plaibox-app/src-tauri/tests/ plaibox-app/src-tauri/Cargo.toml
git commit -m "feat: Rust project metadata reader with tests"
```

---

### Task 3: Frontend Sidebar

**Files:**
- Create: `plaibox-app/src/sidebar.js`
- Modify: `plaibox-app/src/app.js`

- [ ] **Step 1: Implement sidebar.js**

Create `plaibox-app/src/sidebar.js`:

```javascript
const { invoke } = window.__TAURI__.core;

let allProjects = [];
let activeProjectPath = null;
let onProjectSelect = null;

export function setSidebarCallback(callback) {
  onProjectSelect = callback;
}

export async function loadProjects() {
  allProjects = await invoke('list_projects');
  renderSidebar(allProjects);
}

export function getActiveProject() {
  return allProjects.find(p => p.path === activeProjectPath) || null;
}

function renderSidebar(projects) {
  const container = document.getElementById('project-list');
  container.innerHTML = '';

  const groups = { sandbox: [], projects: [], archive: [] };
  for (const p of projects) {
    if (groups[p.space]) {
      groups[p.space].push(p);
    }
  }

  for (const [space, items] of Object.entries(groups)) {
    if (items.length === 0) continue;

    const group = document.createElement('div');
    group.className = 'space-group';

    const label = document.createElement('div');
    label.className = 'space-label';
    label.textContent = space.charAt(0).toUpperCase() + space.slice(1);
    group.appendChild(label);

    for (const project of items) {
      const item = document.createElement('div');
      item.className = 'project-item';
      if (project.path === activeProjectPath) {
        item.classList.add('active');
      }

      let displayName = project.name;
      if (project.private) {
        displayName += ' *';
      }
      item.textContent = displayName;
      item.title = project.description;

      item.addEventListener('click', () => {
        activeProjectPath = project.path;
        renderSidebar(projects);
        if (onProjectSelect) {
          onProjectSelect(project);
        }
      });

      group.appendChild(item);
    }

    container.appendChild(group);
  }
}

export function initFilter() {
  const input = document.getElementById('filter-input');
  input.addEventListener('input', () => {
    const query = input.value.toLowerCase();
    if (!query) {
      renderSidebar(allProjects);
      return;
    }
    const filtered = allProjects.filter(
      p => p.name.toLowerCase().includes(query) ||
           p.description.toLowerCase().includes(query)
    );
    renderSidebar(filtered);
  });
}

export function setActiveByPath(path) {
  activeProjectPath = path;
  renderSidebar(allProjects);
}
```

- [ ] **Step 2: Update app.js to use sidebar**

Replace `plaibox-app/src/app.js`:

```javascript
import { loadProjects, initFilter, setSidebarCallback } from './sidebar.js';

async function init() {
  initFilter();

  setSidebarCallback((project) => {
    document.getElementById('project-name').textContent = project.name;
    const statusSuffix = project.private ? '*' : '';
    document.getElementById('project-status').textContent = project.status + statusSuffix;
    console.log('Selected project:', project.path);
  });

  await loadProjects();
}

window.addEventListener('DOMContentLoaded', init);
```

- [ ] **Step 3: Verify sidebar renders**

Run:
```bash
cd plaibox-app && cargo tauri dev
```

Expected: The sidebar shows your actual plaibox projects grouped by space. Clicking a project highlights it and updates the project name in the action bar. The filter input filters the list. Close the window.

- [ ] **Step 4: Commit**

```bash
git add plaibox-app/src/sidebar.js plaibox-app/src/app.js
git commit -m "feat: sidebar with project list, filter, and selection"
```

---

### Task 4: Rust PTY Management

**Files:**
- Modify: `plaibox-app/src-tauri/src/terminal.rs` (replace stub)
- Modify: `plaibox-app/src-tauri/src/lib.rs`

- [ ] **Step 1: Implement terminal.rs**

Replace `plaibox-app/src-tauri/src/terminal.rs`:

```rust
use portable_pty::{native_pty_system, CommandBuilder, PtySize};
use std::collections::HashMap;
use std::io::{Read, Write};
use std::sync::{Arc, Mutex};
use std::thread;
use tauri::{AppHandle, Emitter};

/// Unique key for a PTY: project path + tab index
#[derive(Debug, Clone, Hash, Eq, PartialEq)]
struct PtyKey {
    project_path: String,
    tab_index: u32,
}

struct PtySession {
    writer: Box<dyn Write + Send>,
    // We keep the master/child alive by holding them
    _master: Box<dyn portable_pty::MasterPty + Send>,
    _child: Box<dyn portable_pty::Child + Send + Sync>,
}

pub struct TerminalManager {
    sessions: HashMap<PtyKey, PtySession>,
    next_tab: HashMap<String, u32>, // project_path -> next tab index
}

impl TerminalManager {
    pub fn new() -> Self {
        Self {
            sessions: HashMap::new(),
            next_tab: HashMap::new(),
        }
    }

    pub fn spawn(
        &mut self,
        project_path: &str,
        app_handle: &AppHandle,
    ) -> u32 {
        let tab_index = *self.next_tab.get(project_path).unwrap_or(&0);
        self.next_tab.insert(project_path.to_string(), tab_index + 1);

        let key = PtyKey {
            project_path: project_path.to_string(),
            tab_index,
        };

        let pty_system = native_pty_system();
        let pair = pty_system
            .openpty(PtySize {
                rows: 24,
                cols: 80,
                pixel_width: 0,
                pixel_height: 0,
            })
            .expect("failed to open pty");

        let shell = std::env::var("SHELL").unwrap_or_else(|_| "/bin/zsh".to_string());
        let mut cmd = CommandBuilder::new(&shell);
        cmd.cwd(project_path);

        let child = pair.slave.spawn_command(cmd).expect("failed to spawn shell");
        // Drop slave after spawning — the master now owns the PTY
        drop(pair.slave);

        let writer = pair.master.take_writer().expect("failed to get writer");
        let mut reader = pair.master.try_clone_reader().expect("failed to get reader");

        // Spawn a thread to read PTY output and emit to frontend
        let event_name = format!("pty-output-{}-{}", project_path, tab_index);
        let handle = app_handle.clone();
        thread::spawn(move || {
            let mut buf = [0u8; 4096];
            loop {
                match reader.read(&mut buf) {
                    Ok(0) => break,
                    Ok(n) => {
                        let data = String::from_utf8_lossy(&buf[..n]).to_string();
                        let _ = handle.emit(&event_name, data);
                    }
                    Err(_) => break,
                }
            }
        });

        self.sessions.insert(
            key,
            PtySession {
                writer,
                _master: pair.master,
                _child: child,
            },
        );

        tab_index
    }

    pub fn write(&mut self, project_path: &str, tab_index: u32, data: &[u8]) {
        let key = PtyKey {
            project_path: project_path.to_string(),
            tab_index,
        };
        if let Some(session) = self.sessions.get_mut(&key) {
            let _ = session.writer.write_all(data);
        }
    }

    pub fn resize(&mut self, project_path: &str, tab_index: u32, rows: u16, cols: u16) {
        let key = PtyKey {
            project_path: project_path.to_string(),
            tab_index,
        };
        if let Some(session) = self.sessions.get(&key) {
            let _ = session._master.resize(PtySize {
                rows,
                cols,
                pixel_width: 0,
                pixel_height: 0,
            });
        }
    }

    pub fn tab_count(&self, project_path: &str) -> u32 {
        *self.next_tab.get(project_path).unwrap_or(&0)
    }
}

// Thread-safe wrapper
pub type SharedTerminalManager = Arc<Mutex<TerminalManager>>;

pub fn new_shared() -> SharedTerminalManager {
    Arc::new(Mutex::new(TerminalManager::new()))
}

// --- Tauri commands ---

#[tauri::command]
pub fn spawn_terminal(
    project_path: String,
    state: tauri::State<'_, SharedTerminalManager>,
    app_handle: AppHandle,
) -> u32 {
    let mut mgr = state.lock().unwrap();
    mgr.spawn(&project_path, &app_handle)
}

#[tauri::command]
pub fn write_terminal(
    project_path: String,
    tab_index: u32,
    data: String,
    state: tauri::State<'_, SharedTerminalManager>,
) {
    let mut mgr = state.lock().unwrap();
    mgr.write(&project_path, tab_index, data.as_bytes());
}

#[tauri::command]
pub fn resize_terminal(
    project_path: String,
    tab_index: u32,
    rows: u16,
    cols: u16,
    state: tauri::State<'_, SharedTerminalManager>,
) {
    let mut mgr = state.lock().unwrap();
    mgr.resize(&project_path, tab_index, rows, cols);
}
```

- [ ] **Step 2: Update lib.rs to register terminal commands and state**

Replace `plaibox-app/src-tauri/src/lib.rs`:

```rust
mod projects;
mod notes;
mod state;
pub mod terminal;
mod watcher;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(terminal::new_shared())
        .invoke_handler(tauri::generate_handler![
            projects::list_projects,
            projects::get_config,
            terminal::spawn_terminal,
            terminal::write_terminal,
            terminal::resize_terminal,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 3: Verify it compiles**

Run:
```bash
cd plaibox-app/src-tauri && cargo build
```

Expected: Compiles without errors.

- [ ] **Step 4: Commit**

```bash
git add plaibox-app/src-tauri/src/terminal.rs plaibox-app/src-tauri/src/lib.rs
git commit -m "feat: Rust PTY manager with spawn, write, resize commands"
```

---

### Task 5: Frontend Terminal with xterm.js

**Files:**
- Create: `plaibox-app/src/terminal.js`
- Modify: `plaibox-app/src/app.js`
- Modify: `plaibox-app/src/index.html`

- [ ] **Step 1: Implement terminal.js**

Create `plaibox-app/src/terminal.js`:

```javascript
const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;
import { Terminal } from '../node_modules/@xterm/xterm/lib/xterm.mjs';
import { FitAddon } from '../node_modules/@xterm/addon-fit/lib/addon-fit.mjs';

// State: project_path -> { tabs: [{terminal, fitAddon, tabIndex, unlisten}], activeTab }
const projectTerminals = new Map();
let currentProjectPath = null;

const container = () => document.getElementById('terminal-container');
const tabBar = () => document.getElementById('terminal-tabs');

function createXterm() {
  const terminal = new Terminal({
    fontSize: 13,
    fontFamily: "'SF Mono', 'Menlo', 'Consolas', monospace",
    theme: {
      background: '#0d0d1a',
      foreground: '#cccccc',
      cursor: '#7c6fff',
      selectionBackground: '#2a2a6a',
    },
    cursorBlink: true,
    scrollback: 10000,
  });
  const fitAddon = new FitAddon();
  terminal.loadAddon(fitAddon);
  return { terminal, fitAddon };
}

async function spawnTab(projectPath) {
  const tabIndex = await invoke('spawn_terminal', { projectPath });

  const { terminal, fitAddon } = createXterm();

  // Listen for PTY output
  const eventName = `pty-output-${projectPath}-${tabIndex}`;
  const unlisten = await listen(eventName, (event) => {
    terminal.write(event.payload);
  });

  // Forward user input to PTY
  terminal.onData((data) => {
    invoke('write_terminal', { projectPath, tabIndex, data });
  });

  // Handle resize
  terminal.onResize(({ rows, cols }) => {
    invoke('resize_terminal', { projectPath, tabIndex, rows, cols });
  });

  const entry = { terminal, fitAddon, tabIndex, unlisten, label: null };

  if (!projectTerminals.has(projectPath)) {
    projectTerminals.set(projectPath, { tabs: [], activeTab: 0 });
  }

  const state = projectTerminals.get(projectPath);
  state.tabs.push(entry);
  state.activeTab = state.tabs.length - 1;

  return entry;
}

function renderTabBar(projectPath) {
  const bar = tabBar();
  bar.innerHTML = '';

  const state = projectTerminals.get(projectPath);
  if (!state) return;

  state.tabs.forEach((entry, i) => {
    const tab = document.createElement('div');
    tab.className = 'term-tab' + (i === state.activeTab ? ' active' : '');

    const label = document.createElement('span');
    label.className = 'term-tab-label';
    label.textContent = entry.label || `zsh${i > 0 ? ` (${i + 1})` : ''}`;
    tab.appendChild(label);

    tab.addEventListener('click', () => {
      state.activeTab = i;
      showTab(projectPath);
    });

    // Double-click to rename tab
    label.addEventListener('dblclick', (e) => {
      e.stopPropagation();
      const input = document.createElement('input');
      input.type = 'text';
      input.value = label.textContent;
      input.style.cssText = 'width:60px;font-size:11px;background:var(--bg-dark);color:var(--text-bright);border:1px solid var(--accent);padding:1px 4px;border-radius:2px;outline:none;';
      label.replaceWith(input);
      input.focus();
      input.select();

      const finish = () => {
        entry.label = input.value.trim() || label.textContent;
        renderTabBar(projectPath);
      };
      input.addEventListener('blur', finish);
      input.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter') finish();
        if (ev.key === 'Escape') renderTabBar(projectPath);
      });
    });

    if (state.tabs.length > 1) {
      const close = document.createElement('span');
      close.className = 'term-tab-close';
      close.textContent = '×';
      close.addEventListener('click', (e) => {
        e.stopPropagation();
        closeTab(projectPath, i);
      });
      tab.appendChild(close);
    }

    bar.appendChild(tab);
  });

  const addBtn = document.createElement('button');
  addBtn.id = 'tab-add';
  addBtn.textContent = '+';
  addBtn.addEventListener('click', async () => {
    await spawnTab(projectPath);
    showTab(projectPath);
  });
  bar.appendChild(addBtn);
}

function showTab(projectPath) {
  const el = container();
  // Detach all terminals
  el.innerHTML = '';

  const state = projectTerminals.get(projectPath);
  if (!state || state.tabs.length === 0) return;

  renderTabBar(projectPath);

  const active = state.tabs[state.activeTab];
  const div = document.createElement('div');
  div.style.height = '100%';
  el.appendChild(div);

  active.terminal.open(div);
  active.fitAddon.fit();

  // Send initial resize to PTY
  const { rows, cols } = active.terminal;
  invoke('resize_terminal', {
    projectPath,
    tabIndex: active.tabIndex,
    rows,
    cols,
  });

  active.terminal.focus();
}

function closeTab(projectPath, index) {
  const state = projectTerminals.get(projectPath);
  if (!state) return;

  const entry = state.tabs[index];
  entry.unlisten();
  entry.terminal.dispose();
  state.tabs.splice(index, 1);

  if (state.tabs.length === 0) {
    projectTerminals.delete(projectPath);
    container().innerHTML = '';
    tabBar().innerHTML = '';
    return;
  }

  if (state.activeTab >= state.tabs.length) {
    state.activeTab = state.tabs.length - 1;
  }

  showTab(projectPath);
}

export async function openProject(projectPath) {
  currentProjectPath = projectPath;

  // If project has no tabs yet, spawn the first one
  if (!projectTerminals.has(projectPath)) {
    await spawnTab(projectPath);
  }

  showTab(projectPath);
}

export function getCurrentProjectPath() {
  return currentProjectPath;
}

// Re-fit terminal on window resize
window.addEventListener('resize', () => {
  if (!currentProjectPath) return;
  const state = projectTerminals.get(currentProjectPath);
  if (!state) return;
  const active = state.tabs[state.activeTab];
  if (active) {
    active.fitAddon.fit();
  }
});
```

- [ ] **Step 2: Update app.js to connect sidebar to terminal**

Replace `plaibox-app/src/app.js`:

```javascript
import { loadProjects, initFilter, setSidebarCallback } from './sidebar.js';
import { openProject } from './terminal.js';

async function init() {
  initFilter();

  setSidebarCallback(async (project) => {
    document.getElementById('project-name').textContent = project.name;
    const statusSuffix = project.private ? '*' : '';
    document.getElementById('project-status').textContent = project.status + statusSuffix;
    await openProject(project.path);
  });

  await loadProjects();
}

window.addEventListener('DOMContentLoaded', init);
```

- [ ] **Step 3: Fix xterm.js CSS import path**

The xterm CSS needs to be accessible. Update `plaibox-app/src/index.html` — change the xterm CSS link:

```html
<link rel="stylesheet" href="./node_modules/@xterm/xterm/css/xterm.css">
```

Note: Tauri serves from the `src/` directory. The `node_modules/` folder is at `plaibox-app/node_modules/`, so the path must be relative from `src/` up one level: `../node_modules/...`. Update the link to:

```html
<link rel="stylesheet" href="../node_modules/@xterm/xterm/css/xterm.css">
```

- [ ] **Step 4: Verify terminal works**

Run:
```bash
cd plaibox-app && cargo tauri dev
```

Expected: Click a project in the sidebar. A terminal opens showing your shell prompt in that project's directory. You can type commands, see output with colors. The `+` button adds a new tab. Tabs switch correctly. Close the window.

- [ ] **Step 5: Commit**

```bash
git add plaibox-app/src/terminal.js plaibox-app/src/app.js plaibox-app/src/index.html
git commit -m "feat: terminal with xterm.js, PTY integration, and tab support"
```

---

### Task 6: Action Bar with Lifecycle Buttons

**Files:**
- Create: `plaibox-app/src/action-bar.js`
- Modify: `plaibox-app/src/app.js`
- Modify: `plaibox-app/src/terminal.js`

- [ ] **Step 1: Implement action-bar.js**

Create `plaibox-app/src/action-bar.js`:

```javascript
import { getCurrentProjectPath } from './terminal.js';

const { invoke } = window.__TAURI__.core;

let currentProject = null;
let writeToTerminal = null;

export function setTerminalWriter(fn) {
  writeToTerminal = fn;
}

export function updateActionBar(project) {
  currentProject = project;

  document.getElementById('project-name').textContent = project.name;
  const statusSuffix = project.private ? '*' : '';
  document.getElementById('project-status').textContent = project.status + statusSuffix;

  const buttons = document.getElementById('action-buttons');
  buttons.innerHTML = '';

  const actions = getActionsForStatus(project.status, project.space);
  for (const action of actions) {
    const btn = document.createElement('button');
    btn.textContent = action.label;
    btn.disabled = action.disabled || false;

    if (!action.disabled) {
      btn.addEventListener('click', () => {
        runAction(action.command);
      });
    }

    buttons.appendChild(btn);
  }
}

function getActionsForStatus(status, space) {
  switch (space) {
    case 'sandbox':
      return [
        { label: 'Promote', command: 'plaibox promote' },
        { label: 'Archive', command: 'plaibox archive' },
        { label: 'Delete', command: '', disabled: true },
      ];
    case 'projects':
      return [
        { label: 'Archive', command: 'plaibox archive' },
        { label: 'Delete', command: '', disabled: true },
      ];
    case 'archive':
      return [
        { label: 'Delete', command: 'plaibox delete' },
      ];
    default:
      return [];
  }
}

function runAction(command) {
  if (!command || !writeToTerminal) return;
  // Type the command into the active terminal followed by Enter
  writeToTerminal(command + '\n');
}

export function clearActionBar() {
  document.getElementById('project-name').textContent = 'No project selected';
  document.getElementById('project-status').textContent = '';
  document.getElementById('action-buttons').innerHTML = '';
  currentProject = null;
}
```

- [ ] **Step 2: Export a write helper from terminal.js**

Add this export at the bottom of `plaibox-app/src/terminal.js`:

```javascript
export function writeToActiveTerminal(data) {
  if (!currentProjectPath) return;
  const state = projectTerminals.get(currentProjectPath);
  if (!state) return;
  const active = state.tabs[state.activeTab];
  if (active) {
    invoke('write_terminal', {
      projectPath: currentProjectPath,
      tabIndex: active.tabIndex,
      data,
    });
  }
}
```

- [ ] **Step 3: Wire action bar into app.js**

Replace `plaibox-app/src/app.js`:

```javascript
import { loadProjects, initFilter, setSidebarCallback } from './sidebar.js';
import { openProject, writeToActiveTerminal } from './terminal.js';
import { updateActionBar, setTerminalWriter } from './action-bar.js';

async function init() {
  initFilter();
  setTerminalWriter(writeToActiveTerminal);

  setSidebarCallback(async (project) => {
    updateActionBar(project);
    await openProject(project.path);
  });

  await loadProjects();
}

window.addEventListener('DOMContentLoaded', init);
```

- [ ] **Step 4: Verify action bar works**

Run:
```bash
cd plaibox-app && cargo tauri dev
```

Expected: Click a sandbox project — see Promote, Archive, Delete (dimmed) buttons. Click an archived project — see Delete button. Click Promote on a sandbox project — the `plaibox promote` command is typed into the terminal and executes. Close the window.

- [ ] **Step 5: Commit**

```bash
git add plaibox-app/src/action-bar.js plaibox-app/src/terminal.js plaibox-app/src/app.js
git commit -m "feat: action bar with contextual lifecycle buttons"
```

---

### Task 7: Filesystem Watcher for Live Sidebar Updates

**Files:**
- Modify: `plaibox-app/src-tauri/src/watcher.rs` (replace stub)
- Modify: `plaibox-app/src-tauri/src/lib.rs`
- Modify: `plaibox-app/src/sidebar.js`
- Modify: `plaibox-app/src/app.js`

- [ ] **Step 1: Implement watcher.rs**

Replace `plaibox-app/src-tauri/src/watcher.rs`:

```rust
use notify::{Config, RecommendedWatcher, RecursiveMode, Watcher, EventKind};
use std::path::PathBuf;
use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter};

use crate::projects;

/// Start watching plaibox directories for .plaibox.yaml changes.
/// Emits "projects-changed" event to the frontend when metadata changes.
pub fn start_watcher(app_handle: AppHandle, root: String) {
    thread::spawn(move || {
        let (tx, rx) = mpsc::channel();

        let mut watcher = RecommendedWatcher::new(tx, Config::default())
            .expect("failed to create watcher");

        let root_path = PathBuf::from(&root);
        for dir_name in ["sandbox", "projects", "archive"] {
            let dir = root_path.join(dir_name);
            if dir.exists() {
                let _ = watcher.watch(&dir, RecursiveMode::Recursive);
            }
        }

        let debounce = Duration::from_millis(500);
        let mut last_emit = Instant::now() - debounce;

        loop {
            match rx.recv() {
                Ok(Ok(event)) => {
                    // Only react to changes involving .plaibox.yaml files
                    let dominated_path = event.paths.iter().any(|p| {
                        p.file_name()
                            .map(|n| n == ".plaibox.yaml")
                            .unwrap_or(false)
                    });

                    // Also react to directory create/delete (project added/removed)
                    let is_dir_change = matches!(
                        event.kind,
                        EventKind::Create(_) | EventKind::Remove(_)
                    );

                    if dominated_path || is_dir_change {
                        let now = Instant::now();
                        if now.duration_since(last_emit) >= debounce {
                            last_emit = now;
                            let all = projects::list_all_projects(&root);
                            let _ = app_handle.emit("projects-changed", &all);
                        }
                    }
                }
                Ok(Err(_)) => {}
                Err(_) => break, // Channel closed
            }
        }
    });
}
```

- [ ] **Step 2: Start watcher on app launch in lib.rs**

Replace `plaibox-app/src-tauri/src/lib.rs`:

```rust
pub mod projects;
mod notes;
mod state;
pub mod terminal;
mod watcher;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(terminal::new_shared())
        .setup(|app| {
            let config = projects::load_config();
            watcher::start_watcher(app.handle().clone(), config.root);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            projects::list_projects,
            projects::get_config,
            terminal::spawn_terminal,
            terminal::write_terminal,
            terminal::resize_terminal,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 3: Listen for changes in sidebar.js**

Add to the top of `plaibox-app/src/sidebar.js`:

```javascript
const { listen } = window.__TAURI__.event;
```

Add this export function:

```javascript
export async function startWatching() {
  await listen('projects-changed', (event) => {
    allProjects = event.payload;
    const filterValue = document.getElementById('filter-input').value.toLowerCase();
    if (filterValue) {
      const filtered = allProjects.filter(
        p => p.name.toLowerCase().includes(filterValue) ||
             p.description.toLowerCase().includes(filterValue)
      );
      renderSidebar(filtered);
    } else {
      renderSidebar(allProjects);
    }
  });
}
```

- [ ] **Step 4: Call startWatching in app.js**

Update `plaibox-app/src/app.js` — add `startWatching` to the import and call it in `init()`:

```javascript
import { loadProjects, initFilter, setSidebarCallback, startWatching } from './sidebar.js';
import { openProject, writeToActiveTerminal } from './terminal.js';
import { updateActionBar, setTerminalWriter } from './action-bar.js';

async function init() {
  initFilter();
  setTerminalWriter(writeToActiveTerminal);

  setSidebarCallback(async (project) => {
    updateActionBar(project);
    await openProject(project.path);
  });

  await loadProjects();
  await startWatching();
}

window.addEventListener('DOMContentLoaded', init);
```

- [ ] **Step 5: Verify watcher works**

Run:
```bash
cd plaibox-app && cargo tauri dev
```

In a separate terminal, create a new plaibox project:
```bash
plaibox new "watcher test"
```

Expected: The new project appears in the app sidebar within ~1 second without restarting the app. Archive or delete it — the sidebar updates.

- [ ] **Step 6: Commit**

```bash
git add plaibox-app/src-tauri/src/watcher.rs plaibox-app/src-tauri/src/lib.rs plaibox-app/src/sidebar.js plaibox-app/src/app.js
git commit -m "feat: filesystem watcher for live sidebar updates"
```

---

### Task 8: Notes Panel

**Files:**
- Modify: `plaibox-app/src-tauri/src/notes.rs` (replace stub)
- Modify: `plaibox-app/src-tauri/src/lib.rs`
- Create: `plaibox-app/src-tauri/tests/notes_test.rs`
- Create: `plaibox-app/src/notes.js`
- Modify: `plaibox-app/src/app.js`

- [ ] **Step 1: Write tests for notes read/write**

Create `plaibox-app/src-tauri/tests/notes_test.rs`:

```rust
use std::fs;
use tempfile::TempDir;

#[test]
fn test_read_notes_missing_file() {
    let dir = TempDir::new().unwrap();
    let content = plaibox_app_lib::notes::read_notes(dir.path().to_str().unwrap());
    assert_eq!(content, "");
}

#[test]
fn test_write_and_read_notes() {
    let dir = TempDir::new().unwrap();
    let path = dir.path().to_str().unwrap();

    plaibox_app_lib::notes::write_notes(path, "# My Notes\nSome content".to_string());

    let content = plaibox_app_lib::notes::read_notes(path);
    assert_eq!(content, "# My Notes\nSome content");
}

#[test]
fn test_append_note() {
    let dir = TempDir::new().unwrap();
    let path = dir.path().to_str().unwrap();

    plaibox_app_lib::notes::write_notes(path, "Existing note".to_string());
    plaibox_app_lib::notes::append_note(path, "Captured text here".to_string());

    let content = plaibox_app_lib::notes::read_notes(path);
    assert!(content.starts_with("Existing note"));
    assert!(content.contains("Captured text here"));
    assert!(content.contains("---"));
}

#[test]
fn test_append_note_to_empty() {
    let dir = TempDir::new().unwrap();
    let path = dir.path().to_str().unwrap();

    plaibox_app_lib::notes::append_note(path, "First capture".to_string());

    let content = plaibox_app_lib::notes::read_notes(path);
    assert!(content.contains("First capture"));
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd plaibox-app/src-tauri && cargo test
```

Expected: Compilation errors — functions in `notes` module don't exist yet.

- [ ] **Step 3: Implement notes.rs**

Replace `plaibox-app/src-tauri/src/notes.rs`:

```rust
use chrono::Local;
use std::fs;
use std::path::PathBuf;

const NOTES_FILENAME: &str = ".plaibox-notes.md";

fn notes_path(project_path: &str) -> PathBuf {
    PathBuf::from(project_path).join(NOTES_FILENAME)
}

pub fn read_notes(project_path: &str) -> String {
    let path = notes_path(project_path);
    fs::read_to_string(path).unwrap_or_default()
}

pub fn write_notes(project_path: &str, content: String) {
    let path = notes_path(project_path);
    let _ = fs::write(path, content);
}

pub fn append_note(project_path: &str, text: String) {
    let existing = read_notes(project_path);
    let timestamp = Local::now().format("%b %d, %Y %-I:%M %p").to_string();

    let separator = format!("\n\n---\n*Captured {}*\n\n", timestamp);
    let new_content = if existing.is_empty() {
        format!("*Captured {}*\n\n{}", timestamp, text)
    } else {
        format!("{}{}{}", existing, separator, text)
    };

    write_notes(project_path, new_content);
}

// --- Tauri commands ---

#[tauri::command]
pub fn get_notes(project_path: String) -> String {
    read_notes(&project_path)
}

#[tauri::command]
pub fn save_notes(project_path: String, content: String) {
    write_notes(&project_path, content);
}

#[tauri::command]
pub fn capture_note(project_path: String, text: String) -> String {
    append_note(&project_path, text);
    read_notes(&project_path)
}
```

Make `notes` module public in `lib.rs` — change `mod notes;` to `pub mod notes;`.

- [ ] **Step 4: Register notes commands in lib.rs**

Update the `invoke_handler` in `plaibox-app/src-tauri/src/lib.rs`:

```rust
        .invoke_handler(tauri::generate_handler![
            projects::list_projects,
            projects::get_config,
            terminal::spawn_terminal,
            terminal::write_terminal,
            terminal::resize_terminal,
            notes::get_notes,
            notes::save_notes,
            notes::capture_note,
        ])
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
cd plaibox-app/src-tauri && cargo test
```

Expected: All notes tests pass (plus existing projects tests).

- [ ] **Step 6: Implement notes.js frontend**

Create `plaibox-app/src/notes.js`:

```javascript
const { invoke } = window.__TAURI__.core;

let currentProjectPath = null;
let saveTimeout = null;

const contentEl = () => document.getElementById('notes-content');
const quickInput = () => document.getElementById('quick-note');

export function initNotes() {
  // Auto-save on edit with 500ms debounce
  contentEl().addEventListener('input', () => {
    if (!currentProjectPath) return;
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => {
      const content = contentEl().innerText;
      invoke('save_notes', { projectPath: currentProjectPath, content });
    }, 500);
  });

  // Quick-add on Enter
  quickInput().addEventListener('keydown', async (e) => {
    if (e.key !== 'Enter' || !currentProjectPath) return;
    const text = quickInput().value.trim();
    if (!text) return;

    const updated = await invoke('capture_note', {
      projectPath: currentProjectPath,
      text,
    });
    contentEl().innerText = updated;
    quickInput().value = '';

    // Scroll to bottom
    contentEl().scrollTop = contentEl().scrollHeight;
  });
}

export async function loadNotes(projectPath) {
  currentProjectPath = projectPath;
  const content = await invoke('get_notes', { projectPath });
  contentEl().innerText = content;
}

export async function captureToNotes(text) {
  if (!currentProjectPath) return;
  const updated = await invoke('capture_note', {
    projectPath: currentProjectPath,
    text,
  });
  contentEl().innerText = updated;
  contentEl().scrollTop = contentEl().scrollHeight;
}

export function clearNotes() {
  currentProjectPath = null;
  contentEl().innerText = '';
}
```

- [ ] **Step 7: Wire notes into app.js**

Replace `plaibox-app/src/app.js`:

```javascript
import { loadProjects, initFilter, setSidebarCallback, startWatching } from './sidebar.js';
import { openProject, writeToActiveTerminal } from './terminal.js';
import { updateActionBar, setTerminalWriter } from './action-bar.js';
import { initNotes, loadNotes } from './notes.js';

async function init() {
  initFilter();
  initNotes();
  setTerminalWriter(writeToActiveTerminal);

  setSidebarCallback(async (project) => {
    updateActionBar(project);
    await openProject(project.path);
    await loadNotes(project.path);
  });

  await loadProjects();
  await startWatching();
}

window.addEventListener('DOMContentLoaded', init);
```

- [ ] **Step 8: Verify notes work**

Run:
```bash
cd plaibox-app && cargo tauri dev
```

Expected: Click a project. The notes panel is empty. Type in it — text appears. Switch to another project and back — your notes persisted. Type a quick note in the bottom input and press Enter — it's appended with a timestamp. Check the project directory for `.plaibox-notes.md`.

- [ ] **Step 9: Commit**

```bash
git add plaibox-app/src-tauri/src/notes.rs plaibox-app/src-tauri/src/lib.rs plaibox-app/src-tauri/tests/notes_test.rs plaibox-app/src/notes.js plaibox-app/src/app.js
git commit -m "feat: notes panel with auto-save, quick-add, and capture"
```

---

### Task 9: "Make Note" from Terminal Selection

**Files:**
- Modify: `plaibox-app/src/terminal.js`
- Modify: `plaibox-app/src/index.html`

- [ ] **Step 1: Add the "Make Note" button to index.html**

Add this just before the closing `</div>` of `#app` in `plaibox-app/src/index.html`:

```html
    <button id="make-note-btn">Make Note</button>
```

- [ ] **Step 2: Add selection handling to terminal.js**

Add the following to `plaibox-app/src/terminal.js`. Import `captureToNotes` at the top:

```javascript
import { captureToNotes } from './notes.js';
```

Add a `setupMakeNote` function and call it when showing a tab. After the `showTab` function, add:

```javascript
function setupMakeNote(terminal) {
  const btn = document.getElementById('make-note-btn');

  terminal.onSelectionChange(() => {
    const selection = terminal.getSelection();
    if (selection && selection.trim().length > 0) {
      // Position the button near the terminal container
      const rect = container().getBoundingClientRect();
      btn.style.display = 'block';
      btn.style.top = (rect.top + 8) + 'px';
      btn.style.right = (window.innerWidth - rect.right + 8) + 'px';

      btn.onclick = () => {
        captureToNotes(selection.trim());
        terminal.clearSelection();
        btn.style.display = 'none';
      };
    } else {
      btn.style.display = 'none';
    }
  });
}
```

In the `showTab` function, after `active.terminal.focus();`, add:

```javascript
  setupMakeNote(active.terminal);
```

- [ ] **Step 3: Verify "Make Note" works**

Run:
```bash
cd plaibox-app && cargo tauri dev
```

Expected: In the terminal, select some text by clicking and dragging. A "Make Note" button appears. Click it — the selected text appears in the notes panel with a timestamp. The selection clears and the button disappears.

- [ ] **Step 4: Commit**

```bash
git add plaibox-app/src/terminal.js plaibox-app/src/index.html
git commit -m "feat: Make Note button captures terminal selection to notes"
```

---

### Task 10: App State Persistence

**Files:**
- Modify: `plaibox-app/src-tauri/src/state.rs` (replace stub)
- Create: `plaibox-app/src-tauri/tests/state_test.rs`
- Modify: `plaibox-app/src-tauri/src/lib.rs`
- Modify: `plaibox-app/src/app.js`
- Modify: `plaibox-app/src/sidebar.js`

- [ ] **Step 1: Write tests for state persistence**

Create `plaibox-app/src-tauri/tests/state_test.rs`:

```rust
use std::fs;
use tempfile::TempDir;

#[test]
fn test_read_state_missing_file() {
    let dir = TempDir::new().unwrap();
    let state = plaibox_app_lib::state::read_app_state(dir.path());
    assert!(state.last_project.is_none());
}

#[test]
fn test_write_and_read_state() {
    let dir = TempDir::new().unwrap();

    plaibox_app_lib::state::save_app_state(
        dir.path(),
        &plaibox_app_lib::state::AppState {
            last_project: Some("/Users/nick/plaibox/sandbox/2026-04-10_test".to_string()),
        },
    );

    let state = plaibox_app_lib::state::read_app_state(dir.path());
    assert_eq!(
        state.last_project.unwrap(),
        "/Users/nick/plaibox/sandbox/2026-04-10_test"
    );
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd plaibox-app/src-tauri && cargo test
```

Expected: Compilation errors — `state` module functions don't exist yet.

- [ ] **Step 3: Implement state.rs**

Replace `plaibox-app/src-tauri/src/state.rs`:

```rust
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

const STATE_FILENAME: &str = "app-state.yaml";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppState {
    pub last_project: Option<String>,
}

impl Default for AppState {
    fn default() -> Self {
        Self { last_project: None }
    }
}

fn state_path(config_dir: &Path) -> std::path::PathBuf {
    config_dir.join(STATE_FILENAME)
}

pub fn read_app_state(config_dir: &Path) -> AppState {
    let path = state_path(config_dir);
    let content = match fs::read_to_string(path) {
        Ok(c) => c,
        Err(_) => return AppState::default(),
    };
    serde_yaml::from_str(&content).unwrap_or_default()
}

pub fn save_app_state(config_dir: &Path, state: &AppState) {
    let path = state_path(config_dir);
    if let Ok(content) = serde_yaml::to_string(state) {
        let _ = fs::write(path, content);
    }
}

fn plaibox_config_dir() -> std::path::PathBuf {
    dirs::home_dir()
        .expect("cannot find home directory")
        .join(".plaibox")
}

// --- Tauri commands ---

#[tauri::command]
pub fn get_last_project() -> Option<String> {
    let state = read_app_state(&plaibox_config_dir());
    state.last_project
}

#[tauri::command]
pub fn set_last_project(project_path: String) {
    let state = AppState {
        last_project: Some(project_path),
    };
    save_app_state(&plaibox_config_dir(), &state);
}
```

Make `state` module public in `lib.rs` — change `mod state;` to `pub mod state;`.

- [ ] **Step 4: Register state commands in lib.rs**

Update the `invoke_handler` in `plaibox-app/src-tauri/src/lib.rs`:

```rust
        .invoke_handler(tauri::generate_handler![
            projects::list_projects,
            projects::get_config,
            terminal::spawn_terminal,
            terminal::write_terminal,
            terminal::resize_terminal,
            notes::get_notes,
            notes::save_notes,
            notes::capture_note,
            state::get_last_project,
            state::set_last_project,
        ])
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
cd plaibox-app/src-tauri && cargo test
```

Expected: All state tests pass (plus existing tests).

- [ ] **Step 6: Update app.js to restore last project on launch**

Replace `plaibox-app/src/app.js`:

```javascript
import { loadProjects, initFilter, setSidebarCallback, startWatching, setActiveByPath } from './sidebar.js';
import { openProject, writeToActiveTerminal } from './terminal.js';
import { updateActionBar, setTerminalWriter } from './action-bar.js';
import { initNotes, loadNotes } from './notes.js';

const { invoke } = window.__TAURI__.core;

async function init() {
  initFilter();
  initNotes();
  setTerminalWriter(writeToActiveTerminal);

  setSidebarCallback(async (project) => {
    updateActionBar(project);
    await openProject(project.path);
    await loadNotes(project.path);
    // Save as last opened project
    invoke('set_last_project', { projectPath: project.path });
  });

  const projects = await loadProjects();
  await startWatching();

  // Restore last project
  const lastPath = await invoke('get_last_project');
  if (lastPath) {
    setActiveByPath(lastPath);
    // Trigger the same flow as clicking the project
    const project = projects?.find(p => p.path === lastPath);
    if (project) {
      updateActionBar(project);
      await openProject(project.path);
      await loadNotes(project.path);
    }
  }
}

window.addEventListener('DOMContentLoaded', init);
```

- [ ] **Step 7: Update loadProjects to return the project list**

In `plaibox-app/src/sidebar.js`, update `loadProjects` to return the list:

```javascript
export async function loadProjects() {
  allProjects = await invoke('list_projects');
  renderSidebar(allProjects);
  return allProjects;
}
```

- [ ] **Step 8: Verify state persistence works**

Run:
```bash
cd plaibox-app && cargo tauri dev
```

Expected: Click a project. Close the app. Reopen it — the same project is selected, terminal is running, notes are loaded. Check `~/.plaibox/app-state.yaml` contains the project path.

- [ ] **Step 9: Commit**

```bash
git add plaibox-app/src-tauri/src/state.rs plaibox-app/src-tauri/src/lib.rs plaibox-app/src-tauri/tests/state_test.rs plaibox-app/src/app.js plaibox-app/src/sidebar.js
git commit -m "feat: persist last-opened project across app restarts"
```

---

### Task 11: New Project and Sync Buttons

**Files:**
- Modify: `plaibox-app/src/app.js`

- [ ] **Step 1: Wire up sidebar buttons**

Add the following to `plaibox-app/src/app.js`, inside `init()` after `await startWatching()`:

```javascript
  // New project button — opens a prompt, then runs plaibox new in a temporary terminal
  document.getElementById('btn-new').addEventListener('click', () => {
    const description = prompt('New project description:');
    if (!description || !description.trim()) return;
    // If there's an active terminal, type the command there
    // Otherwise we'd need a way to run it — for now, use the active terminal
    writeToActiveTerminal(`plaibox new "${description.trim()}"\n`);
  });

  // Sync button
  document.getElementById('btn-sync').addEventListener('click', () => {
    writeToActiveTerminal('plaibox sync pull\n');
  });
```

- [ ] **Step 2: Verify buttons work**

Run:
```bash
cd plaibox-app && cargo tauri dev
```

Expected: Open a project first (so there's an active terminal). Click `+ New` — a prompt dialog appears. Enter a description — `plaibox new "your description"` is typed into the terminal. Click `Sync` — `plaibox sync pull` runs in the terminal. The sidebar updates when these commands complete (via filesystem watcher).

- [ ] **Step 3: Commit**

```bash
git add plaibox-app/src/app.js
git commit -m "feat: wire New and Sync sidebar buttons to CLI commands"
```

---

### Task 12: README and Final Polish

**Files:**
- Create: `plaibox-app/README.md`
- Modify: `plaibox-app/src-tauri/tauri.conf.json` (if needed)

- [ ] **Step 1: Write README**

Create `plaibox-app/README.md`:

```markdown
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
```

- [ ] **Step 2: Run the full test suite**

Run:
```bash
cd plaibox-app/src-tauri && cargo test
```

Expected: All Rust tests pass.

- [ ] **Step 3: Verify the app builds in release mode**

Run:
```bash
cd plaibox-app && cargo tauri build
```

Expected: Builds successfully. A `.app` bundle is created in `src-tauri/target/release/bundle/macos/`.

- [ ] **Step 4: Commit**

```bash
git add plaibox-app/README.md
git commit -m "docs: add README for plaibox app"
```
