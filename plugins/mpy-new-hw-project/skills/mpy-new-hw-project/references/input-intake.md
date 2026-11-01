# Input intake

The agent talks to the user to get the design inputs. The scripts read a few formats. For every other format, the agent reads the input and converts it by reasoning into the fact files. Every converted row is marked `source: inferred` until the user confirms it.

Ask only for what is missing. Read what the user already gave before the first question.

## Required facts

Collect these before any generation. A fact is closed when it has a value and a source.

| Fact | Why | Typical source |
|---|---|---|
| MCU part number (full orderable name) | picks the port, series, AF table, linker script | BOM, schematic, user |
| MCU package and pin count | package pin to port pin name mapping | footprint, part number, datasheet |
| MCU reference designator in the netlist | selects the right component | netlist, schematic |
| Port (`stm32`, `rp2`, `esp32`, `mimxrt`, `samd`) | selects the board family | part number |
| Netlist or a pin table | package pin to net | netlist, datasheet pin table |
| Package pin to port pin name table | the pin gate | netlist `pinfunction`, datasheet pin table |
| Main crystal or oscillator (frequency, or none) | clock tree | BOM, schematic |
| 32.768 kHz crystal (present or not) | RTC source | BOM, schematic |
| External flash or PSRAM (type, size, bus) | storage and memory settings | BOM |
| Internal flash and RAM size of this part | linker script, filesystem size | datasheet, part number |
| Debug, programming and console connection | REPL and flashing path | schematic, user |
| USB (device, host, none) and which pins | USB macros | schematic |
| Buses with devices: I2C, SPI, UART (pins, devices, addresses) | `peripherals.json` | schematic, BOM |
| LEDs and buttons (pin, polarity, pull) | board macros, `LED_PIN` | schematic |
| Analog inputs and PWM outputs (pin, purpose) | `peripherals.json` | schematic |
| Power rails that firmware must control (enable pins, supervisors) | board init code | schematic, user |
| SD card or other storage | storage macros | schematic |
| Radio or network (WiFi, BLE, Ethernet PHY, modem) | build features | BOM |
| Bootloader (stm32 only: use mboot or not) | `use_mboot`, `bootloader_address` | user |
| Project settings: name, git URL, author, licence, CI platform | template answers | user |
| MicroPython version or checkout path | tree to read | user |

Do not guess project settings or the MCU part. Ask.

## Questions

Ask in this order. Skip a question when an input already answers it.

1. Which files or documents describe the hardware? Accept a netlist, BOM, pin table, datasheet (PDF or text), photos or text of the schematic, or a description.
2. What is the exact MCU part number, and which package? If the BOM and the user disagree, ask which one is right.
3. Which designator is the MCU in the netlist?
4. Is there a pin table (package pin to port pin name)? If not, can you supply the MCU datasheet pin-definition table? Without one, the netlist must carry pin function names.
5. Which crystals and oscillators are fitted: main clock frequency and type (crystal, external clock, none), and a 32.768 kHz crystal?
6. What external memory is fitted (QSPI or SPI flash, PSRAM, SD)? Sizes and part numbers.
7. How does the device connect to a host: USB (which role), a debug UART, a USB serial bridge?
8. List each bus and the parts on it: I2C (addresses), SPI (chip selects), UART (what is connected).
9. List LEDs and buttons with their pins, and say which level turns an LED on and which level means a button is pressed.
10. Which pins are analog inputs or PWM outputs, and what do they measure or drive?
11. Which rails does the firmware control, and how?
12. For stm32: do you want the mboot bootloader? At which flash address will the bootloader sit?
13. Project name, git remote URL, author, licence (MIT, Apache-2.0, BSD-3-Clause, none), CI platform (github, gitlab, both).
14. Which MicroPython checkout or version should be used?

Ask for one thing at a time when the user answers short. Group related questions when the user answers in full sentences.

## Accepted inputs

