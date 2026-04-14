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

pub fn write_notes(project_path: &str, content: String) -> Result<(), String> {
    let path = notes_path(project_path);
    fs::write(path, content).map_err(|e| format!("Failed to save notes: {e}"))
}

pub fn append_note(project_path: &str, text: String) -> Result<(), String> {
    let existing = read_notes(project_path);
    let timestamp = Local::now().format("%b %d, %Y %-I:%M %p").to_string();

    let separator = format!("\n\n---\n*Captured {}*\n\n", timestamp);
    let new_content = if existing.is_empty() {
        format!("*Captured {}*\n\n{}", timestamp, text)
    } else {
        format!("{}{}{}", existing, separator, text)
    };

    write_notes(project_path, new_content)
}

// --- Tauri commands ---

#[tauri::command]
pub fn get_notes(project_path: String) -> String {
    read_notes(&project_path)
}

#[tauri::command]
pub fn save_notes(project_path: String, content: String) -> Result<(), String> {
    write_notes(&project_path, content)
}

#[tauri::command]
pub fn capture_note(project_path: String, text: String) -> Result<String, String> {
    append_note(&project_path, text)?;
    Ok(read_notes(&project_path))
}
