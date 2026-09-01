---
name: phased-roadmap
description: >-
  Turn an open-ended project or topic into a phased implementation roadmap where
  every phase is decomposed into activities ready to hand to dynamic (multi-agent)
  workflows. Use when the user says "let's plan out this project", "develop a
  phased plan", "research and roadmap this topic", "investigate X and produce a
  plan", "break this into workflows", "document the current state and plan how to
  extend it", or otherwise asks to go from a broad goal to a sequenced,
  execution-ready plan. Covers the full arc: set up capture discipline, fan out
  parallel research agents that write timestamped reports, verify the load-bearing
  facts yourself, track open design questions to dated decisions, write phases
  that each carry a goal, work items, targets, tests, exit criteria, and a
  model-tiered workflow decomposition, and expand substantive work items into
  self-contained commit-stamped ticket files upfront, revalidated deterministically
  at phase entry. Also use it to resume or extend an existing roadmap when new
  information or user direction arrives, or to revalidate a phase's tickets when
  entering that phase.
---

# Phased Roadmap Planning

Bundled in the `agentic-app-development` plugin as the heavyweight option for
large or long-running planning, alongside that plugin's lighter default of a
ticket or two for minor work. See that plugin's own skill for where this fits,
the planning workspace's git posture, and how patches against a vendored
dependency are tracked - this skill covers the roadmap-and-tickets procedure
itself and nothing outside it.

A procedure for taking a broad, open-ended topic ("extend X across the codebase",
"add capability Y", "modernise subsystem Z") and producing a roadmap that is
sequenced by dependency and broken down so each phase can be executed by a
dynamic multi-agent workflow. The output is a set of living documents, not a
one-shot report.

This is a planning-and-research skill. It stops at an execution-ready plan; it
does not implement. Implementation happens later, phase by phase, via the
`Workflow` tool using the decomposition this skill writes.

The procedure is iterative, not linear. The user commonly injects new direction
mid-stream - a firsthand fact, a decision, an added goal - and the plan absorbs
it by updating the living documents in place (Step 6), not by restarting. Expect
to revisit Steps 3-5 each time that happens.

## When this applies

The request is strategic and open-ended: the answer is a plan, not a patch. There
is real research to do first (current state is not fully known), the work is too
big for one pass, and the user wants it sequenced into independently executable
chunks. If the task is a single well-scoped change, this skill is overkill.

## Core principles

1. **Capture before conclusions.** Set up the planning folder and context doc
   first, so every research artifact lands somewhere durable and commit-anchored.
2. **Fan out research, keep only conclusions.** Independent dimensions get
   independent agents running in parallel. Each writes a detailed timestamped
   report to the planning folder and returns only a concise summary. The main
   context never fills with raw file dumps.
3. **Verify what the plan rests on.** Before building the roadmap on a claim,
   check it against source yourself, especially anything an agent reported as a
   summary. Plans that hinge on an unverified fact are fragile.
4. **Track open questions explicitly.** Every unresolved design decision is a
   numbered question owned by a phase, closed later with a dated decision and a
   design note. New information updates the living documents, it does not fork
   them.
5. **Phases are dependency-ordered and workflow-ready.** Not calendar-ordered.
   Each phase names what it depends on and carries everything a workflow needs to
   execute it: goal, work items, targets, tests, exit criteria, and a
   model-tiered agent decomposition.
6. **Substantive work items become self-contained tickets, written at peak
   knowledge, revalidated at phase entry.** During planning, while the research
   context is fully loaded, non-trivial work items across all phases are expanded
   into individual ticket files with enough detail and cross-references that the
   implementation workflow planner does not have to re-research. Future-phase
   knowledge gathered by the upfront research is captured now, not lost when the
   planning session's context is gone. The staleness this creates is handled, not
   avoided: every ticket (like every planning output) is stamped with its date
   and HEAD commit SHA, so at phase entry the planner can deterministically
   compute exactly what changed since the ticket was written and update it
   before executing (Step 5c).

## Procedure

### Step 1 - Set up capture discipline

Create (or confirm) two things before researching:

- A **planning folder** (default `./planning/`). Every report goes here as
  `YYYYMMDD_<topic>.md` with a header line stating the date and the current HEAD
  commit SHA (`git rev-parse --short=10 HEAD`). This makes every finding
  reproducible against a known tree state.
