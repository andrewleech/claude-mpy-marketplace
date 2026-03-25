# MicroPython Claude Marketplace

Claude Code plugins for MicroPython development workflows.

## Installation

```bash
claude plugin add https://github.com/andrewleech/claude-mpy-marketplace
```

Restart Claude Code after installation.

## Developer Installation

For local development with live source updates:

```bash
git clone https://github.com/andrewleech/claude-mpy-marketplace.git
cd claude-mpy-marketplace

# Register marketplace and enable all plugins
./install.sh --enable-all

# Or just register (enable plugins individually later)
./install.sh

# Uninstall
./uninstall.sh
```

Edits to plugin files take effect on next session -- no reinstall needed.

## Plugins

### mpy-rules

Automatically loads MicroPython build, style, PR, and architecture guidelines into `.claude/rules/` for any MicroPython repo. Installs via a session-start hook so rules are available without manual setup.

**Rules provided:** core build/test conventions, architecture overview, PR workflow

### mpy-ci

Run the MicroPython CI pipeline locally in Docker. Covers all 18 port build/test targets and 8 code quality checks.

**Skill trigger:** Ask to run CI, test changes, build firmware, run linters, etc.

See [plugins/mpy-ci/README.md](plugins/mpy-ci/README.md) for target list and usage.

### mpy-pr-triage

List, sort, and triage personal open MicroPython PRs with branch and worktree status.

**Slash command:** `/mpy-pr-triage [feedback|newest|oldest]`

**Skill trigger:** Ask about open PRs, PR triage, which PRs need attention, etc.

### mpy-pr-maintenance

Systematic workflow for maintaining personal open MicroPython PRs. Processes PRs oldest to newest through reconnaissance, user discussion, rebase/fix in worktree subprocesses, local CI validation, and force-push. Supports batch processing of PRs without reviewer feedback.

**Skill trigger:** Ask about PR maintenance, PR backlog, rebasing PRs, working through open PRs.

**Depends on:** mpy-pr-triage, mpy-ci

### mpy-reviewer *(external)*

MicroPython code review assistant backed by categorized review comments from upstream. Provides RAG-based review guidance and an MCP server for querying the review database.

**Source:** [andrewleech/mpy-reviewer](https://github.com/andrewleech/mpy-reviewer)

**Skill trigger:** Ask for code review feedback on MicroPython changes.

## Adding New Plugins

1. Create `plugins/<name>/.claude-plugin/plugin.json`
2. Add skills under `plugins/<name>/skills/<skill-name>/SKILL.md`
3. Add commands under `plugins/<name>/commands/<command-name>.md`
4. Register in `.claude-plugin/marketplace.json`
5. Run `./install.sh --enable-all` or manually add to enabledPlugins
