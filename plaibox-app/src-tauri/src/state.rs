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
