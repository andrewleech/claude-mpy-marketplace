---
name: mpy-review
description: Review MicroPython code changes using domain-focused agents. Invoke when user mentions reviewing code, wants feedback on MicroPython PRs/commits/diffs, or asks for code review.
---

**Version:** 2.0.0

Review MicroPython code changes with parallel domain-focused agents: $ARGUMENTS

Your goal is to perform a multi-dimensional review of MicroPython code changes by launching four parallel review agents (Correctness & Safety, Resource Constraints, API & Portability, Conventions & Completeness), validating their findings to filter noise, then presenting consolidated results.

## STEP 1: DETECT CONTEXT & GATHER DIFF

### Verify MicroPython Repo

Check for MicroPython markers:
```bash
test -f py/mpconfig.h || test -f py/runtime.h || test -f mpy-cross/main.c
```

If none found:
```
This does not appear to be a MicroPython repository.
/mpy-review requires a MicroPython checkout.
```
Exit gracefully.

### Parse User Request

Determine what to review from `$ARGUMENTS` or conversation context:

| User says | Diff command |
|-----------|-------------|
| "review my current branch" / "review this branch" | `git diff main` (or detected base) |
| "review commit abc123" | `git show abc123` |
| "review PR 12345" | `gh pr diff 12345` |
| "review changes to py/gc.c" | `git diff main -- py/gc.c` |
| "review staged changes" | `git diff --cached` |
| "review uncommitted changes" | `git diff HEAD` |

If reviewing a branch, detect the base branch:
1. `git rev-parse --abbrev-ref @{upstream} 2>/dev/null`
2. `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'`
3. Fall back to `main` if it exists, then `master`

### Generate Timestamp & Gather Metadata

```bash
REVIEW_TS=$(date +%Y%m%d_%H%M%S)
```

Gather context:
```bash
# Changed files with stats
git diff --stat <BASE>..HEAD

# File list
git diff --name-only <BASE>..HEAD

# Commit log (if reviewing a branch)
git log --oneline <BASE>..HEAD

# Line change summary
git diff --shortstat <BASE>..HEAD

# Save full diff to temp file
git diff <BASE>..HEAD > /tmp/mpy_review_diff_${REVIEW_TS}.patch
```

For PR reviews, also fetch metadata:
```bash
gh pr view <PR_NUMBER> --json title,body,commits
```

### Present Summary

```
MicroPython Review Setup
========================

Branch:     <current-branch>
Base:       <BASE>
Commits:    <N>
Files:      <N> changed
Lines:      +<additions> / -<deletions>

Changed Files:
  <file list with stats>

Launching 4 review agents...
```

## STEP 2: LAUNCH PARALLEL REVIEW AGENTS

### Resolve Prompt Directory

```
PROMPT_DIR = ${CLAUDE_PLUGIN_ROOT}/prompts
RULES_DIR = ${CLAUDE_PLUGIN_ROOT}/rules
```

Verify all required prompt files exist:
- `${PROMPT_DIR}/shared-context.md`
- `${PROMPT_DIR}/correctness-safety.md`
- `${PROMPT_DIR}/resource-constraints.md`
- `${PROMPT_DIR}/api-portability.md`
- `${PROMPT_DIR}/conventions-completeness.md`

If any are missing, report an error and stop.

### Launch 4 Agents in Parallel

Launch ALL four agents in a SINGLE message using the Agent tool with
`model='opus'`.

Each agent's prompt has three parts:

**Part 1 -- Runtime Context (inline):**

```
MICROPYTHON REVIEW CONTEXT
===========================
Base Branch: <BASE>

Changed Files:
<output of git diff --name-only>

Commit History:
<output of git log --oneline BASE..HEAD>

PR Title: <title if available>
PR Body: <body if available>

Full Diff: Read /tmp/mpy_review_diff_<REVIEW_TS>.patch
```

**Part 2 -- File Read Directives:**

```
Read these files before reviewing:
1. <PROMPT_DIR>/shared-context.md (review stance, style guide, output format)
2. <PROMPT_DIR>/<dimension>.md (your specific review criteria)
3. <RULES_DIR>/development-patterns.md (MicroPython development patterns)

Then read CODECONVENTIONS.md at the repo root.
```

**Part 3 -- Execution Instruction:**

