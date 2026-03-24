---
name: mpy-pr-maintenance
description: Process open MicroPython PR backlog systematically
argument-hint: "[PR number]"
allowed-tools: ["Bash", "Read", "Agent", "Write"]
---

Start the MicroPython PR maintenance workflow. If a PR number is given, process that specific PR. Otherwise, start from the beginning of the backlog (oldest first).

Follow the full workflow documented in the `mpy-pr-maintenance` skill:

1. **Initialization** -- Fetch open PRs and load/create the state file at `~/mpy/pr-maintenance-state.json`
2. **Reconnaissance** -- Gather PR metadata, comments, reviews, CI status, branch state, and commit history
3. **User Discussion** -- Present findings and wait for user decision (proceed/skip/close/defer/discuss)
4. **Rebase and Fix** -- Set up worktree and launch subprocess
5. **CI Validation** -- Run appropriate CI targets based on changed files
6. **Push** -- Force-push with lease after CI passes

Present each PR's status to the user before taking action. Always wait for user confirmation before proceeding with rebase, close, or push operations.
