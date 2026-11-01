# Generate the board files

You are a subagent of the `mpy-new-hw-project` skill. Model tier: sonnet. You can read files, edit files and run commands. You cannot ask the user questions. Record every doubt as an open question in your reply.

Variables the main agent gives you in the task text:

- `SKILL`: the skill directory.
- `PROJECT`: the project root (scaffolded, with the baseline commit made).
- `BOARD`: the project board name (`project_board_name`). The board directory is `PROJECT/src/system/BOARD/`.
- `PORT`: the port.
- `FACTS`: the facts directory (`PROJECT/hardware/facts/`).

# Target

Edit the copy of the seed board definition in `PROJECT/src/system/BOARD/` so that it describes the new hardware. The copy was made by `initial_setup.py` from the seed board in `src/micropython/ports/PORT/boards/`. The build must find a consistent board: chip, linker files, clocks, pins, peripherals and storage must agree with the facts.

# Inputs

- `FACTS/mcu.json`, `pinmap.json`, `peripherals.json`, `clock-power.md`.
- `PROJECT/src/system/BOARD/pins.csv`, written by `gen_pins_csv.py` before you start. Do not rewrite it, add lines to it or rename its entries. If it is missing or wrong, stop and report. On stm32 every pad named by a macro in `mpconfigboard.h` must be listed; if a pad that your macros name has no line, report the pad. The main agent adds it with `gen_pins_csv.py --include-pad <PAD>` and runs the script again. On rp2, samd and mimxrt, rows whose board name equals the pad name are left out on purpose; do not add them.
- `SKILL/references/ports/<PORT>.md`, which lists what to edit in each file, the rules for each variable or macro, and the pin checks. Follow it.
- `SKILL/references/micropython-port-structure.md` (what each board file does).
- `SKILL/references/app-template.md` (what `initial_setup.py` added).
- The MicroPython tree at `PROJECT/src/micropython/` (read-only), for the AF data, the linker scripts and the other boards of the port as examples.
- Template answers: `PROJECT/.copier-answers.yml` (`use_mboot`, `bootloader_address` for stm32).

# Outputs

- Edits to files in `PROJECT/src/system/BOARD/` only.
- Your final reply, containing:
  1. A change log. One line per edited setting: file, variable or macro, old value, new value, the fact that justifies it (file and row in `FACTS`).
  2. The lint result: the command, the exit code, and every warning and `unchecked` entry.
  3. The list of seed settings you left unchanged on purpose, with the reason.
  4. The open questions: every setting you could not take from a fact and the value you chose.

# Boundaries

The edits are confined to `PROJECT/src/system/BOARD/`. Before you finish, run `git -C PROJECT status --porcelain` and `git -C PROJECT diff --stat`. Every changed or new path must start with `src/system/BOARD/`. The one exception is the facts directory `hardware/`, which the main agent owns. If another path changed, revert a tracked file you edited by mistake with `git checkout -- <path>`, and say so.

Do not edit:

- `PROJECT/src/micropython/` and any other submodule;
- `PROJECT/src/system/Makefile`, `mpconfigproj.mk`, `mpconfigproj.cmake`, `build_containers.mk`;
- `PROJECT/src/system/BOARD/manifest.py` (the project manifest that includes `manifest_base.py`);
- the mboot footer files `mboot_footer.c` and `mboot_footer.ld` (stm32 with mboot);
- anything under `PROJECT/src/firmware/` or `PROJECT/hardware/`.

Keep two lines that `initial_setup.py` added. They must still be present when you finish:

- the project build include at the end of `mpconfigboard.mk` (`include $(BOARD_DIR)/../mpconfigproj.mk`) or `mpconfigboard.cmake` (`include(${MICROPY_BOARD_DIR}/../mpconfigproj.cmake)`). The marker is the text `mpconfigproj`.
- the board-name prefix in `mpconfigboard.h`: the first `#define MICROPY_HW_BOARD_NAME` string starts with `<PROJECT_NAME_UPPER>-`. You may change the part after the prefix.

# Method

1. Read `SKILL/references/ports/<PORT>.md`. Read every file in `src/system/BOARD/`.
2. Build a work list from the port reference: for each file and each variable or macro listed there, decide keep, change, remove or add. Take each decision from a fact. Where the facts give no value, keep the seed value only if it is a property of the chip family. Remove it if it is a property of the seed hardware. List it as an open question when you are not sure.
3. Edit `board.json`: `mcu`, `product`, `vendor`, `url`, `features`. Set `images`, `thumbnail`, `deploy` to values that exist in the project, or to empty values. Do not claim the seed vendor's name or URL.
4. Edit the build file (`mpconfigboard.mk` or `mpconfigboard.cmake`): chip identifiers, linker files, flash layout, memory, features. For stm32 with `use_mboot: true`, apply the mboot layout rules of `ports/stm32.md`.
5. Edit `mpconfigboard.h`: board name, MCU name, clocks, bus pins, LEDs, buttons, USB, storage, network. Remove every group that names hardware the new board does not have. Remove USB vendor and product IDs that belong to the seed's vendor.
6. Port-specific files: stm32 `stm32*_hal_conf.h` and `board_init.c`; rp2 variant files and the pico-sdk board header; esp32 `sdkconfig.board`; mimxrt IOMUX and index tables; samd linker files and default bus ids. The port reference lists them. mimxrt: build `MICROPY_HW_UART_INDEX`, `MICROPY_HW_SPI_INDEX` and `MICROPY_HW_I2C_INDEX` and the IOMUX tables so that each `bus_id` in `peripherals.json` is the position of its hardware instance in the index table (see `ports/mimxrt.md`: UART position 0 is a `0` placeholder, so `UART(1)` is the first UART; I2C and SPI start at position 0). Check the remaining seed entries (CTS/RTS, other buses) for pads that the design uses for another function. Keep the CAN macros (see `ports/mimxrt.md`).
7. Delete variant files and `board.json` `variants` entries that the hardware does not need. Ask in the reply when you are not sure.
8. Check that every pin name used in a macro (`pin_B8`, `GPIO3`, `IOMUXC_...`) exists for the chip in the AF data of `PROJECT/src/micropython`, and that each bus pin pair matches the bus id in `peripherals.json`.
9. Run the lint:

```bash
uv run SKILL/scripts/lint_board.py --micropython PROJECT/src/micropython --port PORT \
  --board-dir PROJECT/src/system/BOARD --peripherals FACTS/peripherals.json
```

   Exit 1 means errors. Fix every error and run it again. Read the warnings. Copy the warnings and the `unchecked` entries into the reply.
10. Run the boundary check from the section above.

# Acceptance

- `lint_board.py` exits 0.
- `git status --porcelain` shows changes only under `src/system/BOARD/` (and the main agent's `hardware/`).
- The `mpconfigproj` include line and the board-name prefix are present.
- No file in the board directory still names the seed board, the seed vendor's pins, parts or USB IDs, except settings you listed as left unchanged on purpose.
- Every changed setting is in the change log with its fact.
- No build was run. The main agent runs the builds.

# Rules

- Do not commit.
- Do not use memory for chip or pin facts. Use the facts, the datasheet text in `INPUTS`, and the MicroPython tree.
- Do not invent clock, flash or memory values. When a value is missing, stop at that setting and list it.
- Do not use `sed`, `perl` or Python scripts to edit. Use the edit tool.
- Keep the style of the seed files (indent, comment style, macro alignment).
- Comments in the files describe the board as it is now. Do not write comments about what the seed had or what you changed.
- Use short factual sentences in your reply. No em dashes.
