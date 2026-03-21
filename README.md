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

**Slash command:** `/pr-triage [feedback|newest|oldest]`

**Skill trigger:** Ask about open PRs, PR triage, which PRs need attention, etc.

## Adding New Plugins

1. Create `plugins/<name>/.claude-plugin/plugin.json`
2. Add skills under `plugins/<name>/skills/<skill-name>/SKILL.md`
3. Add commands under `plugins/<name>/commands/<command-name>.md`
4. Register in `.claude-plugin/marketplace.json`
5. Run `./install.sh --enable-all` or manually add to enabledPlugins
