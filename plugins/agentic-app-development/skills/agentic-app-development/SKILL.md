---
name: agentic-app-development
description: >-
  This skill should be used when starting or continuing agentic development on
  a real, ongoing software project, as opposed to a one-off task. Covers where
  process material (research notes, tickets, PR drafts, investigation logs)
  should live relative to the shipped repository, how to scale planning
  structure to the size of the work (a couple of ticket files for a minor
  feature, versus a full phased roadmap for a large or long-running effort),
  and how to track local patches carried against a vendored or forked
  dependency until they land upstream. Use when the user says "set up a
  planning workspace", "how should I organise this project's process
  material", "this project vendors/forks X and I need to track my patches",
  "should this be its own git repo", or when a project's `./planning`
  (or equivalent) folder needs a first pass at structure. Also use when
  resuming work on a project that already has this structure, to orient
  before making changes to it.

# Agentic App Development

A pattern for running agentic development on a project over many sessions:
where process material lives relative to the code that ships, how much
planning structure a piece of work actually warrants, and how to track local
patches against a dependency you vendor or fork until they are proposed and
merged upstream. This skill states the default and the escalation points; it
does not replace judgement about a specific project.

## Two document homes

Keep two things apart, always:

- **What the system is**, in the repo that ships it. A `docs/architecture.md`
  (or equivalent) describing the system as built, with any designed-but-unbuilt
  parts labelled as such. Updated at the exit of whatever phase changed the
  system's shape, as part of that phase's work, not as a follow-up.
- **How it got that way, and what's next**, in a planning workspace the shipped
  repo does not carry: research notes, open questions, tickets, draft PR
  descriptions, investigation logs, bench scripts. None of this belongs in the
  product's commit history. A reviewer of the shipped repo should never have to
  read the journey to understand the destination.

The planning workspace defaults to `./planning/` at the project root unless the
project already has a convention. Confirm which applies before creating either
document home; do not assume greenfield.

## Choosing the planning workspace's git posture

The workspace needs *some* persistence discipline, because process material
without version history loses exactly the thing that makes it useful:
who decided what, and when. Three postures, in order of how much the workspace
needs to survive independently of the code:

1. **Untracked scratch directory.** No git of its own. Fine for genuinely
   short-lived process material that will be entirely stale once the current
   piece of work lands - a couple of ticket files for a minor feature, say.
   Loses history if deleted; that is an acceptable trade only when nothing in
   it needs to be reconstructed later.
2. **A separate local git repo, excluded from the product repo.** `git init` inside
   the workspace directory, then exclude it from the product repo via that
   repo's *local*, uncommitted exclusion mechanism (`.git/info/exclude`, not the
   tracked `.gitignore`) so the exclusion itself never enters the product's
   history and a fresh clone is not forced to carry it either. This gives the
   workspace full commit history, branches, and (if the project uses it) an
   investigation log, while guaranteeing planning material can never leak into
   a product PR by accident, because it is a different repository, not a
   different directory tree. This is the default for any project expected to
   run more than a handful of sessions.
3. **A separate git repo pushed to its own remote.** The same local repo as (2),
   with a remote added. Escalate to this when the planning material has to
   survive independently of any single machine or clone - a team where more
   than one person needs to see the roadmap, a long-running effort where losing
   the working copy would be a real loss, or a maintainer who wants the
   decision trail visible without it ever being a product PR. Nothing about the
   workspace's internal structure changes; only its durability does.

State which posture applies (and why) in the workspace's own index file, not
only in conversation, so a fresh session or a different machine can tell
immediately whether `git push` inside the workspace is expected to do anything.

## Scaling structure to the work

Default to the lightest structure that keeps the work traceable, and escalate
explicitly rather than starting heavy:

- **Minor, well-scoped work**: one or two files under `planning/tickets/` (or
  directly in `planning/` if there is no `tickets/` yet) is enough. No F/R/Q
  roadmap machinery, no phases. A short `planning/README.md` still belongs at
  the top, even for this - see below.
- **Large or long-running work**: open-ended scope, multiple dependency-ordered
  phases, or research that needs to happen before the shape of the work is even
  known. Use the vendored `phased-roadmap` skill in this plugin for the full
  procedure: fanned-out research written to timestamped reports, a living
  roadmap with numbered facts/rules/open-questions, phases carrying goals and
  exit criteria, and work items expanded into self-contained tickets stamped
  with the commit they were written against and revalidated for drift at phase
  entry. Do not hand-rewrite that procedure here; load that skill when a
  project's planning need crosses this line.