- A **context/design-rules document** (e.g. `CLAUDE.local.md` in the working
  dir, or a `planning/00_context.md`). It states the goal, the working design
  rules, and an index of the planning documents. It is the thing loaded into
  future sessions, so keep it current as decisions close. Note the planning
  folder also gets its own index / operating-instructions file (Step 5d) so it
  stays actionable by agents that see only the repo; a stub now is fine, but it
  must exist and be complete by the end of Step 5.

Read any reference material the user points at (discussions, PRs, prior art) in
this step, or delegate it to a research agent in Step 2.

### Step 2 - Fan out research

Identify the independent dimensions of the unknown. Typical dimensions:

- **Prior art / precedent** in the codebase (what pattern already solves a
  similar problem and should be copied).
- **Current-state survey** across the breadth the roadmap must cover (per-port,
  per-module, per-service). For wide surveys use a coordinator agent that spawns
  per-item workers, then consolidates a matrix.
- **External context** (an upstream discussion, an RFC/PR, a competing project's
  approach) read deeply for constraints and stated positions.

Spawn these as parallel agents in a single message (multiple Agent calls in one
turn so they run concurrently). Each agent's final message returns to you as the
tool result, so the report-to-disk / summary-to-you split is enforced by how you
word the prompt. Give each agent a prompt that ends with, verbatim in spirit:

> Write your detailed report to `./planning/YYYYMMDD_<topic>.md` with a header
> containing the date and HEAD commit SHA. Return to me only a concise summary:
> the top findings and anything that contradicts the working assumptions. Do not
> paste the whole report back.

For a **wide survey** (per-port, per-module, per-service across many similar
items), use a coordinator agent that spawns one worker per item and then
consolidates their findings into a single matrix. Two failure modes to guard
against explicitly in the coordinator's prompt: (a) it can return a skeleton with
the matrix left as placeholders if not told to fill every cell from the workers'
results and write the consolidated file itself; (b) a single worker's summary may
overturn a shared assumption, so have the coordinator surface contradictions, not
just aggregate. If a coordinator returns an incomplete matrix, send it back with
the specific empty cells and missing items named (Step 2's incomplete-deliverable
rule applies to coordinators too).

Match the model to the role. For research/design/audit dimensions, pick the model
that fits the task (a deep adversarial review of a contested design merits the
strongest tier; a mechanical file survey does not). When the later phases involve
coding, the standing tiering is implementation→sonnet, automated testing→haiku,
standard+adversarial review→opus; that tiering governs the *workflow
decomposition* you write in Step 5, not necessarily the research agents here.

If an agent returns an incomplete or all-placeholder deliverable, send it back
with specific gaps listed rather than accepting it.

### Step 3 - Verify load-bearing facts

Before writing the plan, personally check every fact the roadmap's structure
depends on. Signs a claim is load-bearing: a phase ordering depends on it, an API
decision rests on it, or two agents disagree about it. Read the actual source or
run the actual command. Fold corrections back into the planning documents. It is
normal for this step to overturn an assumption the whole plan was about to rest
on; that is exactly why it exists.

### Step 4 - Record current state and open questions

Write (or update) two structured pieces, usually in the roadmap document:

- A **current-state summary**: the condensed matrix / inventory from the surveys,
  plus a short list of the key facts that shape the plan (each stated once,
  plainly, with a source reference).
- A **design-decisions section** split into *settled* (the working rules) and
  *open* (a table of numbered questions Q1..Qn, each with candidate options and
  the phase that owns it). As questions close, mark them DECIDED with the date and
  a pointer to the design note that resolved them; do not delete them.

### Step 5 - Write the phased roadmap

Order phases by dependency, not time. Phase 0 is usually design consolidation and
(if relevant) upstream/stakeholder alignment before significant build work. Each
subsequent phase should ship something independently useful.

Give **every phase** this structure:

```
### Phase N - <name>

Goal: one sentence, the property that becomes true when the phase is done.

Why this order / why this target first: the dependency and the rationale for the
lead target (lowest-friction proof, best existing precedent, best test rig).

Work items:
1. ... (numbered, concrete, each a reviewable unit)
2. ...

Targets: named hardware / environments / modules to work on and test against.

Tests: the specific checks that prove the goal, including the adversarial ones.

Exit criteria: the measurable conditions that let the next phase start.

Workflow shape: the dynamic-workflow decomposition - which agents, what model
each runs on, and the loop. Default coding tiering: implementation on sonnet,
test authoring/running on haiku, standard + adversarial review on opus, looped
(review findings -> implementer fixes -> re-test -> re-review) until reviews are
clean and tests pass.
```

