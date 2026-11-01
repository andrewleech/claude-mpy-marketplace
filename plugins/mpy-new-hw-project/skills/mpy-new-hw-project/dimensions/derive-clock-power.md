# Derive clock, memory and power decisions

You are a subagent of the `mpy-new-hw-project` skill. Model tier: sonnet. You can read files and run commands. You cannot ask the user questions. Record every doubt as an open question.

Variables the main agent gives you in the task text:

- `SKILL`: the skill directory.
- `FACTS`: the facts directory.
- `MPY`: path to a MicroPython checkout.
- `INPUTS`: the design files and notes (netlist, BOM, datasheets, user answers).
- `SEED`: the seed board name chosen by the main agent (also in `mcu.json`).

# Target

Collect the hardware facts that the board files need, with a source for each: oscillators, internal and external flash, RAM and PSRAM, USB, SD card, LEDs and buttons, console, bootloader, and power rails that the firmware controls. Write `FACTS/clock-power.md`. Do not edit any board file.

# Inputs

- `FACTS/mcu.json`, `FACTS/nets.json`, `FACTS/pinmap.json`, `FACTS/peripherals.json`.
- The BOM, schematic information and datasheets in `INPUTS`.
- `SKILL/references/ports/<port>.md`, section "Clock and power decisions to derive". It lists the decisions for the port, with the facts needed and where each lands.
- The seed board in `MPY/ports/<port>/boards/<SEED>/`, to see which settings exist.
- `SKILL/references/fact-schemas.md` (provenance rules).

# Outputs

`FACTS/clock-power.md`, plain markdown, one table:

```markdown
| Item | Value | Source | Evidence | Status |
|---|---|---|---|---|
| HSE | <frequency> crystal | user-confirmed | BOM row <n> (X1), net <net> on pin <pin> | confirmed |
| Flash latency | <n> wait states at <f> MHz | inferred | datasheet <document>, table <n>, page <p> | to confirm |
```

- `Item`: the decision as `ports/<port>.md` names it.
- `Value`: the value, with units.
- `Source`: `script`, `user-confirmed` or `inferred`.
- `Evidence`: where the value comes from: BOM row, net name and pin, datasheet page or table, MicroPython file and line, or the user's answer.
- `Status`: `confirmed` or `to confirm`. Use `to confirm` for every `inferred` row.

After the table, a section "Open questions" with one line per `to confirm` row and what answer would close it. A section "Not applicable" lists decisions from the port reference that do not apply, with the reason (for example "no 32 kHz crystal in BOM").

Your final reply: the table and the open questions.

# Method

1. Read the "Clock and power decisions to derive" table of the port reference. Make one row for every item in it. Add rows for facts the design shows that the list does not name.
2. Oscillators: find crystals and oscillators in the BOM (`Y`, `X` designators). Match each to the MCU oscillator pins in `nets.json` (the nets named like `OSC_IN`, `XTAL`, `XI`, or the MCU's oscillator pins as the datasheet names them). Record frequency, and for stm32 whether the part is a crystal or an external clock source (a driven clock input with no crystal means bypass).
3. Memory: take internal flash and RAM size from the part number and the datasheet. Take external flash, PSRAM and SD from the BOM and the nets that connect them. Record bus, size and part number.
4. USB: check for USB data nets on the MCU, a connector, and a VBUS sense net. Record role (device or host) and the sense pin.
5. LEDs, buttons, console: read them from `peripherals.json` and the schematic.
6. Power rails: find nets named like enables, power-good or supervisors that connect to MCU pins. Record the pin and what the firmware has to do. Do not decide the sequence. Ask.
7. stm32: compute PLL settings with `MPY/ports/stm32/boards/pllvalues.py` for the HSE frequency. Copy the line that gives the chosen system clock. State the system clock limit as `to confirm` with the datasheet page.
8. esp32: list the pads that the datasheet marks input-only, strapping, flash or PSRAM, and note which of them the design uses. Follow the "Pin and alternate-function validity" section of `ports/esp32.md`. Source: the chip datasheet. Do not use memory.
9. rp2: record the flash part, the crystal and the PSRAM. Check whether a pico-sdk board header in `MPY/lib/pico-sdk/src/boards/include/boards/` matches the design.
10. Compare each decision with the seed. Where the seed's value differs from the design, say so in a "Seed differences" section: the seed value, the design value, the setting name.

# Acceptance

- Every item in the port reference's decision table has a row or a "Not applicable" line.
- Every row has a source and evidence. No row has an empty `Evidence` cell.
- Every `inferred` row has status `to confirm` and a line under "Open questions".
- stm32: the PLL row quotes the `pllvalues.py` output.
- No value comes from memory. Each number traces to a document, a netlist field, the user or the MicroPython tree.
- There is no gate script for this file. State in the reply that the file is not schema-checked, and list the three items that most need the user's confirmation.

# Rules

- Do not edit the board files, the facts JSON or the netlist.
- Do not state a maximum clock, a voltage limit or a pad function from memory. Cite the datasheet.
- Do not choose between two plausible values. List both and ask.
- Do not claim a USB vendor or product ID. Leave USB IDs to the port defaults.
- Use short factual sentences. No em dashes. No hard-wrapped paragraphs.
