---
name: mpy-pr-maintenance
description: Systematic workflow for maintaining a backlog of open MicroPython PRs. Use when the user asks about PR maintenance, PR backlog processing, rebasing PRs, working through open PRs, or updating stale PRs. Handles reconnaissance, reviewer feedback discussion, rebase in worktrees via subprocess, local CI validation, and force-push.
---

# MicroPython PR Maintenance Workflow

Process open PRs on micropython/micropython authored by a specific user, oldest to newest. Each PR goes through: reconnaissance, user discussion, rebase/fix in a worktree subprocess, local CI validation, and push.

## Prerequisites

- `gh` CLI authenticated with access to micropython/micropython
- The `mpy-ci` plugin installed (provides `ci/ci-local.sh` and `ci/Dockerfile`)
- The `mpy-pr-triage` plugin installed (provides PR listing)
- Docker installed and running (for CI)
- A MicroPython repo clone as the working directory with `origin` pointing to the user's fork and `upstream` pointing to `micropython/micropython`

## Phase 0: Initialization

### Fetch the PR list

Use the triage plugin or `gh` directly to get open PRs:

```bash
gh pr list --repo micropython/micropython --author @me --state open --json number,title,headRefName,createdAt,isDraft --limit 100
```

Sort by `createdAt` ascending (oldest first).

### Initialize state file

Create or load `~/mpy/pr-maintenance-state.json`:

```json
{
  "last_updated": "ISO-8601 timestamp",
  "current_pr_index": 0,
  "prs": [
    {
      "number": 5323,
      "branch": "ordered_maps",
      "status": "pending",
      "notes": ""
    }
  ]
}
```

Valid statuses: `pending`, `in_progress`, `completed`, `skipped`, `deferred`, `closed`.

Update `current_pr_index` as PRs are processed. Save after each PR completes.

## Phase 1: Reconnaissance

For each PR, run 5 parallel Bash calls to gather:

1. **PR metadata** -- title, body, labels, draft status, mergeable state:
   ```bash
   gh pr view <NUMBER> --repo micropython/micropython --json title,body,labels,isDraft,mergeable,baseRefName,headRefName,createdAt,updatedAt
   ```

2. **Comments and reviews** -- all discussion, review comments, inline review comments:
   ```bash
   gh pr view <NUMBER> --repo micropython/micropython --comments
   gh api /repos/micropython/micropython/pulls/<NUMBER>/comments
   gh api /repos/micropython/micropython/pulls/<NUMBER>/reviews
   ```

3. **CI status** -- check runs on the PR head:
   ```bash
   gh pr checks <NUMBER> --repo micropython/micropython
   ```

4. **Branch state** -- whether the branch exists locally, divergence from upstream/master:
   ```bash
   git fetch origin <BRANCH> 2>&1
   git log --oneline origin/<BRANCH>..upstream/master | head -20
   git log --oneline upstream/master..origin/<BRANCH>
   ```

5. **Commit history** -- commits on the PR branch:
   ```bash
   gh api /repos/micropython/micropython/pulls/<NUMBER>/commits --jq '.[].commit.message'
   ```

### Identify unaddressed feedback

Filter comments and reviews to find feedback from external reviewers (not the PR author, not bots). Key maintainer accounts: `dpgeorge`, `projectgus`, `jimmo`, `robert-hh`.

Feedback is "unaddressed" if:
- It was posted after the last push to the PR branch
- It requests changes or asks questions
- No subsequent comment from the PR author responds to it

## Phase 2: User Discussion

Present findings to the user:

1. PR title, age, and current state
2. Summary of unaddressed reviewer feedback (quote key comments)
3. Whether the PR is a draft
4. How far behind upstream/master it is
5. Proposed action: what changes are needed to address feedback

Wait for the user to choose one of:
- **proceed** -- continue to rebase and fix
- **skip** -- mark as `skipped`, move to next PR
- **close** -- close the PR via `gh pr close <NUMBER> --repo micropython/micropython`, mark as `closed`
- **defer** -- mark as `deferred`, move to next PR
- **discuss** -- talk through the feedback before deciding

For draft PRs, default recommendation is `skip` unless the user says otherwise.

### Batch mode

If multiple PRs have no unaddressed reviewer feedback, present them as a batch and offer to launch all of them in parallel (up to 6 concurrent subprocesses). Still present each PR's summary so the user can exclude any.

## Phase 3: Rebase and Fix

### Set up worktree

```bash
git fetch origin <BRANCH>
git worktree add ~/mpy/<BRANCH> origin/<BRANCH>
cd ~/mpy/<BRANCH> && git checkout -b <BRANCH>
git remote add upstream https://github.com/micropython/micropython.git 2>/dev/null || true
git fetch upstream master
```

Install CI tooling and project context into the worktree:

