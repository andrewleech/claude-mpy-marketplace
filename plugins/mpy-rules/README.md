# mpy-rules

MicroPython rules, a multi-agent review skill and a documentation style guide. The canonical rule files are `rules/*.md`; every agent reads that one copy.

## How the rules arrive

| Agent | How rules arrive | What you must do | Limits |
|---|---|---|---|
| Claude Code | SessionStart hook (`hooks/hooks.json` runs `scripts/setup-rules.sh`). In a MicroPython repo it copies the rules to `~/.claude/mpy-rules/`, symlinks them into `.claude/rules/`, installs the pre-push hook and ignores `.claude/` locally. `architecture.md` and `documentation.md` load only for files matching their `paths:`. | Nothing. | Claude Code 2.1.311 did not load `.claude/rules/` symlinks that point outside the project in a test run (`claude -p`); the `mpy-rules` skill covers that case. |
| Codex | The same SessionStart hook. On Codex the script writes no files. In a MicroPython repo it prints `core.md` and an index (path, scope, description) of the other rule files to stdout, which Codex adds to the model context. The model reads the other files on demand. | Trust the hook once, see below. Without trust the hook does not run and only the `mpy-rules` skill remains. | Hook output is capped near 2,500 tokens by default, so only `core.md` is inlined. The pre-push hook is not installed from a Codex session. Path scopes are advice in the index text, not enforced. |
| omp | `hooks/pre/mpy-rules.ts` (omp ignores `hooks.json`). On the first prompt of a session in a MicroPython repo it injects `core.md`. All rule files also carry `description:` and `globs:` frontmatter, so omp lists them and the model reads them with `rule://<name>`. | Restart omp after installing the plugin. | The rule list shows in every project, not only MicroPython repos. Globs are advice, not enforced. The injected text is a session message and can be summarised away by compaction. The pre-push hook is not installed from omp. |
| All | Skill `mpy-rules` (`skills/mpy-rules/SKILL.md`). It tells the model to check for a MicroPython repo and read the rule files by path. | Nothing. | The model must choose to invoke the skill. |

A MicroPython repo is a directory that contains `py/mpconfig.h`, `py/runtime.h` or `mpy-cross/main.c`. The check uses the session working directory, so start the agent at the repo root.

## Trust the hook on Codex

Codex skips plugin hooks until you trust them. Either route works once; the trust stays valid across plugin version updates while `hooks/hooks.json` is unchanged.

1. Interactive: start `codex`, run `/hooks`, select the `mpy-rules` SessionStart hook and trust it.
2. Config file: add this to `~/.codex/config.toml` (or `$CODEX_HOME/config.toml`):

```toml
[hooks.state."mpy-rules@mpy-marketplace:hooks/hooks.json:session_start:0:0"]
trusted_hash = "sha256:43ae4f0c8d80a16c1295972876c7e9057ec6f559c8a375fb60c1910bcad0ccfc"
```

The hash is the `currentHash` that `hooks/list` reports for the hook. If Codex shows the hook as untrusted after you add it, read the current value from `/hooks` or from the app-server `hooks/list` response and replace the hash.

`codex exec` skips untrusted hooks without a message. For a one-off headless run, `codex exec --dangerously-bypass-hook-trust` runs them.

## Plugin root in skills

Codex and omp do not substitute `${CLAUDE_PLUGIN_ROOT}` in skill text. The skills use paths relative to their own `SKILL.md` (`../../rules/`) and state that the plugin root is two directories above it.