```
Apply the review stance, style guide, and dimension-specific criteria to
the diff. Explore the existing codebase around changed files before
reviewing. Return findings as a JSON array following the schema in
shared-context.md. End with a 2-3 sentence summary.
```

The four agents and their dimension files:
- Agent 1: Correctness & Safety -> `correctness-safety.md`
- Agent 2: Resource Constraints -> `resource-constraints.md`
- Agent 3: API & Portability -> `api-portability.md`
- Agent 4: Conventions & Completeness -> `conventions-completeness.md`

### Track Agent Launches

```
Review Agents Launched
======================

Agent 1: Correctness & Safety    -- launched
Agent 2: Resource Constraints    -- launched
Agent 3: API & Portability       -- launched
Agent 4: Conventions & Complete  -- launched

Waiting for results from 4 agents...
```

## STEP 3: VALIDATE FINDINGS

### Collect Raw Findings

After all 4 agents return, parse JSON findings from each. If an agent returned
malformed output, note it and continue with findings from successful agents.

Concatenate all findings into a single list. Each finding should already have
a `dimension` field from the agent (set by shared-context.md). If missing, tag
based on which agent produced it.

### Launch Validation Agent

Launch a SINGLE validation agent (separate Agent call to preserve orchestrator
context) with `model='opus'`.

The validation agent prompt:

**Part 1 -- All Raw Findings:**

```
RAW FINDINGS FROM REVIEW AGENTS
================================

<All findings as JSON array>
```

**Part 2 -- Branch Context:**

```
REVIEW CONTEXT
==============
Base Branch: <BASE>

Changed Files:
<file list>

Full Diff: Read /tmp/mpy_review_diff_<REVIEW_TS>.patch
```

**Part 3 -- File Read Directives:**

```
Read these files:
1. <PROMPT_DIR>/finding-validation.md (validation criteria)
2. <PROMPT_DIR>/shared-context.md (review stance)
3. <RULES_DIR>/development-patterns.md (project patterns)

Evaluate every finding per the validation criteria. Read source files to
verify convention findings. Follow the output format in finding-validation.md.
```

### Process Validation Results

Parse the validation output. For each finding:
- **KEEP** -- include in report
- **QUESTIONABLE** -- include with `[QUESTIONABLE]` tag and validation note
- **INVALID** -- exclude from report

```
Finding Validation
==================

Raw findings received:  <N>
  Kept:                 <N>
  Questionable:         <N> (included with flag)
  Invalid (removed):    <N>

Generating report...
```

## STEP 4: PRESENT RESULTS

### Write Report

Write to `/tmp/MPY_REVIEW_<REVIEW_TS>.md`:

```markdown
# MicroPython Review: <branch or PR description>

**Base:** <BASE> | **Commits:** <N> | **Files Changed:** <N> | **Lines:** +<X> / -<Y>
**Date:** <YYYY-MM-DD>

## Summary
<2-3 sentence assessment. State merge readiness.>

## Findings

### Correctness & Safety
<Findings from Agent 1>

### Resource Constraints
<Findings from Agent 2>

### API & Portability
<Findings from Agent 3>

### Conventions & Completeness
<Findings from Agent 4>

## Action Items
- [ ] [blocking] Description -- file:line -- commit: <hash>
- [ ] [suggestion] Description -- file:line -- commit: <hash>
- [ ] [nitpick] Description -- file:line -- commit: <hash>

## Statistics
| Dimension | Blocking | Suggestion | Nitpick |
|-----------|----------|------------|---------|
| Correctness & Safety | <N> | <N> | <N> |
| Resource Constraints | <N> | <N> | <N> |
| API & Portability | <N> | <N> | <N> |
| Conventions & Completeness | <N> | <N> | <N> |
| **Total** | **<N>** | **<N>** | **<N>** |
```

### Console Summary

