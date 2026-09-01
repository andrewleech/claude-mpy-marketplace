---
name: draft-pr
description: This skill MUST be used when drafting GitHub Pull Request or GitLab Merge Request titles and descriptions. This includes when the user asks to "create a PR", "open a PR", "raise a MR", "write a PR description", "draft a merge request", "submit a PR", "make a merge request", or when an agent workflow reaches a PR/MR creation step. This skill should also be used when reviewing or rewriting an existing PR/MR description.
---

# Draft PR/MR Description

Draft titles and descriptions for GitHub Pull Requests and GitLab Merge Requests by reading the actual changes from git, then presenting the draft for user confirmation before creating.

This skill takes precedence unless the current project's CLAUDE.md or equivalent defines its own PR/MR description process.

## Workflow

### 1. Determine the base branch

Auto-detect from git tracking info. Fall back to `main`, `master`, or `develop` (in that order, whichever exists). Accept an explicit override as an argument (e.g. `/draft-pr develop`).

### 2. Read the changes

Gather context from:

```bash
# All commits on this branch relative to base
git log --oneline <base>..HEAD

# Full diff against base
git diff <base>...HEAD

# Current branch name
git rev-parse --abbrev-ref HEAD
```

Read all commits, not just the latest. The description must reflect the entire branch.

### 3. Draft the title

Default format (overridable by project CLAUDE.md):

```
component: Brief imperative description.
```

Rules:
- Under 70 characters
- Imperative mood ("Add...", "Fix...", "Refactor...")
- Focus on the end-user or downstream-developer effect, not implementation mechanics
- Trailing period (default convention -- drop if project convention differs)
- `component` is the primary area of the codebase affected (e.g. `py/objstr`, `extmod/modnetwork`, `docs`)

### 4. Draft the body

Use this template:

```markdown
### Summary
<!-- Lead with what you found or what prompted the change -- the
     observation, bug, or requirement that made you open the editor.
     Give the reviewer the same "aha" moment you had: what was wrong
     or missing, and why it matters. Only then describe the approach
     taken to address it.

     Bad: "Add a shaped renderer backend using rustybuzz."
     Good: "The resvg renderer spends 92% of its time re-parsing SVG
     every frame. To avoid that overhead while keeping text quality..."

     For changes that span multiple subsystems, introduce new components,
     or alter data/control flow, include a mermaid diagram (flowchart,
     sequence, state, etc.) to give the reviewer a map of the change
     before they read the diff. -->

### Testing
<!-- What was tested and on which boards/ports. Mention anything that
     could NOT be tested. Omit this section only for trivially obvious
     changes (typo fixes, comment-only edits). -->

### Trade-offs and Alternatives
<!-- Include by default. Explain any negative impact (code size, performance)
     and why the trade-off is worthwhile. Mention alternative approaches
     considered. Delete this section entirely if genuinely irrelevant. -->

### Generative AI
<!-- Include this section when AI tools were used during development.
     Remove entirely if all code was written manually. -->

I used generative AI tools when creating this PR, but a human has checked
the code and is responsible for the description above.
```

### 5. Present draft and confirm

Show the drafted title and body to the user. On confirmation, create the PR/MR using the appropriate tool (`gh pr create` or `glab mr create`). Do not create without confirmation.

## Persisting a draft as a local file

Most of the time, draft, present, and create happen in one pass and nothing
is written to disk. Persist the draft as a local markdown file instead when
the PR cannot be raised yet - a branch that has to land after a prerequisite,
one still missing a bench result, or a queue of many such branches across a
vendored dependency or fork that gets worked through over time rather than in
one sitting. The signal is the same either way: if the user would lose this
draft by closing the session before creating the PR, write it down.

