use tempfile::TempDir;

#[test]
fn test_read_state_missing_file() {
    let dir = TempDir::new().unwrap();
    let state = plaibox_app::state::read_app_state(dir.path());
    assert!(state.last_project.is_none());
}

#[test]
fn test_write_and_read_state() {
    let dir = TempDir::new().unwrap();

    plaibox_app::state::save_app_state(
        dir.path(),
        &plaibox_app::state::AppState {
            last_project: Some("/Users/nick/plaibox/sandbox/2026-04-10_test".to_string()),
        },
    );

    let state = plaibox_app::state::read_app_state(dir.path());
    assert_eq!(
        state.last_project.unwrap(),
        "/Users/nick/plaibox/sandbox/2026-04-10_test"
    );
}
