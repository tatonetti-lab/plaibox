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
            # Show saved session if one exists
            local session_info
            session_info=$(command plaibox session 2>/dev/null)
            if echo "$session_info" | grep -q "^Resume session:"; then
                echo ""
                echo "$session_info"
            fi
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
    elif [ "$1" = "claude" ] || [ "$1" = "codex" ]; then
        local tool="$1"
        shift
        local capture_file
        capture_file=$(mktemp /tmp/plaibox_session_XXXXXX)

        # Run the tool with script to capture output
        script -q "$capture_file" "$tool" "$@"

        # Parse resume command from captured output
        local resume_cmd=""
        if [ "$tool" = "claude" ]; then
            # Match: claude --resume <id> or claude -r <id>
            resume_cmd=$(sed $'s/\\x1b\\[[0-9;]*m//g' "$capture_file" | grep -oE "claude (--resume|-r) [a-zA-Z0-9_-]+" | tail -1)
        elif [ "$tool" = "codex" ]; then
            # Match: codex resume <id>
            resume_cmd=$(sed $'s/\\x1b\\[[0-9;]*m//g' "$capture_file" | grep -oE "codex resume [a-zA-Z0-9_-]+" | tail -1)
        fi

        rm -f "$capture_file"

        # Save if we found a resume command and we are in a plaibox project
        if [ -n "$resume_cmd" ] && [ -f ".plaibox.yaml" ]; then
            command plaibox session --save "$resume_cmd"
        fi
    else
        command plaibox "$@"
    fi
}
'''
