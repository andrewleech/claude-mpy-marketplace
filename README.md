# MicroPython Claude Marketplace

Claude Code plugins for MicroPython development workflows.

## Installation

```bash
# Register marketplace and enable all plugins
./install.sh --enable-all

# Or just register (enable plugins individually later)
./install.sh
```

Restart Claude Code after installation. Edits to plugin files take effect on next session -- no reinstall needed.

## Uninstall

```bash
./uninstall.sh
```

## Plugins

### mpy-pr-triage

List, sort, and triage open MicroPython PRs with branch and worktree status.

**Slash command:** `/mpy-pr-triage [feedback|newest|oldest]`

**Skill trigger:** Ask about open PRs, PR triage, which PRs need attention, etc.

### mpy-ci

Run the MicroPython CI pipeline locally in Docker. Covers all 18 port build/test targets and 8 code quality checks.

**Skill trigger:** Ask to run CI, test changes, build firmware, run linters, etc.

See [plugins/mpy-ci/README.md](plugins/mpy-ci/README.md) for target list and usage.

### mpy-pr-maintenance

Systematic workflow for maintaining open MicroPython PRs. Processes PRs oldest to newest through reconnaissance, user discussion, rebase/fix in worktree subprocesses, local CI validation, and force-push. Supports batch processing of PRs without reviewer feedback.

**Skill trigger:** Ask about PR maintenance, PR backlog, rebasing PRs, working through open PRs.

**Depends on:** mpy-pr-triage, mpy-ci

## Adding New Plugins

1. Create `plugins/<name>/.claude-plugin/plugin.json`
2. Add skills under `plugins/<name>/skills/<skill-name>/SKILL.md`
3. Add commands under `plugins/<name>/commands/<command-name>.md`
4. Register in `.claude-plugin/marketplace.json`
5. Run `./install.sh --enable-all` or manually add to enabledPlugins
