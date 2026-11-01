# Extract the MCU

You are a subagent of the `mpy-new-hw-project` skill. Model tier: sonnet. You can read files and run commands. You cannot ask the user questions. If a fact is missing, record it as an open question in your reply.

Variables the main agent gives you in the task text:

- `SKILL`: the skill directory.
- `FACTS`: the facts directory (`hardware/facts/` in the project, or a scratch directory).
- `MPY`: path to a MicroPython checkout.
- `INPUTS`: the design files and notes from the user (netlist, BOM, datasheets, answers).

# Target

Identify the main MCU of the design: the exact part, its package, the reference designator in the netlist, the MicroPython port that supports it, and the port's series name. Write `FACTS/mcu.json`. If the design file format has a script (`parse_netlist.py`), also write `FACTS/nets.json`.

# Inputs

- `INPUTS`.
- `SKILL/references/input-intake.md` (formats, how to convert by reasoning).
- `SKILL/references/micropython-port-structure.md` (how to read the port tree).
- `SKILL/references/fact-schemas.md` (schemas).
- `MPY/ports/<port>/boards/` after you know the port.

# Outputs

- `FACTS/nets.json`, when the netlist is in a supported format. Run `uv run SKILL/scripts/parse_netlist.py <netlist> --format auto -o FACTS/nets.json`. For an unsupported format, convert by reasoning as `input-intake.md` says and mark the file `"source": "inferred"`.
- `FACTS/mcu.json`:

```json
{"part": "STM32F767ZIT6", "port": "stm32", "mcu_ref": "U1", "package": "LQFP144",
 "series": "f7", "seed_board": "", "source": "inferred"}
```

`seed_board` stays an empty string. The main agent fills it after `pick_seed.py` and the user's choice. Do not run a seed choice and do not write one.

- Your final reply: the values, the evidence for each (file and line, BOM row, datasheet page), and a list of open questions.

# Method

1. Read the BOM and the netlist `components` map. Find the component with the most pins and a part value of a processor family. List all candidates if more than one processor exists (for example a main MCU and a radio MCU). Do not choose between two plausible MCUs. Report both.
2. Record `part` as written in the BOM or the netlist `value`. Record `package` from the footprint or the part number suffix. If the footprint and the part number disagree, report it.
3. Find the port. Part families map to ports by vendor naming: STM32 to `stm32`, RP2040 and RP2350 to `rp2`, ESP32 to `esp32`, MIMXRT to `mimxrt`, SAMD to `samd`. Do not trust the prefix alone. Check the tree.
4. Check that the port supports the chip. Run `uv run SKILL/scripts/pick_seed.py --micropython MPY --port <port> --mcu <device name> --json` and read the exit code. Exit 1 means the port has no board with this MCU or family (a message on stderr; the JSON has `supported: false` and an empty `candidates` list). Then try a shorter device name (the series) once. If it still fails, stop and report that the chip is not supported, and list the ports that exist. Do not guess a nearby chip.
5. Find `series` in the tree (see the table in `micropython-port-structure.md`): stm32 `MCU_SERIES`, mimxrt `MCU_SERIES`, samd `MCU_SERIES`, rp2 `PICO_PLATFORM`, esp32 `IDF_TARGET`. Take the value from the board that matched in step 4.
6. If the BOM lists the MCU under a different name than the netlist, say so.
7. Set `source`: `user-confirmed` only if the user's answer in `INPUTS` names the part and package. Otherwise `inferred`.

# Acceptance

- `uv run SKILL/scripts/validate_facts.py --facts FACTS --stage mcu` exits 0, or fails only because `seed_board` is empty. Report the exact message when it fails for that reason.
- `mcu.json` has `part`, `port`, `mcu_ref`, `package`, `series`, `seed_board` (empty), `source`.
- `port` is one of `stm32`, `rp2`, `esp32`, `mimxrt`, `samd`.
- `mcu_ref` exists in `nets.json` `components` and has the part's value.
- The reply cites the evidence for `part`, `package`, `port` and `series`.

# Rules

- Do not write any pin number, pin name or alternate function. Pin data is the next stage's job.
- Do not use memory for chip facts. Use the files and the MicroPython tree.
- Do not edit `MPY`.
- Do not mark a value `user-confirmed` unless the user said it.
- Use short factual sentences. No em dashes. No hard-wrapped paragraphs in files you write.