The signal to escalate is the one already stated: does the plan need to be
sequenced into independently executable chunks that will still make sense
after the context that produced them is gone? If yes, this is a
`phased-roadmap` job, not a ticket-or-two job.

## Making the workspace self-describing

Whichever scale applies, the workspace's own top-level `README.md` (or
`00_index.md`) must let a fresh agent - a new session, a different machine, a
plain workflow subagent with no access to this skill - act on the workspace
without external context. State: what lives where, the reading order, and any
conventions in force (document stamping, an open-questions numbering scheme,
whatever applies at the current scale). Update it in the same change whenever
a convention changes; it is a manual, not a report, and a stale manual is
worse than no manual because it is trusted.

If the workspace also tracks patches against a vendored dependency (below), the
index should say so and point at the sub-folder that does it, since that
sub-folder has its own, more specific conventions worth documenting separately
rather than folding into the top-level index.

## Tracking patches against a vendored or forked dependency

Some projects vendor an upstream dependency, as a submodule or an in-tree fork,
and carry local patches against it that are meant to go upstream eventually but
accumulate faster than they get reviewed and merged. Left untracked, this
becomes a single divergent branch nobody can safely rebase, split, or explain.
Track it explicitly instead:

- **One integration branch per vendored dependency**, composed from named,
  individually-upstreamable feature branches merged together (never squashed
  flat - each feature branch has to remain proposable to the upstream project
  on its own merits, independent of the others). The product build points at
  the integration branch; the feature branches are the unit of upstream
  contribution.
- **A registry file at the product repo's root**, not in the planning
  workspace, naming every carried branch per vendored dependency and which
  integration branch composes them. This is operational state the build
  depends on, not process material, so it belongs where the code that reads it
  lives. `mbm.toml` (managed by the `micropython-branch-manager` /
  `mbm` tool) is one concrete implementation of this pattern for MicroPython
  submodule forks; the pattern - a registry naming carried branches per
  vendored repo - applies to any project vendoring a dependency this way, tool
  or no tool.
- **A local draft PR description per carried branch**, in the planning
  workspace (commonly `pr-drafts/`), using the frontmatter schema documented in
  this marketplace's `draft-pr` skill (see "Persisting a draft as a local
  file"). Do not duplicate that schema here; it lives in `draft-pr` because
  drafting the description is that skill's job regardless of whether the
  result is created immediately or persisted for later.
- **Raise drafts against your own fork first, targeting the fork's own default
  branch, never upstream directly.** This gives the project owner a normal
  review UI to read the diff and description before anything is visible to an
  upstream maintainer. Moving a draft from the fork to the upstream project is
  a separate, later, explicitly-requested action.
- When one piece of work has to be two PRs because it spans two repositories -
  a core change and the driver/library change that is the only thing that
  makes it measurable, for instance - give each its own draft file and link
  them via the `relationship` field `draft-pr`'s schema provides, plus a short
  index file listing the pairs so the coupling is visible without reading
  every draft.

## Composing with other skills

This skill does not duplicate what already exists elsewhere in this
marketplace or the user's own skills; it says where each piece belongs:

- **Drafting the actual PR title and description**, and the local-file
  persistence format for one not ready to raise yet: the `draft-pr` skill.
  This skill only says where the drafts live (`pr-drafts/` in the planning
  workspace) and the fork-first raising discipline.
- **Exploratory or investigative work within a phase** - debugging, reverse
  engineering, evaluating an approach where the path matters as much as the
  result: the `investigation-log` skill, activated on the working branch for
  that phase and distilled to final-state commits before merge or review. Not
  every phase needs it; use it when the phase's own value includes what was
  tried and ruled out, not only the result.
- **Large or long-running planning**: the vendored `phased-roadmap` skill in
  this plugin, per the scaling rule above.
- **Executing a phase's work**: for coding work, tier agents by role rather
  than running everything on one model - implementation on a mid-tier model,
  automated build/test on a cheap one, both standard and adversarial review on
  the strongest available, looped (review findings -> implementer fixes ->
  re-test -> re-review) until reviews are clean and tests pass. A specific
  work item's own stated workflow shape overrides this default when present.
  `phased-roadmap`'s ticket template carries a field for exactly this.
