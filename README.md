# MicroPython Agents Marketplace

Plugins for MicroPython development workflows, for coding agents: Claude Code, oh-my-pi (omp) and Codex.

## Installation

All three agents read the `.claude-plugin/marketplace.json` catalog in this repository, so one marketplace serves all of them. The marketplace name is `mpy-marketplace`.

### Claude Code

```bash
claude plugin marketplace add https://github.com/andrewleech/claude-mpy-marketplace
claude plugin install mpy-new-hw-project@mpy-marketplace
```

Install other plugins the same way, for example `claude plugin install mpremote@mpy-marketplace`. Restart Claude Code after installation.

### oh-my-pi (omp)

```bash
omp plugin marketplace add andrewleech/claude-mpy-marketplace
omp plugin install mpy-new-hw-project@mpy-marketplace
```

Install other plugins the same way, for example `omp plugin install mpremote@mpy-marketplace`. Add `--scope project` to install into the current project (`.omp/plugins`) instead of the user directory.

Inside the omp TUI the equivalents are `/marketplace add andrewleech/claude-mpy-marketplace` and `/marketplace install mpy-new-hw-project@mpy-marketplace`. Run `/reload-plugins` after installing.

Update with `omp plugin marketplace update` and `omp plugin upgrade <plugin>@mpy-marketplace`.

### Codex

```bash
codex plugin marketplace add andrewleech/claude-mpy-marketplace
codex plugin add mpy-new-hw-project@mpy-marketplace
```

Install other plugins the same way, for example `codex plugin add mpremote@mpy-marketplace`. List the available and installed plugins with `codex plugin list`. Codex installs a copy of each plugin into `~/.codex/plugins/cache/`. Start a new Codex session after installing.

Update with `codex plugin marketplace upgrade mpy-marketplace`, then `codex plugin add` again for each installed plugin.

Codex loads the plugin skills, and turns plugin slash commands into skills. Some plugins use Claude Code hooks or `${CLAUDE_PLUGIN_ROOT}` paths, which may not work in Codex or omp.

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

Edits to plugin files take effect on next session, no reinstall needed.

`install.sh` and `uninstall.sh` are for Claude Code only. omp and Codex install a cached copy of each plugin, so edits are not live. Add the local clone as a marketplace, then reinstall after each edit:

```bash
# oh-my-pi
omp plugin marketplace add ~/claude-mpy-marketplace
omp plugin install --force mpy-new-hw-project@mpy-marketplace

# Codex
codex plugin marketplace add ~/claude-mpy-marketplace
codex plugin add mpy-new-hw-project@mpy-marketplace
```

In omp run `/reload-plugins` after reinstalling. In Codex start a new session.

## Agent support

All plugins install on Claude Code, omp and Codex. Skills load on all three. Slash commands are `/<command>` on Claude Code, `/<plugin>:<command>` on omp, and skills named `source-command-<command>` on Codex.

| Plugin | Notes |
|---|---|
| mpy-rules | Rules arrive by a SessionStart hook on Claude Code and Codex (Codex needs a one-time hook trust), and by an extension on omp. A skill covers the case where the hook does not run. See [plugins/mpy-rules/README.md](plugins/mpy-rules/README.md). |
| mpy-ci, mpy-pr-triage | Run their bundled scripts on Codex and omp, found relative to the skill. |
| mpy-pr-maintenance | Launches a subprocess agent. The skill offers Claude Code, omp and Codex launch forms and defaults to the agent that is running it. |
| mpy-new-hw-project, mpremote, draft-pr, agentic-app-development | Skills only, no agent-specific paths. |

## Plugins

### mpy-rules

Loads MicroPython build, style, PR, and architecture guidelines for any MicroPython repo, on Claude Code, Codex and omp. A session-start hook (an extension on omp) delivers them without manual setup.

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

### agentic-app-development

Planning-workspace structure and upstream-patch tracking for ongoing agentic
development: where process material lives relative to the shipped repo, three
git postures for that workspace, scaling structure to the size of the work,
and tracking local patches against a vendored/forked dependency until they
land upstream. Vendors `phased-roadmap` as the option for large or
long-running planning.

**Skill trigger:** Setting up a planning workspace, organising process
material for an ongoing project, tracking patches against a vendored or
forked dependency, deciding whether planning material needs its own git repo.

**Works with:** `draft-pr` (owns the local-draft-file frontmatter this plugin
points at), `investigation-log` (referenced for exploratory phase work, not
bundled).

### mpremote

MicroPython device interaction via mpremote. Three skills covering device connection and management, file transfer, and persistent PTY sessions for asyncio-safe command execution.

**Skill triggers:** Ask about connecting to a device, copying files, running code on a device, monitoring output, persistent sessions.

### mpy-new-hw-project

Create a new MicroPython firmware project for custom hardware. The agent takes a hardware design (KiCad or Protel/Altium netlist, BOM, pin table, datasheets, or an interview with the user), scaffolds the project from [mpy-app-template](https://github.com/andrewleech/mpy-app-template), retargets a seed board definition from the MicroPython tree to the new board, and generates a `hardware.py` skeleton with tests that run on the unix port using [micropython-mock-machine](https://github.com/planetinnovation/micropython-mock-machine).

Covers the MicroPython ports with board definitions: stm32, rp2, esp32, mimxrt and samd. The plugin carries no pin tables. Pin names and alternate functions come from the MicroPython tree and from the design files and datasheets the user supplies. A deterministic gate checks the package pin to port name mapping against the netlist before any board file is written.

**Slash command:** `/mpy-new-hw-project [design files or description]`

**Skill trigger:** Ask to bring up MicroPython on a custom board, create a board definition or firmware project for a PCB, or generate a board profile from a netlist.

**Needs:** `uv`, `git`, `make`, and docker or podman for firmware builds.

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