Close the roadmap with an **upstream/rollout strategy**, a **risk register**
(each risk with its mitigation, often a specific test), and a **progress-tracking**
note stating: each phase writes its own `YYYYMMDD_<topic>.md` to the planning
folder; this roadmap is updated, not forked, as phases complete; and at the
entrance to each phase the workflow planner must revalidate that phase's tickets
against everything done since they were written (Step 5c) before executing.

Keep work items in the roadmap itself as one-line bullets; the full detail lives
in the per-item tickets (Step 5b).

### Step 5b - Expand work items into tickets while context is hot

Do this during planning, as part of producing the roadmap, not later: much of what
a future phase needs is already known from the upfront research, and the planning
session is the moment of peak knowledge. Detail not written down now is lost when
this context is gone. Turn every substantive work item, across all phases, into an
individual ticket file, e.g. `planning/tickets/<phaseN>_<slug>.md`, so the
implementation workflow planner (the `Workflow` script author, or the implementer
agents inside it) picks up a ticket and can plan immediately without re-researching
what this planning process already learned.

Expand only items a planner would otherwise have to research. Leave trivial,
self-evident items (a size measurement, a config flag flip) as inline bullets in
the phase; a ticket for them is noise.

Stamp every ticket with its date and the HEAD SHA at writing time, and pull the
rationale from the design notes written earlier. Tickets for later phases will go
stale as earlier phases change the tree; that is expected and safe, because the
stamp makes the drift deterministically computable at phase entry (Step 5c).

Ticket template:

```
# <component>: <imperative one-line title>

Phase: N
Depends on: <other tickets / phases / external prerequisites>
Written: <YYYY-MM-DD> at HEAD <short SHA>
Revalidated: <YYYY-MM-DD> at HEAD <short SHA> - <one line: what changed / "no drift">
  (append one line per revalidation; never overwrite the Written stamp)

## Context
Why this exists, in a few sentences. Link the design notes and research reports
that justify it ([[YYYYMMDD_<note>.md]]), and the closed open-questions (Qk) that
constrain the approach. Link upstream discussions/PRs if relevant.

## Scope
In scope: the exact change this ticket makes.
Out of scope: adjacent things explicitly deferred (and to which ticket/phase).

## Files and anchors
The concrete files and file:line references the implementer will touch or must
respect, captured now so the planner does not re-derive them. State the behaviour
at each anchor that matters.

## Design constraints
The settled rules and prior decisions that bind this item (cross-ref the context
doc's rules and the Qk decisions). Anything the implementer must not break.

## Approach sketch
Enough of the intended shape that the planner starts from a direction, not a blank
page. Not a full design - the workflow still owns detailed design - but the
non-obvious choices already made during planning are recorded here.

## Acceptance criteria and tests
The specific checks that prove the ticket is done, including the adversarial ones
and any hardware/environment needed. These become the test-agent's brief.

## Workflow shape
The model-tiered agent decomposition for this ticket (implementation on sonnet,
tests on haiku, standard + adversarial review on opus, looped), or a note that it
runs inside the phase's larger workflow.

## Open questions
Anything still genuinely undecided for this item, so the planner surfaces it rather
than guessing.
```

A well-written ticket is the unit a dynamic workflow consumes: its scope, anchors,
constraints, and acceptance criteria are exactly the brief the implementer and test
agents need, and its workflow shape is the decomposition the `Workflow` script
encodes.

### Step 5c - Revalidate tickets at phase entry

At the entrance to each phase, before authoring the phase's `Workflow` script, the
planning agent reviews each of that phase's tickets against all work and learnings
since the ticket was written. The stamps make this deterministic rather than a
judgement call:

1. **Code drift**: `git log --oneline <ticket SHA>..HEAD` for what landed since,
   and `git diff <ticket SHA>..HEAD -- <the ticket's anchored files>` for exactly
   how the ticket's anchors moved. Re-resolve every file:line reference against
   the current tree.
2. **Knowledge drift**: read planning-folder documents and design notes dated
   after the ticket's Written stamp (this is why every output carries a timestamp),
   plus any open questions (Qk) closed or reopened since, plus completed phases'
   progress reports and their learnings.
