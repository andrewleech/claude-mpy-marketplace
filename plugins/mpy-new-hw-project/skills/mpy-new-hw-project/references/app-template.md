# App template

The template is `https://github.com/andrewleech/mpy-app-template`, a Copier template. A local checkout can sit at `/home/corona/mpy-app-template`. It creates a MicroPython application project: the MicroPython and library submodules, a board definition copied from MicroPython, a frozen application, unit tests that run on the unix port, containerised builds and CI configuration.

Jinja delimiters in the template are `[[ ]]` and `[% %]`. The template carries its own `AGENTS.md` (`CLAUDE.md` is a symlink to it). Read the generated project's `AGENTS.md` before you change build files.

## Scaffold

Always run the template through `mpy-new-project`. It reads the port and board lists from MicroPython and hands them to Copier. Running `copier` directly leaves the lists empty and the `target_port` validator stops with the correct command.

Git form (normal use):

```bash
uvx --from git+https://github.com/andrewleech/mpy-app-template mpy-new-project --data-file <answers.yml> <dest>
```

Local development form:

```bash
uvx --no-cache --from <template-checkout> mpy-new-project --src <template-checkout> --vcs-ref HEAD --data-file <answers.yml> <dest>
```

`--no-cache` is needed. uv reuses a wheel it built from a local path and does not notice edits to the source. A new commit or a dirty tree does not change that. Installing from git is not affected.

Other options: `--defaults` (take defaults for unanswered questions), `--update` (re-apply the template to an existing project), `--vcs-ref` (template ref, default `main`).

The scaffold needs network access (git clones), `git`, `uv`, `make` and `docker` or `podman` (the rp2 and esp32 `make submodules` step runs in the build container). Run `preflight.py` first. On a cold machine the container image pull dominates: the esp32 scaffold and its `make submodules` can take about 30 minutes. Run them in the background and wait for the result.

### Answers file

`<answers.yml>` holds the answers. Keys that start with `_` are ignored by `mpy-new-project`. Example for stm32 with mboot:

```yaml
project_name: AcmeSensor
project_url: https://github.com/acme/acme-sensor.git
author: Acme Ltd
license: MIT

target_port: stm32
template_board: NUCLEO_F767ZI
project_board_name: ACMESENSOR_NUCLEO_F767ZI

use_mboot: true
bootloader_address: '0x08000000'

ci_platform: github
```

| Key | Meaning |
|---|---|
| `project_name` | no spaces. Used in paths and device identification. Upper-cased, it is the board-name prefix. |
| `project_url` | git remote URL, added as `origin` |
| `author` | copyright holder for headers and LICENSE |
| `license` | `MIT`, `Apache-2.0`, `BSD-3-Clause` or `none` |
| `target_port` | `stm32`, `rp2`, `esp32`, `mimxrt`, `samd` (and others the template offers) |
| `template_board` | the seed board. It must exist in `ports/<port>/boards/` of the cloned MicroPython. |
| `project_board_name` | name of the project's copy of the board, upper case. Default: `<PROJECT_NAME_UPPER>_<template_board>`. This becomes `BOARD` and the directory `src/system/<project_board_name>/`. |
| `use_mboot` | stm32 only. Build the app for the mboot bootloader and add `make mboot`. |
| `bootloader_address` | stm32 and `use_mboot` only. Flash address of mboot (default `0x08000000`). It sets `MBOOT_TEXT0_ADDR` and the version footer position. |
| `ci_platform` | `github`, `gitlab` or `both` |

The test answers in `/home/corona/mpy-app-template/test/*.copier-answers.yml` show one file per variant (`esp32`, `rp2`, `stm32-mboot`, `stm32-no-mboot`, `unix`).

The questions `use_mboot` and `bootloader_address` exist for stm32 only. Do not set them for other ports. Regular mboot only: signing and encryption are not supported.

The `project_board_name` can be a better name than the default (for example the product name), but keep it upper case, free of spaces and unique among the project's boards.

## What `tools/initial_setup.py` does

Copier runs it as the post-generation task. `make setup` runs it again. It re-executes itself under `uv run --with mpbuild --with pyyaml` when those imports are missing.

Order (the order matters):

