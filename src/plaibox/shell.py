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
            export _PLAIBOX_PREV_DIR="$PWD"
            cd "$output"
        else
            echo "$output"
        fi
    elif [ "$1" = "exit" ]; then
        if [ -n "$_PLAIBOX_PREV_DIR" ]; then
            cd "$_PLAIBOX_PREV_DIR"
            unset _PLAIBOX_PREV_DIR
        else
            echo "No previous directory to return to."
        fi
    else
        command plaibox "$@"
    fi
}
'''
