use notify::event::{CreateKind, RemoveKind};
use notify::{Config, EventKind, RecommendedWatcher, RecursiveMode, Watcher};
use std::path::PathBuf;
use std::sync::mpsc;
use std::thread;
use std::time::Duration;
use tauri::{AppHandle, Emitter};

use crate::projects;

/// Start watching plaibox directories for .plaibox.yaml changes.
/// Emits "projects-changed" event to the frontend when metadata changes.
pub fn start_watcher(app_handle: AppHandle, root: String) {
    thread::spawn(move || {
        let (tx, rx) = mpsc::channel();

        let mut watcher = match RecommendedWatcher::new(tx, Config::default()) {
            Ok(w) => w,
            Err(e) => {
                eprintln!("watcher: failed to create filesystem watcher: {e}");
                return;
            }
        };

        let root_path = PathBuf::from(&root);
        for dir_name in ["sandbox", "projects", "archive"] {
            let dir = root_path.join(dir_name);
            if dir.exists() {
                if let Err(e) = watcher.watch(&dir, RecursiveMode::Recursive) {
                    eprintln!("watcher: failed to watch {}: {e}", dir.display());
                }
            }
        }

        let debounce = Duration::from_millis(500);
        let mut pending = false;

        loop {
            // If we have a pending change, wait up to the debounce window for
            // more events (trailing-edge strategy). Otherwise block until the
            // next event arrives.
            let event_result = if pending {
                match rx.recv_timeout(debounce) {
                    Ok(result) => Some(result),
                    Err(mpsc::RecvTimeoutError::Timeout) => None,
                    Err(mpsc::RecvTimeoutError::Disconnected) => break,
                }
            } else {
                match rx.recv() {
                    Ok(result) => Some(result),
                    Err(_) => break, // Channel closed
                }
            };

            if let Some(result) = event_result {
                match result {
                    Ok(event) => {
                        // Only react to changes involving .plaibox.yaml files
                        let is_metadata_change = event.paths.iter().any(|p| {
                            p.file_name()
                                .map(|n| n == ".plaibox.yaml")
                                .unwrap_or(false)
                        });

                        // Also react to folder create/delete (project added/removed)
                        let is_dir_change = matches!(
                            event.kind,
                            EventKind::Create(CreateKind::Folder)
                                | EventKind::Remove(RemoveKind::Folder)
                        );

                        if is_metadata_change || is_dir_change {
                            pending = true;
                        }
                    }
                    Err(e) => {
                        eprintln!("watcher: notify error: {e}");
                    }
                }
            } else {
                // Timeout expired -- emit the trailing-edge update
                pending = false;
                let all = projects::list_all_projects(&root);
                let _ = app_handle.emit("projects-changed", &all);
            }
        }
    });
}
