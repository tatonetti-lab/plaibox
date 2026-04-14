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
    _master: Box<dyn portable_pty::MasterPty + Send>,
    child: Box<dyn portable_pty::Child + Send + Sync>,
}

pub struct TerminalManager {
    sessions: HashMap<PtyKey, PtySession>,
    next_tab: HashMap<String, u32>,
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
    ) -> Result<u32, String> {
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
            .map_err(|e| format!("Failed to open PTY: {e}"))?;

        let shell = std::env::var("SHELL").unwrap_or_else(|_| "/bin/zsh".to_string());
        let mut cmd = CommandBuilder::new(&shell);
        cmd.cwd(project_path);

        let child = pair.slave.spawn_command(cmd).map_err(|e| format!("Failed to spawn shell: {e}"))?;
        drop(pair.slave);

        let writer = pair.master.take_writer().map_err(|e| format!("Failed to get PTY writer: {e}"))?;
        let mut reader = pair.master.try_clone_reader().map_err(|e| format!("Failed to get PTY reader: {e}"))?;

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
                child,
            },
        );

        Ok(tab_index)
    }

    pub fn close(&mut self, project_path: &str, tab_index: u32) {
        let key = PtyKey {
            project_path: project_path.to_string(),
            tab_index,
        };
        if let Some(mut session) = self.sessions.remove(&key) {
            // Drop writer/master to signal EOF to the reader thread
            drop(session.writer);
            drop(session._master);
            // Kill the child process
            let _ = session.child.kill();
        }
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
) -> Result<u32, String> {
    let mut mgr = state.lock().map_err(|e| format!("Terminal lock poisoned: {e}"))?;
    mgr.spawn(&project_path, &app_handle)
}

#[tauri::command]
pub fn write_terminal(
    project_path: String,
    tab_index: u32,
    data: String,
    state: tauri::State<'_, SharedTerminalManager>,
) -> Result<(), String> {
    let mut mgr = state.lock().map_err(|e| format!("Terminal lock poisoned: {e}"))?;
    mgr.write(&project_path, tab_index, data.as_bytes());
    Ok(())
}

#[tauri::command]
pub fn resize_terminal(
    project_path: String,
    tab_index: u32,
    rows: u16,
    cols: u16,
    state: tauri::State<'_, SharedTerminalManager>,
) -> Result<(), String> {
    let mut mgr = state.lock().map_err(|e| format!("Terminal lock poisoned: {e}"))?;
    mgr.resize(&project_path, tab_index, rows, cols);
    Ok(())
}

#[tauri::command]
pub fn close_terminal(
    project_path: String,
    tab_index: u32,
    state: tauri::State<'_, SharedTerminalManager>,
) -> Result<(), String> {
    let mut mgr = state.lock().map_err(|e| format!("Terminal lock poisoned: {e}"))?;
    mgr.close(&project_path, tab_index);
    Ok(())
}