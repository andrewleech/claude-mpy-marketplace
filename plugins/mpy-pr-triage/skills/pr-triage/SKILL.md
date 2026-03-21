---
name: MPy PR Triage
description: This skill should be used when the user wants to list, sort, or triage open MicroPython pull requests. Invoke when user mentions open PRs, PR triage, PR status, checking feedback on PRs, or wants to see which PRs need attention. Shows branch names, external feedback status, and local worktree/branch availability.
---

# MPy PR Triage

Display and sort open MicroPython pull requests from GitHub, enriched with local git state (branch existence, worktree paths) and external feedback timestamps.

## When to Use

- Listing open PRs for the MicroPython project
- Sorting PRs by feedback recency to find which need a response
- Checking which PRs have local worktrees or branches already set up
- Triaging old PRs to decide which to close, rebase, or update

## Workflow

### List PRs

Run the bundled script to fetch and display PR data:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/pr-triage/scripts/list-prs.py \
    --repo micropython/micropython \
    --author andrewleech \
    --sort feedback \
    --local-repo /home/corona/micropython
```

Available sort modes:
- `feedback` -- most recent external feedback first (default)
- `newest` -- most recently created first
- `oldest` -- oldest first

Add `--json` for machine-readable output that can be filtered further.

### Interpreting Output

Each PR entry shows:
- **PR number and branch name** -- the head branch for the PR
- **Created date** and **feedback date/author** -- when the last non-bot, non-author comment or review was left
- **Worktree indicator** -- `[wt: /path]` if the branch has an active worktree, `[local]` if just a local branch exists, blank if neither
- **(draft)** -- if the PR is marked as draft

Bot accounts (codecov, github-actions) are excluded from the feedback column so only human reviewer feedback is shown.

### Triage Decisions

When triaging, consider these categories:
1. **Needs response** -- has recent maintainer feedback (dpgeorge, projectgus, jimmo, robert-hh)
2. **Stale with feedback** -- had maintainer feedback but months ago, may need a rebase and ping
3. **No feedback** -- never reviewed, consider if it's still relevant or needs a description update
4. **Very old** -- 2+ years with no activity, likely candidate for closing or major rework

### Detailed PR Inspection

After listing, to dig into a specific PR:

```bash
# View PR details and comments
gh pr view <NUMBER> --repo micropython/micropython --comments

# View the diff
gh pr diff <NUMBER> --repo micropython/micropython

# Get inline review comments via API
gh api /repos/micropython/micropython/pulls/<NUMBER>/comments
```
