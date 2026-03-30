#!/usr/bin/env bash
# pre-push hook for MicroPython — validates commits before pushing.
#
# Catches issues that pre-commit hooks miss (e.g. during rebase, where
# git cherry-pick uses implicit --no-verify).
#
# Checks:
#   1. Commit message format (verifygitlog.py) including Signed-off-by
#   2. C code formatting (codeformat.py)
#   3. Python linting and formatting (ruff)
#   4. Spelling (codespell)
#
# Install:
#   ln -sf ../../tools/pre-push-check.sh .git/hooks/pre-push
#   # Or for worktrees:
#   ln -sf $(git rev-parse --show-toplevel)/tools/pre-push-check.sh \
#          $(git rev-parse --git-dir)/hooks/pre-push
#
# Skip (emergency):
#   git push --no-verify

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"

# pre-push hook receives lines on stdin: <local ref> <local sha> <remote ref> <remote sha>
# We need the range of commits being pushed.
while read -r local_ref local_sha remote_ref remote_sha; do
    if [ "$local_sha" = "0000000000000000000000000000000000000000" ]; then
        # Deleting a branch, nothing to check
        continue
    fi

    if [ "$remote_sha" = "0000000000000000000000000000000000000000" ]; then
        # New branch — check all commits not on the remote default branch
        # Try upstream/master first, fall back to origin/main
        base=$(git merge-base "$local_sha" upstream/master 2>/dev/null \
            || git merge-base "$local_sha" origin/main 2>/dev/null \
            || echo "")
        if [ -z "$base" ]; then
            echo "pre-push: cannot determine base branch, skipping checks"
            continue
        fi
        range="${base}..${local_sha}"
    else
        range="${remote_sha}..${local_sha}"
    fi

    # Get changed files in this push
    changed_files=$(git diff --name-only "$range" 2>/dev/null || true)
    if [ -z "$changed_files" ]; then
        continue
    fi

    changed_c=$(echo "$changed_files" | grep -E '\.[ch]$' || true)
    changed_py=$(echo "$changed_files" | grep -E '\.py$' || true)

    echo "pre-push: checking $(echo "$changed_files" | wc -l) files in $range"

    errors=0

    # 1. Commit message format
    echo "  Checking commit messages..."
    if ! "$REPO_ROOT/tools/verifygitlog.py" -v "$range"; then
        errors=$((errors + 1))
    fi

    # 2. C code formatting (only if C files changed)
    if [ -n "$changed_c" ]; then
        echo "  Checking C formatting..."
        # codeformat.py -c -v -f checks formatting without modifying files
        # It exits 0 if everything is formatted, non-zero otherwise
        # Run it on the changed C files only
        if ! echo "$changed_c" | xargs "$REPO_ROOT/tools/codeformat.py" -v -c -f 2>/dev/null; then
            echo "  C formatting issues found. Run: tools/codeformat.py -v -c -f"
            errors=$((errors + 1))
        fi
    fi

    # 3. Python linting and formatting (only if Python files changed)
    if [ -n "$changed_py" ]; then
        if command -v ruff &>/dev/null; then
            echo "  Checking ruff lint..."
            if ! echo "$changed_py" | xargs ruff check --quiet 2>/dev/null; then
                errors=$((errors + 1))
            fi
            echo "  Checking ruff format..."
            if ! echo "$changed_py" | xargs ruff format --check --quiet 2>/dev/null; then
                echo "  Python formatting issues found. Run: ruff format ."
                errors=$((errors + 1))
            fi
        else
            echo "  ruff not found, skipping Python checks"
        fi
    fi

    # 4. Codespell (all changed files)
    if command -v codespell &>/dev/null; then
        echo "  Checking spelling..."
        if ! echo "$changed_files" | xargs codespell --quiet-level=2 2>/dev/null; then
            errors=$((errors + 1))
        fi
    else
        echo "  codespell not found, skipping spelling checks"
    fi

    if [ "$errors" -gt 0 ]; then
        echo ""
        echo "pre-push: $errors check(s) failed. Fix and try again."
        echo "To skip: git push --no-verify"
        exit 1
    fi

    echo "pre-push: all checks passed"
done

exit 0
