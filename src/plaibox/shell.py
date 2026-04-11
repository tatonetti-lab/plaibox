# src/plaibox/shell.py

def shell_init_script() -> str:
    """Return a shell function that wraps the plaibox CLI to enable cd behavior."""
    return '''\
plaibox() {
    if [ "$1" = "new" ] || [ "$1" = "open" ]; then
        local output
        output=$(command plaibox "$@")
        local exit_code=$?
        if [ $exit_code -eq 0 ] && [ -d "$output" ]; then
            cd "$output"
        else
            echo "$output"
        fi
    else
        command plaibox "$@"
    fi
}
'''
