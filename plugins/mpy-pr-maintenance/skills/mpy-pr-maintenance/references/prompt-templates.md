# Subprocess Prompt Templates

Templates for the `claude -p` subprocess launched in each PR's worktree. Select the appropriate template based on the PR's situation. Replace all `<PLACEHOLDERS>` with actual values.

## Template 1: Simple Rebase (no reviewer feedback)

```
You are working in a MicroPython git worktree at ~/mpy/<BRANCH>.

Task: Rebase this branch onto upstream/master and ensure it builds cleanly.

Steps:
1. Run: git fetch upstream master
2. Run: git rebase upstream/master
3. If there are conflicts, resolve them. The intent of this branch is: <PR_TITLE_AND_DESCRIPTION>
4. After rebase, run: git diff --check HEAD~<N_COMMITS>..HEAD  (to check for whitespace errors)
5. Run the code formatters: ./ci/ci-local.sh format
6. If formatting changed any files, amend the relevant commits with: git add -u && git commit --amend --no-edit
7. Verify no stale submodule pointers: git diff upstream/master -- lib/
   If lib/ has changes, drop them: git checkout upstream/master -- lib/ && git commit --amend --no-edit
8. Run a quick build test: ./ci/ci-local.sh <PRIMARY_PORT>

Report what you did and whether the build succeeded.
```

## Template 2: Rebase with Reviewer Feedback

```
You are working in a MicroPython git worktree at ~/mpy/<BRANCH>.

This is PR #<NUMBER>: <PR_TITLE>
PR description: <PR_DESCRIPTION>

Reviewer feedback that must be addressed:

<QUOTED_FEEDBACK>

Task: Rebase onto upstream/master and address the reviewer feedback above.

Steps:
1. Read the relevant source files to understand the current state of the PR.
2. Run: git fetch upstream master
3. Run: git rebase upstream/master
4. If there are conflicts, resolve them consistent with the PR's intent.
5. Address each piece of reviewer feedback:
   - Make the requested code changes
   - If a reviewer suggestion is unclear or conflicts with the PR's purpose, document your reasoning in a comment at the top of the relevant function
6. Run: ./ci/ci-local.sh format
7. If formatting changed files, stage and amend: git add -u && git commit --amend --no-edit
8. Verify no stale submodule pointers: git diff upstream/master -- lib/
   If lib/ has changes, drop them: git checkout upstream/master -- lib/ && git commit --amend --no-edit
9. Run: ./ci/ci-local.sh <PRIMARY_PORT>

Report:
- What rebase conflicts occurred and how you resolved them
- How you addressed each piece of reviewer feedback
- Build result
```

## Template 3: Major Rework (very old PR, heavy conflicts expected)

```
You are working in a MicroPython git worktree at ~/mpy/<BRANCH>.

This is PR #<NUMBER>: <PR_TITLE>
PR description: <PR_DESCRIPTION>

This PR is very old (<AGE>) and is expected to have significant conflicts with current upstream/master. A mechanical rebase may not be feasible. You may need to re-implement the feature from scratch on current master.

The original commits on this branch are:
<COMMIT_LOG>

Original reviewer feedback (if any):
<QUOTED_FEEDBACK>

Task: Get this PR's functionality working on current upstream/master.

Steps:
1. Read the current state of the PR's changed files to understand the feature.
2. Run: git fetch upstream master
3. Attempt: git rebase upstream/master
4. If the rebase has too many conflicts (more than 3 files with non-trivial conflicts):
   a. Abort: git rebase --abort
   b. Reset to upstream/master: git reset --hard upstream/master
   c. Re-implement the feature by reading the original commits and applying the same changes to the current codebase
   d. Create clean commits with descriptive messages
5. Run: ./ci/ci-local.sh format
6. Stage and commit any formatting fixes separately.
7. Verify no stale submodule pointers.
8. Run: ./ci/ci-local.sh <PRIMARY_PORT>

Report:
- Whether you used rebase or reimplementation
- What changes you made relative to the original PR
- How you addressed reviewer feedback (if any)
- Build result
```

## Template 4: Squash and Clean Up

Use this when a PR has too many small fixup commits and needs to be cleaned up into logical commits.

```
You are working in a MicroPython git worktree at ~/mpy/<BRANCH>.

This is PR #<NUMBER>: <PR_TITLE>

The branch has <N> commits that should be consolidated into logical units.

Current commits:
<COMMIT_LOG>

Task: Squash commits into clean, logical units and rebase onto upstream/master.

Steps:
1. Run: git fetch upstream master
2. Run: git rebase upstream/master
3. Resolve any conflicts.
4. Squash related commits using: git reset --soft upstream/master
5. Create clean commits:
   - One commit per logical change
   - Each commit message should follow MicroPython conventions: "<component>: <description>."
   - Component examples: py, extmod, stm32, esp32, rp2, tools, tests, docs
6. Run: ./ci/ci-local.sh format
7. Amend if formatting changed files.
8. Run: ./ci/ci-local.sh <PRIMARY_PORT>

Report what commits you created and the build result.
```

## Prompt Construction Notes

- Always include the full reviewer feedback text, not a summary. The subprocess cannot access GitHub.
- Set `<PRIMARY_PORT>` based on the files changed in the PR. If the PR touches `ports/stm32/`, use `stm32`. If it touches core (`py/`, `extmod/`), use `unix`.
- For PRs touching multiple ports, pick the most affected port for the subprocess build test. Full CI runs in Phase 4 after the subprocess completes.
- The subprocess has no access to the parent Claude session's context. Everything it needs must be in the prompt.