```
====================================================
MICROPYTHON REVIEW COMPLETE
====================================================

Report: /tmp/MPY_REVIEW_<REVIEW_TS>.md

Branch:  <current-branch>
Base:    <BASE>
Commits: <N> | Files: <N> | Lines: +<X> / -<Y>

Validation:
  Raw findings:    <N>
  Kept:            <N>
  Questionable:    <N>
  Removed:         <N>

Issues Found:
  Blocking:    <N>
  Suggestion:  <N>
  Nitpick:     <N>

All Findings:
   1. [blocking] <title> -- <file:line> -- <commit>
   2. [suggestion] <title> -- <file:line> -- <commit>
   3. [suggestion] [QUESTIONABLE] <title> -- <file:line>
   ...

Merge Readiness: <READY | READY WITH WARNINGS | NOT READY>

Next Steps:
  1. Triage      -- walk through each finding
  2. Plan all    -- plan fixes for all findings
  3. Post to PR  -- post review to GitHub (PR reviews only)

====================================================
```

**Merge Readiness:**
- `READY` -- no blocking findings
- `READY WITH WARNINGS` -- blocking findings are all QUESTIONABLE
- `NOT READY` -- confirmed blocking findings

### User Choice

Use `AskUserQuestion` with options:
- **Triage** -- walk through findings individually (STEP 5a)
- **Plan all** -- plan all findings (STEP 5b)
- **Post to GitHub** -- post via post-review.py (STEP 5c, PR reviews only)

## STEP 5a: TRIAGE

Present each finding in severity order (blocking first). For each:

```
Finding <N>/<total>: [SEVERITY] <title>
File:           <file:line>
Commit:         <hash>
Detail:         <description>
Recommendation: <recommendation>
```

Ask user via `AskUserQuestion`: **Include** / **Skip** / **Defer**

After all findings triaged, show summary and proceed to plan generation
if any findings were included.

## STEP 5b: PLAN ALL

Include all KEEP + QUESTIONABLE findings. Proceed to plan generation.

## STEP 5c: POST TO GITHUB

Available when reviewing a PR. Assemble findings into the input format
expected by post-review.py:

```json
{
  "summary": "<review summary>",
  "findings": [<validated findings with status field>]
}
```

Write to temp file and call:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/post-review.py \
  --repo <owner/name> --pr <number> \
  --findings /tmp/mpy_review_findings_<REVIEW_TS>.json \
  --diff /tmp/mpy_review_diff_<REVIEW_TS>.patch
```

Report the result. If the script returns errors (line out of range, auth
failure), show them and offer to retry with corrections.

## PLAN GENERATION (shared by 5a and 5b)

Format included findings as numbered executable steps:

```
Step N: [SEVERITY] <title>
File:    <file:line>
Fixup:   <hash> ("<commit message>")
Change:  <what to edit>
Why:     <1 sentence>
Command: git commit --fixup=<hash>
```

QUESTIONABLE findings prefixed with `[QUESTIONABLE]` and include the
validator's note.

Final step:
```
Step N (final): Fold fixup commits
Command: git rebase --autosquash <BASE>
```

Write plan to `/tmp/MPY_REVIEW_PLAN_<REVIEW_TS>.md`, then call
`EnterPlanMode`.

## GUIDELINES

### DO:
- Verify this is a MicroPython repo before proceeding
- Launch all 4 review agents in parallel in a single tool-call message
- Always specify `model='opus'` for all agents
- Instruct agents to explore existing code before reviewing
- Require agents to attribute findings to specific commits
- Run validation agent AFTER all review agents return
- Exclude INVALID findings from the report
- Tag QUESTIONABLE findings visibly
- Sort findings by severity (blocking > suggestion > nitpick)
- Offer Post to GitHub option when reviewing PRs
- Clean up temp diff file after review completes

### DON'T:
- Launch agents sequentially
- Skip the validation step
- Include INVALID findings in the report
- Remove QUESTIONABLE findings (flag and include them)
- Apply code changes before the user approves the plan
- Reference the RAG database, embeddings, or MCP server
- Mention whose review style is being used

## ERROR HANDLING

### Not a MicroPython Repo
```
This does not appear to be a MicroPython repository.
/mpy-review requires py/mpconfig.h, py/runtime.h, or mpy-cross/main.c.
```

### No Changes Found
```
No changes found to review.
```

### Missing Prompt Files
```
Could not locate review prompt files.
Expected at: <PROMPT_DIR>/
Missing: <list>

The mpy-rules plugin may need reinstalling.
```

### Agent Failure
```
<N>/4 review agents completed successfully.
Agent <name> failed: <reason>
Proceeding with available findings.
```
