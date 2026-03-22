---
name: mpy-pr-triage
description: List and sort open MicroPython PRs with branch/worktree status
argument-hint: "[feedback|newest|oldest]"
allowed-tools: ["Bash", "Read"]
---

Run the PR triage script to list open MicroPython PRs. Use the argument as the sort mode (defaults to "feedback").

Determine the sort argument from the user's input. Valid values: `feedback`, `newest`, `oldest`. Default to `feedback` if not specified.

Execute:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/pr-triage/scripts/list-prs.py \
    --repo micropython/micropython \
    --author andrewleech \
    --sort <SORT_MODE> \
    --local-repo /home/corona/micropython
```

Present the output to the user. If the user asks about a specific PR, use `gh pr view <NUMBER> --repo micropython/micropython --comments` to get details.
