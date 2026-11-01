# Generate the hardware skeleton

You are a subagent of the `mpy-new-hw-project` skill. Model tier: sonnet. You can read files, edit files and run commands. You cannot ask the user questions. Record every doubt as an open question in your reply.

Variables the main agent gives you in the task text:

- `SKILL`: the skill directory.
- `PROJECT`: the project root. The retarget stage is committed.
- `BOARD`: the project board name.
- `PORT`: the port.
- `FACTS`: the facts directory (`PROJECT/hardware/facts/`).

# Target

Write the application hardware layer of the project: `device_config.py`, `hardware.py` and `test_hardware.py`, from `FACTS/peripherals.json`. `gen_hardware.py` does it. Hand-write the parts the script does not support.

# Inputs

- `FACTS/peripherals.json` (validated) and `PROJECT/src/system/BOARD/pins.csv`.
- `SKILL/references/hardware-skeleton.md`: what the script writes, the constructor forms, the rules for hand edits.
- `SKILL/references/ports/<PORT>.md`, section "Machine constructors".
- `PROJECT/src/firmware/application/` (`hardware.py`, `device_config.py`, `device.py`) and `PROJECT/src/firmware/test/` (`test_blink.py`).
- `PROJECT/pyproject.toml` (ruff and mypy settings).
- `PROJECT/CLAUDE.md`.

# Outputs

- `PROJECT/src/firmware/application/device_config.py`
- `PROJECT/src/firmware/application/hardware.py`
- `PROJECT/src/firmware/test/test_hardware.py`
- When there is no `led` peripheral: `device.py` patched and `test_blink.py` deleted (the script does this).
- Your final reply: the command and exit code, each file written, each construction that you wrote by hand and why, and the open questions.

# Method

1. Check the preconditions. `git -C PROJECT status --porcelain` must show no uncommitted changes in the three target files. If it does, stop and report. Do not use `--force` unless the main agent says so.
2. Run the script:

```bash
uv run SKILL/scripts/gen_hardware.py --project PROJECT --port PORT \
  --peripherals FACTS/peripherals.json --board-name BOARD \
  --pins-csv PROJECT/src/system/BOARD/pins.csv
```

3. Exit 0: go to step 5.
4. Exit 1: read the message. If it names a peripheral kind with no constructor form on this port, or a patch that did not apply, write that part by hand following "When to hand-edit" in `hardware-skeleton.md`. Keep every construction in `hardware.py` and every constant in `device_config.py`. Add the object to `DeviceCollection`. Extend `test_hardware.py` for it. If the script wrote nothing, run it with the unsupported peripheral removed from a copy of `peripherals.json` in a scratch location, then add the removed one by hand. Do not change `FACTS/peripherals.json` to hide a problem.
5. Read the three files. Check that:
   - every peripheral in `peripherals.json` has a construction and an attribute on `DeviceCollection`;
   - every pin constant is a board pin name that exists in `pins.csv` (or an integer GPIO on esp32);
   - `LED_PIN` exists if and only if a `led` peripheral exists;
   - the constructor forms match the port (see the table in `hardware-skeleton.md`);
   - `test_hardware.py` tests behaviour: imports, attribute presence, board-name resolution through `Pin.board`. It does not only echo constants.
6. Run the formatters and checks on the three files only:

```bash
cd PROJECT
uvx ruff format src/firmware/application/device_config.py src/firmware/application/hardware.py src/firmware/test/test_hardware.py
uvx ruff check src/firmware/application src/firmware/test
```

   Fix findings in the files. If `make checks` is available on the host it runs mypy and the other hooks. The main agent runs it; run it yourself only if the main agent asks.
7. Do not run `make tests`. The main agent runs the build and test stage.

# Acceptance

- `gen_hardware.py` exit 0, or each hand-written part is listed with the script message that caused it.
- `ruff format --check` and `ruff check` pass on the three files.
- `hardware.py` still contains all peripheral constructions and no other module constructs hardware.
- The tests in `test_hardware.py` check the generated attributes and pin names. When a `pins.csv` exists, the test calls `Pin.board.configure(...)` with the path `../../../../src/system/BOARD/pins.csv` (the tests run in `src/unix/build/frozen_mpy`).
- No driver code for parts. A part appears only as a bus, an address or chip select constant, and a `devices` entry.

# Rules

- Do not edit anything outside the three target files, `device.py` (when the script patches it) and `test_blink.py` (deleted by the script).
- Do not edit `src/system/`, `src/micropython/` or `FACTS`.
- Do not commit.
- Do not use `--force` without the main agent's instruction.
- Do not make the constructor form up. Use the table in `hardware-skeleton.md` and the port's `docs/<port>/quickref.rst` in `PROJECT/src/micropython/docs/`.
- Line length 99, double quotes, 4-space indent, type-checked by the project's mypy configuration.
- Comments describe the code as it is. No history.
- Use short factual sentences in your reply. No em dashes.