```bash
ln -sf ~/CLAUDE_micropython.md ~/mpy/<BRANCH>/CLAUDE.md
mkdir -p ~/mpy/<BRANCH>/ci
cp ${CLAUDE_PLUGIN_ROOT}/../mpy-ci/skills/mpy-ci/scripts/ci-local.sh ~/mpy/<BRANCH>/ci/ci-local.sh
cp ${CLAUDE_PLUGIN_ROOT}/../mpy-ci/skills/mpy-ci/assets/Dockerfile ~/mpy/<BRANCH>/ci/Dockerfile
chmod +x ~/mpy/<BRANCH>/ci/ci-local.sh
```

If `${CLAUDE_PLUGIN_ROOT}` is not available, fall back to the CI files in the current repo's `ci/` directory, or ask the user for the path.

### Launch subprocess

Build a prompt from the templates in `references/prompt-templates.md`. The prompt must include:
- The specific reviewer feedback to address (quoted)
- Instructions to rebase onto upstream/master
- Instructions to fix code formatting
- Instructions to build and test

Run:

```bash
cd ~/mpy/<BRANCH> && claude -p --dangerously-skip-permissions "<PROMPT>" 2>&1 | tee /tmp/claude-pr-<NUMBER>.log | tail -30
```

Key points about the subprocess:
- `--dangerously-skip-permissions` is required because `-p` (pipe/non-interactive mode) cannot approve tool permission prompts
- The subprocess gets its own context window, which is better for complex rebase/rewrite work
- If the subprocess fails or needs manual intervention, the user can resume with: `cd ~/mpy/<BRANCH> && claude`
- The full log is at `/tmp/claude-pr-<NUMBER>.log`

### Verify worktree state after subprocess

After the subprocess exits, verify:
```bash
cd ~/mpy/<BRANCH> && git status
cd ~/mpy/<BRANCH> && git log --oneline upstream/master..HEAD
```

Check that:
- Working tree is clean (no uncommitted changes)
- Branch is ahead of upstream/master
- No stale submodule pointer changes (drop them if present: `git checkout upstream/master -- lib/`)

## Phase 4: CI Validation

### Select CI targets

Determine which CI targets to run based on changed files:

```bash
cd ~/mpy/<BRANCH> && git diff --name-only upstream/master...HEAD
```

Apply these rules:

| Changed path pattern | CI targets |
|---|---|
| `py/**`, `extmod/**`, `shared/**`, `lib/**`, `drivers/**` | `unix`, `stm32` |
| `ports/stm32/**` | `stm32` |
| `ports/esp32/**` | `esp32` |
| `ports/rp2/**` | `rp2` |
| `ports/unix/**` | `unix` |
| `ports/<port>/**` | that port's target name |
| `tests/**` | `unix` |
| `docs/**` | `docs` |
| `tools/mpremote/**` | `mpremote` |

Always include: `format`, `codespell`, `ruff`.

Deduplicate the target list.

### Run CI in background

```bash
cd ~/mpy/<BRANCH> && ./ci/ci-local.sh format codespell ruff <PORT_TARGETS> 2>&1 | tee /tmp/ci-pr-<NUMBER>.log &
```

Run CI in the background so the next PR can be processed in parallel. Record the background job PID for later checking.

### Known flaky tests

These tests fail intermittently and should not block a push:
- `thread/stress_schedule.py`
- `misc/sys_settrace_features.py`

## Phase 5: Push

After CI passes (check the background job):

```bash
cd ~/mpy/<BRANCH> && git push origin <BRANCH> --force-with-lease
```

`--force-with-lease` prevents overwriting changes pushed by someone else since the last fetch.

Update state file: set PR status to `completed`.

### After push

Optionally leave a comment on the PR noting the rebase:
```bash
gh pr comment <NUMBER> --repo micropython/micropython --body "Rebased onto current master and addressed review feedback."
```

## Phase 6: Cleanup

After all PRs are processed:

```bash
# Remove worktrees for completed PRs only
git worktree list | grep ~/mpy/ | awk '{print $1}' | xargs -I{} git worktree remove {}
```

Only clean up worktrees for PRs with status `completed`. Keep worktrees for `deferred` or `in_progress` PRs.

## Edge Cases

### Inter-dependent PRs
Process the oldest (base) PR first. If PR B depends on PR A, rebase A first, then rebase B onto A's updated branch.

### Very old PRs (2+ years)
Expect significant conflicts. The subprocess may need to reimplement the feature on current master rather than performing a git rebase. Flag this to the user during Phase 2.

### Stale submodule pointers
Submodule pointer changes (in `lib/`) that differ from upstream/master should be dropped:
```bash
git checkout upstream/master -- lib/
git commit --amend --no-edit
```

### Draft PRs
Present to the user during Phase 2 with a default recommendation of `skip`. The user may choose to proceed if the draft is close to ready.

## Resources

### references/prompt-templates.md
Subprocess prompt templates for different PR scenarios (simple rebase, rebase with feedback, major rework, squash and clean up).
