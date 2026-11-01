---
name: mpy-new-hw-project
description: Create a new MicroPython firmware project for custom hardware. Takes a hardware design (netlist, BOM, datasheets, or an interview with the user), scaffolds the project from andrewleech/mpy-app-template, retargets a seed board definition to the new board, and generates a hardware.py skeleton with unix mock tests. Covers the MicroPython ports with board definitions - stm32, rp2, esp32, mimxrt and samd. Use when the user wants a new MicroPython port, board definition, board profile or firmware project for their own PCB, or says "bring up MicroPython on my board".
---

# New MicroPython project for custom hardware

Turn a hardware design into a buildable MicroPython application project. The result is a repository scaffolded from `https://github.com/andrewleech/mpy-app-template` with a board definition in `src/system/<BOARD>/`, application hardware in `hardware.py`, and tests that run on the unix port with `mock_machine`.

Ports in scope: stm32, rp2, esp32, mimxrt, samd. The unix and windows ports have no board definitions. The generated project already runs on unix for its tests.

The skill carries no pin or chip tables. Pin names and alternate functions come from the MicroPython tree and from the user's design files and datasheets. If neither can confirm a fact, ask the user.

## Rules

- Work with the user. The inputs vary, so ask for what is missing, and convert formats the scripts do not read by reasoning. Read `references/input-intake.md` before the first question.
- Every fact carries a `source`: `script`, `user-confirmed` or `inferred`. Record each inferred decision as an open question in the report. Do not hide it.
- Never write a pin-number to port-name mapping that the gate has not passed, or that the user has not confirmed.
- Edit only `src/system/<BOARD>/` and the application files that `gen_hardware.py` owns. Leave the MicroPython submodule, the template's build files and the `mpconfigproj` include alone.
- Commit the scaffold before the retarget, so the retarget is one reviewable diff. Use `git` only in the new project.
- Flashing is out of scope. If asked later, reference probes by serial number and serial ports by `/dev/serial/by-id/<name>`.

## Files

Scripts need `uv`. Run them as `uv run <skill-dir>/scripts/<name>.py --help`.

| Path | Use |
|---|---|
| `references/input-intake.md` | what to collect from the user, how to convert unsupported inputs |
| `references/micropython-port-structure.md` | how to read the MicroPython port tree, find supported chips, choose a seed board |
| `references/app-template.md` | scaffold commands, what `initial_setup.py` does, make targets |
| `references/ports/<port>.md` | per-port board files, clock and power decisions, pin rules, constructor forms |
| `references/fact-schemas.md` | the JSON fact files |
| `references/hardware-skeleton.md` | what `gen_hardware.py` writes |
| `dimensions/*.md` | subagent prompts for each stage |
| `scripts/` | `preflight`, `parse_netlist`, `validate_facts`, `resolve_pinmap`, `pick_seed`, `gen_pins_csv`, `lint_board`, `gen_hardware` |

## Pipeline

The facts live in `<project>/hardware/facts/`. Model tiers: sonnet subagents generate, haiku subagents build and run tests, opus subagents review.

### 0. Preflight and intake

1. Run `scripts/preflight.py`. Missing tools limit scope: without docker or podman the build steps are skipped and the report says so.
2. Read `references/input-intake.md`. Ask the user for the design inputs and the project settings (name, URL, author, license, CI platform). Do not guess these.
3. Get a MicroPython checkout: the user's, or a shallow clone in a scratch directory. Read `references/micropython-port-structure.md` to see how the tree is laid out.

### 1. Facts

Dispatch the `dimensions/` prompts, sonnet each:

1. `extract-mcu`: part, package, port, series.
2. `resolve-pinmap`: package pin to port name, then `resolve_pinmap.py`. This is a hard gate: it prints a one-line summary on success and exits 1 on failure. Convert the netlist with `parse_netlist.py` where it supports the format, otherwise by reasoning (see the intake reference).
3. `classify-peripherals`: buses, devices, LEDs, buttons, analog and PWM pins into `peripherals.json`.
4. `derive-clock-power`: oscillators, flash and RAM sizes, USB, storage, power.

