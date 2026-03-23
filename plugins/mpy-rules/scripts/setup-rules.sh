#!/usr/bin/env bash
# Setup MicroPython rules in the current project.
#
# Called by the SessionStart hook. Performs:
# 1. Copies canonical rule files to ~/.claude/mpy-rules/ (stable location)
# 2. If current dir is a MicroPython repo, symlinks .claude/rules/ -> ~/.claude/mpy-rules/
# 3. Ensures .claude/ is locally gitignored
#
# Environment:
#   CLAUDE_PLUGIN_ROOT - set by Claude Code, points to the plugin directory

set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:?CLAUDE_PLUGIN_ROOT not set}"
CANONICAL_DIR="$HOME/.claude/mpy-rules"
SOURCE_DIR="$PLUGIN_ROOT/rules"

# --- Step 1: Copy rule files to stable canonical location ---

mkdir -p "$CANONICAL_DIR"

updated=0
for src in "$SOURCE_DIR"/*.md; do
    [ -f "$src" ] || continue
    name="$(basename "$src")"
    dst="$CANONICAL_DIR/$name"
    # Only copy if source is newer or destination doesn't exist
    if [ ! -f "$dst" ] || [ "$src" -nt "$dst" ]; then
        cp "$src" "$dst"
        updated=$((updated + 1))
    fi
done

if [ "$updated" -gt 0 ]; then
    echo "Updated $updated rule file(s) in $CANONICAL_DIR"
fi

# --- Step 2: Detect MicroPython repo and create symlinks ---

is_micropython_repo() {
    # Check for key MicroPython markers
    [ -f "py/mpconfig.h" ] || [ -f "py/runtime.h" ] || [ -f "mpy-cross/main.c" ]
}

if ! is_micropython_repo; then
    exit 0
fi

mkdir -p .claude/rules

linked=0
for src in "$CANONICAL_DIR"/*.md; do
    [ -f "$src" ] || continue
    name="$(basename "$src")"
    dst=".claude/rules/$name"

    # Skip if already a correct symlink
    if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
        continue
    fi

    # Remove stale file/symlink if present
    rm -f "$dst"
    ln -s "$src" "$dst"
    linked=$((linked + 1))
done

if [ "$linked" -gt 0 ]; then
    echo "Linked $linked rule file(s) into .claude/rules/"
fi

# --- Step 3: Ensure .claude/ is locally gitignored ---

# Only proceed if we're in a git repo
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    exit 0
fi

if command -v git-ignore >/dev/null 2>&1; then
    # git-ignore-tool handles worktrees, submodules, and all edge cases
    git ignore -l .claude/ 2>/dev/null || true
else
    echo "WARNING: git-ignore not found. Install with: cargo install git-ignore-tool"
    echo "  Without it, .claude/ may show as untracked in worktrees/submodules."
    echo "  Falling back to .git/info/exclude for this repo only."

    # Simple fallback for plain repos
    exclude_file="$(git rev-parse --git-dir)/info/exclude"
    if [ -f "$exclude_file" ]; then
        if ! grep -qxF '.claude/' "$exclude_file" 2>/dev/null; then
            echo '.claude/' >> "$exclude_file"
        fi
    fi
fi
