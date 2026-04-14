pub mod projects;
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