| Input | Handling |
|---|---|
| KiCad `.net` (s-expression netlist) | `parse_netlist.py FILE --format kicad`. Carries `pinfunction`. |
| Protel or Altium `.net` | `parse_netlist.py FILE --format protel`. Carries no pin function. |
| CSV `ref,pin,net[,pinfunction]` | `parse_netlist.py FILE --format csv`. |
| BOM CSV | read by the agent: find the MCU row, crystals, memories, connectors, sensors. Not parsed by a script. |
| Pin table CSV `package_pin,port_name` | passed to `resolve_pinmap.py --pin-table`. |
| Datasheet PDF or text | read by the agent. Extract the pin-definition table for the package, and the memory and clock facts. |
| Free text from the user | convert to facts by asking follow-up questions. |
| Netlist formats not listed (Eagle, OrCAD, EDIF, Allegro, KiCad XML, PADS, a schematic PDF) | convert by reasoning, see below. |

Use `uv run <skill-dir>/scripts/parse_netlist.py --help` for the exact options. Use `--format auto` when the extension is not enough.

## Converting unsupported formats

1. Read the input completely. For a long file, read the MCU component and every net that touches it. Do not skip nets that touch the MCU.
2. Produce `nets.json` in the schema from `fact-schemas.md`. Keep net names exactly as in the source. Use `pinfunction: null` when the source has none.
3. Mark the file as converted by reasoning: add `"source": "inferred"` at the top level and on each node object you wrote. A file written by `parse_netlist.py` needs no such mark.
4. Check the conversion against the source with counts: number of components, number of nets, number of nodes on the MCU. Say the counts to the user. Re-read two or three nets from the source and from `nets.json` side by side.
5. Do not repair, merge or rename nets. If the source has an obvious mistake, report it and ask the user.
6. Do not invent a pin function from a net name. A net name that looks like `PA3` is an anchor for the gate. It is not a pin function.

## Building the pin table

The pin table CSV has the header `package_pin,port_name`. The `port_name` is the name the port uses: `PA3` (stm32, samd), `GPIO3` (rp2, esp32), `GPIO_AD_B0_03` (mimxrt).

Sources, in order of preference:

1. The netlist `pinfunction` field (KiCad): `resolve_pinmap.py --from-pinfunction` reads the first token that matches the port's name pattern. No hand table needed.
2. The pin-definition table of the MCU datasheet for the exact package. Copy the package pin and the port pin name only. A table for another package of the same chip is not valid.
3. A pin table the user supplies.
4. Reasoning from a pinout in text or an image. This is the weakest source. Treat it as unconfirmed.

A table built from a datasheet or by reasoning is not a script output. Mark it as `inferred` in `mcu.json` notes and in the report until the user confirms it.

## Read back and confirm

Before any generation, write a short understanding and ask the user to confirm or correct it:

- the MCU, package, port, designator;
- the clock, memory and power decisions with their source;
- each peripheral with its pins and parts;
- every row marked `inferred`, one line each;
- the open questions.

Use a plain list. Do not continue until the user answers. Record the answer by changing `source` from `inferred` to `user-confirmed` for each confirmed item. Never change `source` for an item the user did not confirm.

## Pin gate rules for derived data

The pin gate is `resolve_pinmap.py`. It compares the package-pin table against anchors: nets whose name equals a port pin name on that same MCU pin. It fails on any disagreement, duplicate package pin, duplicate port name, name that is invalid for the port, or fewer than `--min-anchors` (default 3) anchors.

When the pin table is a script output (KiCad `pinfunction`) or the netlist has enough anchors, run the gate without `--confirmed`.

When the table comes from reasoning (a datasheet table read by the agent, a converted netlist without `pinfunction`, a pinout image) the gate is a weaker check:

1. Show the user the full table. Ask for explicit confirmation of the whole table, not of single rows.
2. Only after the user confirms, run with `--confirmed`. The flag records that the user confirmed the table. It does not replace the anchor check: mismatching anchors still fail.
3. Record the confirmation in `mcu.json` with `"source": "user-confirmed"`.
4. If the user does not confirm, stop. Do not run `--confirmed` to get past a failed gate.
5. If anchors disagree with the table, do not edit either side to make them agree. Report both and ask which is right.

Never write a mapping from a pin number to a port name that the gate did not pass and that the user did not confirm.

## Things to ask the user when the design is silent

- Net names that look like pin names but sit on a different pad than the table says.
- Pins shared between a function and a strap (boot mode, flash voltage, PSRAM).
- Two LEDs or buttons with similar names.
- A bus with no devices listed.
- A crystal marked "DNP" or alternative parts in the BOM.
- USB pins with no VBUS sense net.