1. `init_repository`: `git init -b main` and add `origin`, only when there is no `.git`.
2. `add_submodules`: `git submodule add -f --depth 1` for `src/micropython`, `src/libs/micropython-lib`, `src/libs/micropython_unittest_junit` and `src/libs/micropython-mock-machine`. Existing entries in `.gitmodules` are skipped.
3. `add_board_files`: copy `src/micropython/ports/<port>/boards/<template_board>/` to `src/system/<project_board_name>/`.
   - The seed `manifest.py` is copied as `manifest_base.py`. The project `manifest.py` gets `include("manifest_base.py")` appended.
   - A file that already exists in the destination is not overwritten.
   - The copy is skipped when `src/system/<project_board_name>/mpconfigboard.h` already exists, so edits to the board directory survive a re-run.
   - `mpconfigboard.mk` (stm32, mimxrt, samd) gets `include $(BOARD_DIR)/../mpconfigproj.mk` appended. `mpconfigboard.cmake` (rp2, esp32) gets `include(${MICROPY_BOARD_DIR}/../mpconfigproj.cmake)`. The marker `mpconfigproj` prevents a second append.
   - `mpconfigboard.h`: the first `#define MICROPY_HW_BOARD_NAME "..."` becomes `"<PROJECT_NAME_UPPER>-..."`. A name that already has the prefix is left alone.
   - USB vendor and product IDs are not changed.
4. `resolve_build_containers`: ask `mpbuild` for the build container of the seed board. The image names are written into `src/system/build_containers.mk`, `.devcontainer.json`, `.github/workflows/ci.yml` and `.gitlab-ci.yml`. For esp32 the IDF version comes from `ports/esp32/lockfiles` in the submodule, so the answer holds only for the checked-out commit.
5. `make submodules`: check out the submodules and fetch the port dependencies. It needs the board directory to exist, and on rp2 and esp32 it runs in the build container.
6. `install_typings`: `micropython-<port>-stubs` into `tools/typings`.
7. `write_license`.
8. `pre-commit run --all-files` (normalises formatting) and `pre-commit install`.
9. `create_initial_commit`: commit with the message `Create <project_name> from mpy-app-template` and tag `v0.0.1`, only when the repository has no history. The script supplies a committer identity from the answers when git has none.

Re-run safety: `make setup` is safe to repeat. The retargeted board directory, the `mpconfigproj` include and the board-name prefix stay. Run it after a MicroPython submodule bump so the recorded build containers match the checked-out tree. If the project's board directory is deleted, the next run copies the seed again.

If `template_board` does not exist in the cloned tree, the script prints the available boards and exits 1. Fix `template_board` in `.copier-answers.yml` and run `make setup`.

## Commit baseline

The scaffold ends with the initial commit (message `Create <project_name> from mpy-app-template`) and the tag `v0.0.1`. Keep it as the baseline and do not add a second baseline commit. Make the retarget changes (with `hardware/facts/`) as the next commit, and the hardware skeleton as a separate commit after that. The retarget diff against the baseline is then the full set of board changes, and the user can review it as one unit.

If the scaffold did not create the initial commit (the repository already had history), commit the scaffold output yourself before you edit anything. Do not commit the retarget with the scaffold.

Commit only inside the new project. Commit messages: short, imperative, factual, no AI attribution.

## Project layout

```text
src/micropython/                   MicroPython submodule
src/libs/                          micropython-lib, unittest junit, mock machine
src/system/<BOARD>/                board definition (the retarget stage edits this)
src/system/Makefile                project make wrapper (do not edit)
src/system/mpconfigproj.{mk,cmake} project-wide build settings (do not edit)
src/system/build_containers.mk     container image names
src/firmware/application/          main.py, boot.py, device.py, hardware.py, device_config.py, version.py
src/firmware/test/                 unit tests (frozen on the unix port only)
src/unix/                          unix port build, simulation/machine.py
src/manifest.py                    manifest root
tools/                             initial_setup.py, typings
hardware/                          facts and report (added by this skill)
```

`src/system/Makefile` finds the board directory in `src/system/<BOARD>/` first and in the upstream tree second. The marker file is `mpconfigboard.mk` or, for rp2 and esp32, `mpconfigboard.cmake`.