Run `validate_facts.py` after each. Read the facts back to the user and get confirmation before generating anything.

### 2. Seed board

Run `pick_seed.py --port <port> --mcu <part>` (use `--list` to see the port's boards). If the MCU is not in any port, the script exits 1: stop and tell the user which ports exist and which chips they cover. Show the ranked candidates with the reasons and confirm the choice. When several boards tie in the best tier the output has `tie: true` and lists their `features`; the script does not choose between them. Choose by the features of the design, with the user.

### 3. Scaffold

Follow `references/app-template.md`: write the answers file and run `mpy-new-project`. The scaffold makes the baseline commit and the `v0.0.1` tag itself; do not add a second commit. `make setup` is safe to re-run. On a cold machine the esp32 scaffold and its `make submodules` can take about 30 minutes because of the container image pull. Run them in the background.

### 4. Retarget

Check the exit code of every script: 0 is success, 1 is a finding or failure, 2 is a usage error. Do not read a script as passed because it printed output. Run `gen_pins_csv.py --pinmap hardware/facts/pinmap.json --port <port> -o src/system/<BOARD>/pins.csv`. Options:

- Self-named rows (board name equal to the pad name, for example `PB08,PB08`) are skipped on rp2, samd, mimxrt and esp32. On those ports every pad is addressable by its pad name, and a duplicate makes the build fail (`pin_<PAD> redefined`; on esp32 `pin_GPIO4` becomes a reference to itself). The rows stay on stm32, where only pads listed in `pins.csv` get a pin object. `--keep-self-named` keeps them on the ports that skip them. `pins.csv` is optional on esp32 and holds board names only: an integer GPIO with no board name needs no row.
- `--include-pad PAD[=NAME]` (repeatable) lists a pad that has an unnamed net, under `NAME` (default: the pad name). Use it when a macro in `mpconfigboard.h` names a pad that has no named net (stm32: `pin_B8` needs the pad in `pins.csv`). Do not add such lines by hand. It is ignored, with a warning, for a pad whose net is named.
- `--af-file <csv>` adds the pad names of the port's AF table as valid names. mimxrt needs it for pads that do not follow the `GPIO_` naming (`WAKEUP`). Give the same file as for `resolve_pinmap.py`.
- `--exclude NAME...` leaves named nets out.
- `--micropython <dir>` (also on `resolve_pinmap.py` and `lint_board.py`) lets esp32 check `GPIOn` against the pad limit in the port's `make-pins.py`. Without it no range is checked.

Then dispatch `generate-board-files` (sonnet) to edit the board definition from the facts, following `references/ports/<port>.md`. Run `lint_board.py` and fix every error. Warnings and `unchecked` items go to the report. Commit the retarget together with `hardware/facts/`.

### 5. Hardware skeleton

Run `gen_hardware.py` with `peripherals.json` and the board pins. It writes `device_config.py`, `hardware.py` and `test_hardware.py`. If a peripheral kind is not supported for the port, hand-write the construction in `hardware.py` following `references/hardware-skeleton.md`.

### 6. Verify

1. `lint_board.py` once more, then `validate_facts.py --stage all`.
2. Dispatch `verify-board-profile` (opus, adversarial). It checks every fact against the sources and the MicroPython tree. Fix findings, then re-run it until it reports none.
3. Dispatch a haiku subagent to run the builds: `make submodules && make system`, `make libs-only`, `make mboot` when stm32 uses mboot, `make tests`, `make checks`. Container image pulls are slow, esp32 in particular. Report build failures to the sonnet fixer with the log.

### 7. Report

Write `hardware/board-profile-report.md`: pins resolved and anchored, peripherals generated, clock and power decisions, lint warnings, what was not built or tested, and the open questions with the inferred decision for each. Tell the user what was and was not verified. Commit the retarget (with `hardware/facts/`) and the skeleton as separate commits.
