use std::fs;
use tempfile::TempDir;

#[test]
fn test_parse_config_default() {
    let dir = TempDir::new().unwrap();
    let config_path = dir.path().join("config.yaml");
    fs::write(&config_path, "root: ~/plaibox\nstale_days: 30\n").unwrap();

    let config = plaibox_app::projects::load_config_from_path(&config_path);
    assert_eq!(config.root, shellexpand::tilde("~/plaibox").to_string());
    assert_eq!(config.stale_days, 30);
    assert!(!config.sync_enabled);
}

#[test]
fn test_parse_config_with_sync() {
    let dir = TempDir::new().unwrap();
    let config_path = dir.path().join("config.yaml");
    fs::write(
        &config_path,
        "root: ~/plaibox\nstale_days: 30\nsync:\n  enabled: true\n  repo: git@github.com:user/sync.git\n  machine_name: my-mac\n",
    )
    .unwrap();

    let config = plaibox_app::projects::load_config_from_path(&config_path);
    assert!(config.sync_enabled);
}

#[test]
fn test_parse_project_metadata() {
    let dir = TempDir::new().unwrap();
    let project_dir = dir.path().join("sandbox").join("2026-04-10_my-project");
    fs::create_dir_all(&project_dir).unwrap();
    fs::write(
        project_dir.join(".plaibox.yaml"),
        "id: a1b2c3\nname: my-project\ndescription: A test project\nstatus: sandbox\ncreated: '2026-04-10'\ntags: []\ntech: [python]\n",
    )
    .unwrap();

    let projects = plaibox_app::projects::scan_space(&dir.path().join("sandbox"), "sandbox");
    assert_eq!(projects.len(), 1);
    assert_eq!(projects[0].id, "a1b2c3");
    assert_eq!(projects[0].name, "my-project");
    assert_eq!(projects[0].description, "A test project");
    assert_eq!(projects[0].status, "sandbox");
    assert_eq!(projects[0].space, "sandbox");
    assert!(!projects[0].private);
}

#[test]
fn test_parse_private_project() {
    let dir = TempDir::new().unwrap();
    let project_dir = dir.path().join("sandbox").join("2026-04-13_secret");
    fs::create_dir_all(&project_dir).unwrap();
    fs::write(
        project_dir.join(".plaibox.yaml"),
        "id: x1y2z3\nname: secret\ndescription: Private stuff\nstatus: sandbox\ncreated: '2026-04-13'\nprivate: true\ntags: []\ntech: []\n",
    )
    .unwrap();

    let projects = plaibox_app::projects::scan_space(&dir.path().join("sandbox"), "sandbox");
    assert_eq!(projects.len(), 1);
    assert!(projects[0].private);
}

#[test]
fn test_scan_skips_dirs_without_metadata() {
    let dir = TempDir::new().unwrap();
    let good = dir.path().join("sandbox").join("2026-04-10_good");
    let bad = dir.path().join("sandbox").join("no-metadata");
    fs::create_dir_all(&good).unwrap();
    fs::create_dir_all(&bad).unwrap();
    fs::write(
        good.join(".plaibox.yaml"),
        "id: aaaaaa\nname: good\ndescription: Has metadata\nstatus: sandbox\ncreated: '2026-04-10'\ntags: []\ntech: []\n",
    )
    .unwrap();

    let projects = plaibox_app::projects::scan_space(&dir.path().join("sandbox"), "sandbox");
    assert_eq!(projects.len(), 1);
    assert_eq!(projects[0].name, "good");
}
