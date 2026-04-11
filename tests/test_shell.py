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
