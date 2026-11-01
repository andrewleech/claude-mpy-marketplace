#!/usr/bin/env bash
# Deliver the MicroPython rules to the agent that runs this SessionStart hook.
#
# Claude Code:
# 1. Copies canonical rule files to ~/.claude/mpy-rules/ (stable location)
# 2. If current dir is a MicroPython repo, symlinks .claude/rules/ -> ~/.claude/mpy-rules/
# 3. Installs the pre-push hook if none exists
# 4. Ensures .claude/ is locally gitignored
#
# Codex (detected by PLUGIN_ROOT and CODEX_HOME both set):
# In a MicroPython repo, prints rules/core.md plus an index of the other rule
# files to stdout, which Codex adds to the model context. Writes no files and
# prints nothing else, also outside a MicroPython repo.
#
# The extension in hooks/pre/mpy-rules.ts does the same job for omp.
#
# Environment:
#   CLAUDE_PLUGIN_ROOT - set by Claude Code and Codex, points to the plugin directory
#   PLUGIN_ROOT, CODEX_HOME - set by Codex only

set -euo pipefail

# Codex exports PLUGIN_ROOT and CODEX_HOME to hook processes; Claude Code sets neither.
# Evaluate before PLUGIN_ROOT is reassigned below.
if [ -n "${PLUGIN_ROOT:-}" ] && [ -n "${CODEX_HOME:-}" ]; then
    IS_CODEX=1
else
    IS_CODEX=0
fi

is_micropython_repo() {
    # Check for key MicroPython markers
    [ -f "py/mpconfig.h" ] || [ -f "py/runtime.h" ] || [ -f "mpy-cross/main.c" ]
}

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}}"
SOURCE_DIR="$PLUGIN_ROOT/rules"
CANONICAL_DIR="$HOME/.claude/mpy-rules"

# --- Codex: print rules to stdout, change nothing ---

# Prints the file without its YAML frontmatter.
strip_frontmatter() {
    awk 'NR == 1 && $0 == "---" { fm = 1; next } fm && $0 == "---" { fm = 0; next } !fm' "$1"
}

# Prints "description<TAB>paths" for a rule file; paths are comma separated.
rule_meta() {
    awk '
        NR == 1 && $0 == "---" { fm = 1; next }
        fm && $0 == "---" { exit }
        !fm { next }
        /^description:/ {
            sub(/^description:[ \t]*/, "")
            gsub(/^"|"$/, "")
            desc = $0
            inpaths = 0
            next
        }
        /^paths:/ { inpaths = 1; next }
        inpaths && /^[ \t]*-/ {
            sub(/^[ \t]*-[ \t]*/, "")
            gsub(/"/, "")
            paths = paths (paths == "" ? "" : ", ") $0
            next
        }
        { inpaths = 0 }
        END { printf "%s\t%s\n", desc, paths }
    ' "$1"
}

print_codex_context() {
    echo "# MicroPython rules (mpy-rules plugin)"
    strip_frontmatter "$SOURCE_DIR/core.md"
    echo
    echo "## Other MicroPython rule files"
    echo
    echo "Read a file below in full before you touch the paths it covers."
    echo
    local f desc paths
    for f in "$SOURCE_DIR"/*.md; do
        [ -f "$f" ] || continue
        [ "$(basename "$f")" = "core.md" ] && continue
        IFS=$'\t' read -r desc paths < <(rule_meta "$f")
        echo "- $f - scope: ${paths:-any MicroPython work} - $desc"
    done
}

if [ "$IS_CODEX" = 1 ]; then
    if is_micropython_repo; then
        print_codex_context
    fi
    exit 0
fi

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

# --- Step 3: Install pre-push hook if not present ---

# The pre-push hook catches issues that pre-commit misses (e.g. during rebase,
# where git cherry-pick uses implicit --no-verify). It checks commit messages,
# C formatting, ruff, and codespell on the commit range being pushed.

git_dir="$(git rev-parse --git-common-dir 2>/dev/null || true)"
if [ -n "$git_dir" ]; then
    hook_target="$git_dir/hooks/pre-push"
    repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
    # Prefer the in-repo script, fall back to the plugin's bundled copy
    hook_source="$repo_root/tools/pre-push-check.sh"
    if [ ! -f "$hook_source" ]; then
        hook_source="$PLUGIN_ROOT/scripts/pre-push-check.sh"
    fi

    if [ -f "$hook_source" ] && [ ! -e "$hook_target" ]; then
        ln -sf "$hook_source" "$hook_target"
        echo "Installed pre-push hook: $hook_target -> $hook_source"
    fi
fi

# --- Step 4: Ensure .claude/ is locally gitignored ---

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
