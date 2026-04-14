pub mod projects;
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
