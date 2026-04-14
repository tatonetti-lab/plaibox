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
    #[allow(dead_code)]
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
