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