Where the file lives is a project decision, not this skill's - commonly a
directory such as `pr-drafts/` inside a planning workspace (see this
marketplace's guidance on planning workspaces for projects that carry one).
Wherever it lives, use this frontmatter so the file is machine-checkable
rather than only human-readable, and consistent across projects that persist
drafts this way:

```yaml
---
upstream_repo: owner/repo          # required: what this eventually targets
upstream_base: master              # required: the branch it is proposed against
local_branch: feature/thing        # required: the branch name locally
status: planned                    # required: see lifecycle below
title: "component: Imperative title."   # required: quoted, matches step 3's rules
pushed_branch: https://...         # once pushed: URL to the branch on the fork
fork_pr: https://...               # once raised: URL to the draft PR (see below)
head: abc123def456                 # once pushed: the commit the description was written against
relationship: |                    # when relevant: coupling to another branch/PR/repo
  Multi-line prose. What depends on what, review-order constraints, a
  companion change that lives in a different repository.
depends_on: other-branch-name      # when relevant: a prerequisite too simple for `relationship`
todo:                              # when incomplete: concrete, checkable, not "test more"
  - What's unverified and why.
worktree: /path/to/worktree        # when relevant: where this was authored, if that matters for resuming
---
```

`status` is free text - a fixed enum stops fitting the moment a branch's
situation is unusual - but track this progression unless there's a specific
reason to deviate: `planned` (described before the branch exists, typically
the generalisation of a proof-of-concept that has to land first) -> `ready to
propose` (branch exists, pushed, description written, no PR yet) -> `draft
raised on fork for review` -> `draft raised on fork for review, awaiting
sign-off before upstream` (explicit that raising the upstream PR is a
separate, later action, not automatic once the draft is clean).

**Raise persisted drafts on the fork first, targeting the fork's own default
branch, not upstream.** This gives the project owner a normal GitHub/GitLab
review UI to read the diff and description before anything is visible to an
upstream maintainer. Moving a draft from the fork to upstream is a deliberate
later action, not something this skill does on its own - do not open the
upstream PR until asked to.

When one piece of work has to be two PRs because it spans two repositories
(a core change and the driver/library change that makes it measurable, for
instance), give each its own draft file with `relationship:` pointing at the
other, and keep a short index file listing the pairs so the coupling is
visible without reading every draft.

## Writing for Reviewers

The primary audience is a reviewer who will also be reading the diff. The description's job is to provide what the diff alone cannot:

- **Context and motivation** -- why this change exists, what problem prompted it, what the user/developer was experiencing.
- **Mental model for the diff** -- help the reviewer navigate the changes. If the change touches multiple subsystems or has a non-obvious structure, explain the approach so the reviewer isn't reverse-engineering intent from the diff.
- **Architectural overview when warranted** -- for changes that introduce new components, alter data flow, change state machines, or restructure module boundaries, include a mermaid diagram in the Summary. Do not add diagrams for simple or localised changes where the diff speaks for itself.

Do not repeat what the reviewer can already see. The diff shows *what* changed; the description explains *why* and *how to think about* the change. Assume the reader is already an expert in the codebase -- provide only brief detail and background.

**Describe the current state, not the development journey.** The summary should read as an overview of what the branch delivers in its final form -- not a narrative of how it got there. Do not describe intermediate refactors, false starts, or the sequence of iterations. The commit log already captures that history. A reviewer merging this branch cares about what it *is*, not how it was built.

## Writing Style

- **First person, casual voice.** "I noticed the handler was leaking fds..." not "This change addresses a file descriptor leak..."
- **Succinct.** Every sentence must earn its place. Brief detail and background only. Aim for 100-300 words in the Summary section.
- **Lead with the why.** The opening sentence should describe what you found, observed, or were asked to fix -- the motivation, not the solution. Give the reviewer the context that made the change necessary before describing the approach.
- **Technical detail is secondary.** Only include implementation details that the diff cannot convey on its own.
- **Minimal sub-headings.** Use the template sections but do not add extra headings within them.
- **No hard-wrapping.** Do not hard-wrap paragraphs; let the renderer handle line wrapping.
- **No emdash.** Never use the em-dash character. Use a regular dash (-) instead.

## Banned Patterns

The reviewer already has access to the commit log, file list, and full diff in the review UI. Do not duplicate that content in the description.

Never include:
- **File lists** -- the diff viewer shows exactly which files changed
- **Commit-by-commit summaries** -- the commit log is already visible
- **Checklists or done-lists** -- no checkbox lists of completed work items
- **Filler or marketing language** -- no "This PR improves...", no self-congratulatory framing
- **Development narratives** -- no "I started by...", "This uplifts...", "I originally had X then changed to Y"
- **Restating the title** in the body opening
- **Excessive markdown formatting** -- no emoji headers, nested bullet hierarchies, or tables unless they genuinely clarify something

## Avoiding AI Writing Markers

PR/MR descriptions must read as natural human writing. Avoid patterns statistically associated with LLM-generated text.

**Banned vocabulary** -- these words appear at anomalously high rates in AI output and must not be used:
- delve / delve into
- robust, bolster, harness, facilitate, illuminate, underscore
- unparalleled, invaluable, pivotal
- tapestry, realm, beacon, cacophony
- leverage (as a verb meaning "use")
- streamline, foster, navigate (in abstract/metaphorical contexts)
- moreover, furthermore, in conclusion (as paragraph transitions)
- landscape (especially "ever-evolving landscape")
- comprehensive, elegant

**Structural patterns to avoid:**
- Uniform sentence length -- vary deliberately, short sentences next to longer ones
- Three-item lists by default -- use two or four when that's the right count
- Perfect parallelism across all bullet points -- slight variation reads more natural
- Formulaic paragraph openings -- do not start consecutive paragraphs the same way
- Excessive hedging -- "it's worth noting", "I'm confident that" are filler
- Summarising what was just said at the end of a section

## Project-Specific Overrides

Per-project CLAUDE.md files may override:
- Title format (e.g. dropping the `component:` prefix)
- Template sections (e.g. adding a `## Migration Guide` section)
- Voice or style (though first-person casual is the default)
- Which tool to use for creation (`gh` vs `glab` vs other)

When a project override exists, follow it. When it doesn't, this skill's defaults apply.
