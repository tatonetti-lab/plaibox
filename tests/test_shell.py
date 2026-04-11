# tests/test_shell.py
from plaibox.shell import shell_init_script


def test_shell_init_script_contains_function():
    script = shell_init_script()
    assert "plaibox()" in script or "function plaibox" in script


def test_shell_init_script_handles_new():
    script = shell_init_script()
    assert "new" in script


def test_shell_init_script_handles_open():
    script = shell_init_script()
    assert "open" in script


def test_shell_init_script_handles_exit():
    script = shell_init_script()
    assert "exit" in script
    assert "_PLAIBOX_PREV_DIR" in script


def test_shell_init_script_handles_claude():
    script = shell_init_script()
    assert "claude" in script
    assert "script -q" in script


def test_shell_init_script_handles_codex():
    script = shell_init_script()
    assert "codex" in script


def test_shell_init_script_saves_session():
    script = shell_init_script()
    assert "plaibox session --save" in script


def test_shell_init_script_shows_session_on_open():
    script = shell_init_script()
    assert "Resume session:" in script


def test_shell_init_script_activates_venv():
    script = shell_init_script()
    assert ".venv/bin/activate" in script


def test_shell_init_script_deactivates_venv_on_exit():
    script = shell_init_script()
    assert "deactivate" in script


def test_shell_init_script_activates_venv_for_claude():
    script = shell_init_script()
    # The claude/codex branch should activate venv before launching
    assert "VIRTUAL_ENV" in script