3. **Update the ticket in place**: refresh anchors, adjust scope/approach/tests to
   match reality, resolve or escalate anything the drift invalidated, then append
   a Revalidated stamp line (new date + new HEAD SHA + one line on what changed,
   or "no drift"). If the drift is large enough to change the ticket's shape
   entirely, that is a finding for the roadmap too - update the phase, don't
   silently rewrite the ticket.

Only revalidated tickets feed the workflow. A ticket whose latest Revalidated SHA
is not the current HEAD has not been revalidated.

### Step 5d - Make the plan self-describing

A future agent picking up the roadmap (new session, different machine, a plain
workflow subagent) will usually NOT have this skill file available. Everything
needed to action the roadmap and tickets must therefore live inside the planning
folder itself. Write an index / operating-instructions file at the top of the
planning folder (e.g. `planning/README.md` or `planning/00_index.md`) - not only
in a context doc like `CLAUDE.local.md`, which may be untracked and not travel
with the repo.

The index file must contain, deliberately duplicating this skill:

1. **Document map**: what each file in the folder is (roadmap, research reports,
   design notes, tickets) and the reading order for a fresh agent (index ->
   context/design rules -> roadmap -> the current phase -> its tickets).
2. **Conventions**: every document is stamped with date + HEAD SHA; tickets carry
   an immutable `Written:` stamp and an append-only `Revalidated:` history; the
   open-questions table uses Qk numbering with dated DECIDED entries that are
   never deleted; the roadmap is updated in place, never forked; each executed
   phase writes its progress and learnings back to the folder as
   `YYYYMMDD_<topic>.md`.
3. **The phase-entry procedure, verbatim**: before authoring a phase's workflow,
   revalidate each of its tickets - (a) `git log <ticket SHA>..HEAD` plus
   `git diff <ticket SHA>..HEAD -- <anchored files>` for code drift, re-resolving
   every file:line anchor; (b) planning documents dated after the ticket's stamp
   and any Qk changes for knowledge drift; (c) update the ticket in place and
   append a Revalidated stamp. Only tickets revalidated at current HEAD feed a
   workflow; drift big enough to reshape a ticket is a roadmap update, not a
   silent rewrite.
4. **The execution model**: each phase's revalidated tickets are the input to a
   dynamic multi-agent workflow; the coding model tiering (implementation on
   sonnet, test authoring/running on haiku, standard + adversarial review on
   opus, looped until reviews are clean and tests pass); a ticket's own
   Workflow-shape section overrides the default when present.
5. **The ticket template** (or a pointer to a well-formed existing ticket to
   copy).

Keep the index short and operational; it is a manual, not a report. Update it in
the same change whenever a convention changes, and have the context doc (e.g.
CLAUDE.local.md) point at it as the entry point.

### Step 6 - Incorporate new direction as it arrives

When the user adds a constraint, a decision, or firsthand knowledge:

- Update the living documents in place (roadmap, context doc, and any design
  note). Close the relevant open question with a dated DECIDED entry.
- If the input is a design decision big enough to need its own reasoning, write a
  dedicated design note `YYYYMMDD_<decision>.md` and reference it from the
  roadmap and the context doc.
- Verify any factual claim the new direction introduces (Step 3 discipline) before
  encoding it as settled.
- **Durably capture knowledge that exists nowhere else** (a maintainer's private
  preference, a verbal agreement, a bench gotcha) in the persistent memory, not
  only in the planning folder, since the planning folder may not survive a branch.

## The deliverable

A planning folder containing:

- an index / operating-instructions file (`README.md` or `00_index.md`) making
  the folder self-describing - document map, conventions, phase-entry
  revalidation procedure, execution model, ticket template - so an agent
  without access to this skill can action the roadmap (Step 5d),
- the roadmap document (phases, current-state, open questions, risks),
- the survey/research reports (one per dimension, timestamped, commit-anchored),
- design notes for each closed major decision,
- ticket files under `planning/tickets/` for the substantive work items of all
  phases, written upfront at peak knowledge, each stamped Written at a date +
  HEAD SHA,

plus a context/design-rules document that indexes them and states the settled
rules, and a persistent-memory entry for any non-recoverable knowledge.

Each phase in the roadmap is a ready input to the `Workflow` tool: its work items,
targets, tests, and model-tiered agent shape are what a dynamic workflow needs to
sequence it. When a phase runs, its tickets - revalidated at phase entry against
the deterministic drift since their stamps (Step 5c) - are the per-item briefs the
workflow's implementer and test agents consume, so they act rather than research.
