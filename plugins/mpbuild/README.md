# mpbuild

Claude Code plugin for building MicroPython firmware with [mpbuild](https://github.com/micropython/mpbuild).

## Skills

### mpbuild

Build, clean, and rebuild MicroPython firmware for any board via `mpbuild`, which runs each build in
the correct per-port Docker container — no local toolchain install required. Covers `build`, `clean`,
`rebuild`, `list`, and `check_boards`, plus the interactive TUI and extra `make` args passthrough.

## Installation

```bash
claude plugin install mpbuild@mpy-marketplace
```

## Prerequisites

- `mpbuild` installed (`uv tool install mpbuild`, or `pipx install mpbuild` / `pip install mpbuild`)
- Docker installed and running
- Run from the root of a MicroPython repository (upstream or a fork with the standard `ports/`/`boards/` layout)
