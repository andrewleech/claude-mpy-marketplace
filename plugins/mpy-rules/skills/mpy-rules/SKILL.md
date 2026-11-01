---
name: mpy-rules
description: Use when working in a MicroPython repo (py/mpconfig.h exists): build, test, format, commit, docs and PR rules. Read before building, editing code or docs, committing, or drafting a PR.
---

Apply the MicroPython project rules to work in a MicroPython checkout.

## Check the repository

```bash
test -f py/mpconfig.h || test -f py/runtime.h || test -f mpy-cross/main.c
```

If none exists, this is not a MicroPython repository. Stop and do not apply these rules.

## Rule files

The rule files are in `../../rules/`, relative to the directory of this SKILL.md. Plugin root: use `${CLAUDE_PLUGIN_ROOT}` if it is an absolute path; otherwise the plugin root is two directories above the directory of this SKILL.md (`<plugin root>/skills/mpy-rules/SKILL.md`).

Read `core.md` in full first. Then read each file below in full before you touch the paths it covers.

| File | Covers |
|---|---|
| `../../rules/core.md` | Building, running tests, formatting, commit messages, code style. Always. |
| `../../rules/development-patterns.md` | Correctness, resource and portability pitfalls. Before writing or reviewing code. |
| `../../rules/architecture.md` | `py/`, `extmod/`, `ports/`, `lib/`, `shared/`. |
| `../../rules/documentation.md` | `docs/**/*.rst`. |
| `../../rules/pr-workflow.md` | PR descriptions, commit history, private review workflow, `gh` usage. |

Apply the rules to the task. The rules can be loaded already (Claude Code `.claude/rules/`, the Codex SessionStart hook, the omp rule list); in that case read only the files not yet in context.