## Make targets

Run from the project root. Builds run in the toolchain container unless the shell is already in one (`/.dockerenv` exists) or `RUN_IN_DOCKER=0` is set.

| Target | Action |
|---|---|
| `make submodules` | check out submodules and fetch port dependencies (guarded by a stamp file) |
| `make mpy-cross` | build the cross compiler |
| `make system` | build firmware with the application frozen in |
| `make libs-only` | build with the libraries only (`EXCLUDE_APP=1`) |
| `make mboot` | stm32 with `use_mboot`: build the bootloader. `make bootloader` is an alias. |
| `make deploy-dfu` | stm32 with `use_mboot`: flash the application. Flashing is out of scope for this skill. |
| `make unix-port` | build the unix port |
| `make tests` | unit tests on the unix port, all modules. `make tests test=test_hardware` runs one module. |
| `make run-unix`, `make repl-unix` | run the application or a REPL on unix with the mock hardware |
| `make checks` | `pre-commit run --all-files`: ruff, mypy, yamllint (runs on the host, needs `uv`) |
| `make lint`, `make format` | ruff only |
| `make typings` | install type stubs into `tools/typings` |
| `make setup` | re-run `initial_setup.py` |
| `make clean` | delete build output |
| `make template-update` | re-apply the template with copier |

Firmware output lands in `src/system/build-<BOARD>/`. Build verification for this skill: `make submodules && make system`, `make libs-only`, `make mboot` (stm32 with mboot), `make tests`, `make checks`. Image pulls are large for esp32.

To run one test module, use `make tests test=test_hardware`. The value is forwarded into the container.

The generated Makefile exports `MICROPY_MPYCROSS` so the cmake ports use the project's `mpy-cross` and not their own sub-make. It also exports `MICROPY_GIT_TAG` and `MICROPY_GIT_HASH` from `git describe`. Do not change those lines.

## Where hardware lives

`src/firmware/application/hardware.py` is the only module that constructs peripherals (`Pin`, `I2C`, `SPI`, `UART`, `ADC`, `PWM`). `device_config.py` holds the constants it uses. `device.py` runs the tasks. Keep it that way: it is what lets the unix port swap the hardware.

On the unix port, `src/unix/simulation/machine.py` replaces `machine`. It re-exports `mock_machine` and wraps `SPI` so the constructor takes the same arguments as the hardware ports. The mock comes from the `src/libs/micropython-mock-machine` submodule and is frozen into the unix build only.

## Testing with `mock_machine`

`mock_machine` implements `Pin`, `I2C`, `SPI`, `UART`, `ADC`, `PWM`, `Timer`, `WDT`, `RTC`, plus `I2CDevice`, `RegisterBasedI2CDevice` and `Signal`. Docs: the `README.md` and `docs/` of the submodule.

- `Pin("NAME", Pin.OUT)` creates or returns a pin by id. `pin.value()` reads and sets.
- `Pin.board.configure("<path to pins.csv>")` loads board pin names. After that `Pin.board.<NAME>` returns the port pin name, and `Pin.cpu.<NAME>` is the identity map. An unknown name raises, so the call makes board names strict.
- `I2C(id)` has `scan`, `readfrom`, `writeto`, `readfrom_mem`, `writeto_mem` and `add_device`. `I2CDevice(addr=0x68, i2c=i2c)` simulates a device. Its `register_values` dict holds register contents.
- `SPI(id)` records `write_buf` and returns `read_buf`.
- Tests run in `src/unix/build/frozen_mpy`, so a relative path to the board's `pins.csv` is `../../../../src/system/<BOARD>/pins.csv`.
- The mock models the interface, not the electrical behaviour. Anything that needs real peripheral behaviour belongs in an on-target test.

## Generated tooling files that matter to this skill

- `pyproject.toml`: ruff and mypy configuration. Line length is 99. Check it before you write Python.
- `.pre-commit-config.yaml`: the hooks that `make checks` runs.
- `src/firmware/test/test_blink.py`: tests `Blinky`. It is removed when the hardware has no LED.
- `.copier-answers.yml`: the answers used. Edit `template_board` here and run `make setup` to retry a failed scaffold.
