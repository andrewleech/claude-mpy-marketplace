# agentic-app-development

Claude Code plugin for running agentic development on an ongoing project:
where process material lives relative to the shipped repo, how much planning
structure a piece of work actually needs, and how to track local patches
carried against a vendored or forked dependency until they land upstream.

Generalised from a real project's `./planning/` workspace and its `mbm.toml`
submodule-patch registry after several sessions of use.

## Skills

### agentic-app-development

The core pattern: the two-document-homes split (shipped `docs/` vs. a planning
workspace the product repo never carries), three git postures for that
workspace (untracked scratch dir, a separate local repo excluded from the
product repo's history, or that repo pushed to its own remote), scaling
planning structure to the size of the work, making the workspace
self-describing, and tracking patches against a vendored/forked dependency: one
integration branch per dependency composed from named upstreamable feature
branches, a registry file, local PR drafts, and raising those drafts against
your own fork first.

### phased-roadmap

Vendored as the heavyweight option this plugin escalates to for large or
long-running planning: fanned-out research written to timestamped reports,
a living roadmap with numbered facts/rules/open-questions, dependency-ordered
phases with exit criteria, and work items expanded into self-contained
tickets, stamped and revalidated for drift at phase entry.

## Works with

- **draft-pr** (this marketplace) - drafts PR titles and descriptions, and
  owns the frontmatter schema for persisting a draft as a local file before
  it's ready to raise. This plugin only says where those files live and the
  fork-first raising discipline; the schema itself lives in `draft-pr`.
- **investigation-log** - for exploratory or investigative work within a
  phase, where the path matters as much as the result. Referenced, not
  vendored; activate it on a working branch and distil before merge.

## Installation

```bash
claude --plugin-dir ~/claude-mpy-marketplace/plugins/agentic-app-development
```

Or add to your Claude Code settings.
