use tempfile::TempDir;

#[test]
fn test_read_notes_missing_file() {
    let dir = TempDir::new().unwrap();
    let content = plaibox_app::notes::read_notes(dir.path().to_str().unwrap());
    assert_eq!(content, "");
}

#[test]
fn test_write_and_read_notes() {
    let dir = TempDir::new().unwrap();
    let path = dir.path().to_str().unwrap();

    plaibox_app::notes::write_notes(path, "# My Notes\nSome content".to_string()).unwrap();

    let content = plaibox_app::notes::read_notes(path);
    assert_eq!(content, "# My Notes\nSome content");
}

#[test]
fn test_append_note() {
    let dir = TempDir::new().unwrap();
    let path = dir.path().to_str().unwrap();

    plaibox_app::notes::write_notes(path, "Existing note".to_string()).unwrap();
    plaibox_app::notes::append_note(path, "Captured text here".to_string()).unwrap();

    let content = plaibox_app::notes::read_notes(path);
    assert!(content.starts_with("Existing note"));
    assert!(content.contains("Captured text here"));
    assert!(content.contains("---"));
}

#[test]
fn test_append_note_to_empty() {
    let dir = TempDir::new().unwrap();
    let path = dir.path().to_str().unwrap();

    plaibox_app::notes::append_note(path, "First capture".to_string()).unwrap();

    let content = plaibox_app::notes::read_notes(path);
    assert!(content.contains("First capture"));
}
