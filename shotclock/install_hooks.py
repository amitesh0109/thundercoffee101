#!/usr/bin/env python3
"""
Install Shot Clock hooks for Claude Code
"""

import os
import sys
from pathlib import Path


HOOK_SCRIPT = '''#!/usr/bin/env bash
# Shot Clock hook for Claude Code

SHOTCLOCK_DIR="$HOME/.shotclock"
SESSION_FILE="$SHOTCLOCK_DIR/session_$$.json"
SHOTCLOCK_ENABLED="${SHOTCLOCK:-1}"

# Check if enabled
if [ "$SHOTCLOCK_ENABLED" = "0" ] || [ "$SHOTCLOCK_ENABLED" = "off" ]; then
    exit 0
fi

# Ensure directory exists
mkdir -p "$SHOTCLOCK_DIR"

# Check if tmux is available
if ! command -v tmux &> /dev/null; then
    echo "⚠️  Shot Clock: tmux not found. Game disabled." >&2
    exit 0
fi

case "$1" in
    prompt_start)
        # User submitted a prompt - Claude is now busy
        echo '{"status": "busy", "timestamp": '$(date +%s)'}' > "$SESSION_FILE"

        # Wait 5 seconds, then open game pane if still busy
        (
            sleep 5
            if [ -f "$SESSION_FILE" ] && grep -q '"busy"' "$SESSION_FILE" 2>/dev/null; then
                # Check if we're in a tmux session
                if [ -n "$TMUX" ]; then
                    if ! tmux split-window -h -p 30 "python3 {shotclock_path} $$" 2>/dev/null; then
                        echo "⚠️  Shot Clock: couldn't open pane. Continuing without game." >&2
                    fi
                fi
            fi
        ) &
        ;;

    needs_input)
        # Claude needs user input
        if [ -f "$SESSION_FILE" ]; then
            echo '{"status": "needs_input", "timestamp": '$(date +%s)'}' > "$SESSION_FILE"
        fi
        ;;

    prompt_end)
        # Claude finished
        if [ -f "$SESSION_FILE" ]; then
            echo '{"status": "idle", "timestamp": '$(date +%s)'}' > "$SESSION_FILE"
        fi
        ;;

    session_end)
        # Claude Code session ended
        if [ -f "$SESSION_FILE" ]; then
            rm -f "$SESSION_FILE"
        fi
        ;;
esac

exit 0
'''


def get_claude_config_dir():
    """Get Claude Code config directory"""
    # Common locations for Claude Code config
    possible_paths = [
        Path.home() / ".config" / "claude-code",
        Path.home() / ".claude-code",
        Path.home() / "Library" / "Application Support" / "claude-code",
    ]

    for path in possible_paths:
        if path.exists():
            return path

    # Default to first option
    return possible_paths[0]


def install_hooks():
    """Install Shot Clock hooks"""
    print("🏀 Shot Clock - Installing hooks for Claude Code\n")

    # Get shotclock.py path
    shotclock_path = Path(__file__).parent / "shotclock.py"
    if not shotclock_path.exists():
        print("❌ Error: shotclock.py not found")
        sys.exit(1)

    # Get Claude Code config directory
    config_dir = get_claude_config_dir()
    hooks_dir = config_dir / "hooks"

    print(f"Installing hooks to: {hooks_dir}")

    # Create hooks directory
    hooks_dir.mkdir(parents=True, exist_ok=True)

    # Write hook script
    hook_file = hooks_dir / "shotclock.sh"
    hook_content = HOOK_SCRIPT.replace("{shotclock_path}", str(shotclock_path))

    with open(hook_file, 'w') as f:
        f.write(hook_content)

    # Make executable
    os.chmod(hook_file, 0o755)

    print(f"✅ Hook installed: {hook_file}")
    print("\nConfiguration:")
    print("  - Game opens after 5 seconds of Claude thinking")
    print("  - Requires tmux to be running")
    print("  - Disable with: export SHOTCLOCK=off")
    print("\nTo test:")
    print(f"  python3 {shotclock_path}")
    print("\nNote: Hook integration depends on Claude Code's actual hook system.")
    print("You may need to adjust the hook script based on the real event names.")


def uninstall_hooks():
    """Uninstall Shot Clock hooks"""
    config_dir = get_claude_config_dir()
    hook_file = config_dir / "hooks" / "shotclock.sh"

    if hook_file.exists():
        hook_file.unlink()
        print(f"✅ Removed hook: {hook_file}")
    else:
        print("❌ No hooks found to remove")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "uninstall":
        uninstall_hooks()
    else:
        install_hooks()
