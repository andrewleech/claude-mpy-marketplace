---
name: mpbuild
description: Build MicroPython firmware using mpbuild instead of invoking make/cmake/idf.py directly. Use this whenever working inside a MicroPython repository (upstream or a fork) and the user wants to build, clean, or rebuild firmware for a board, or list available boards/ports. mpbuild runs builds in per-port Docker containers, so no local toolchain setup is required. Triggers on "build firmware for <BOARD>", "build micropython", "compile <BOARD>", "clean build", "rebuild", "what boards are available", or any board name mentioned alongside a build request (e.g. "build RPI_PICO", "build PYBV11").
---

# Building MicroPython firmware with mpbuild

Default to **mpbuild** for any MicroPython firmware build, instead of calling `make`, `idf.py`,
`cmake`, or port-specific build scripts directly. mpbuild picks the correct Docker container for
the target port/board automatically, so the host needs no toolchains installed — only Docker.

## Prerequisites

- **mpbuild** installed on the system. Preferred: `uv tool install mpbuild`. `pipx install mpbuild`
  or plain `pip install mpbuild` also work.
  - Check with `mpbuild --version` (or `mpbuild -v`). If the command isn't found, install it before
    attempting a build.
- **Docker** installed, running, and reachable by the current user (`docker ps` should succeed).
  mpbuild pulls/builds the appropriate per-port image on first use of that port.
- Must be run from **the root of a MicroPython repository** (upstream `micropython/micropython` or
  a fork with the same `ports/`, `boards/` layout). mpbuild discovers boards by scanning that tree —
  it will find nothing useful if run elsewhere.

If any prerequisite is missing, tell the user what's missing rather than falling back to a manual
`make` invocation.

## Core commands

```bash
mpbuild build BOARD [VARIANT] [-- EXTRA_ARGS...]   # build a board, optional variant
mpbuild clean BOARD [VARIANT]                      # remove build artifacts
mpbuild rebuild BOARD [VARIANT] [-- EXTRA_ARGS...]  # clean, then build
mpbuild list [PORT]                                # list boards, optionally filtered by port
mpbuild check_boards [--verbose]                    # validate board.json files and referenced images
```

- `BOARD` is the board name as it appears under `ports/<port>/boards/` (e.g. `RPI_PICO`, `PYBV11`,
  `ESP32_GENERIC_S3`). Special non-microcontroller "boards" also work: `unix`, `webassembly`,
  `windows`.
- `VARIANT` is optional and board-specific (e.g. `RISCV`, `FLASH_16M`). Run `mpbuild list <port>` to
  see which boards have variants.
- Anything after the board/variant on `build`/`rebuild` is passed straight through to `make` inside
  the container — useful for things like `-j`, `USER_C_MODULES=...`, or a specific `make` target.
- `--build-container TEXT` (on `build`/`rebuild`) overrides the default container image for that
  board, if the user needs to test against a different toolchain image.

## Other useful modes

- **Interactive TUI**: `mpbuild --interactive` (or `-i`). Lets you browse ports/boards in a tree and
  trigger build/rebuild/clean without typing board names. Offer this only if the user is exploring
  interactively at a terminal — it's not useful for a one-shot scripted build.
- **Tab completion**: `mpbuild --install-completion` sets up shell completion (bash/zsh/fish/
  PowerShell) for commands, board names, and variants. Suggest this once, not on every build.

## Examples

```bash
# Build the Raspberry Pi Pico
mpbuild build RPI_PICO

# Build the RISC-V variant of the Pico 2
mpbuild build RPI_PICO2 RISCV

# Rebuild from scratch, passing -j8 to make
mpbuild rebuild RPI_PICO -- -j8

# See what's available on the rp2 port
mpbuild list rp2

# Clean a board's build directory
mpbuild clean PYBV11
```

## Notes

- First build of a given port downloads its Docker image, which can take a while — this is
  expected, not a hang.
- `unix`, `webassembly`, and `windows` are valid `BOARD` values but don't target a microcontroller —
  see the MicroPython docs if the user needs specifics on what they produce.
- If a board name doesn't match anything, run `mpbuild list` (optionally scoped to a port) to show
  valid names rather than guessing.
