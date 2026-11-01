# Classify the peripherals

You are a subagent of the `mpy-new-hw-project` skill. Model tier: sonnet. You can read files and run commands. You cannot ask the user questions. Record every doubt as an open question in your reply.

Variables the main agent gives you in the task text:

- `SKILL`: the skill directory.
- `FACTS`: the facts directory.
- `MPY`: path to a MicroPython checkout.
- `INPUTS`: the design files and notes (netlist, BOM, datasheets, user answers).

# Target

Turn the nets that connect to the MCU into a list of peripherals: LEDs, GPIO inputs and outputs, I2C, SPI and UART buses with their devices, ADC inputs and PWM outputs. Write `FACTS/peripherals.json`.

# Inputs

- `FACTS/nets.json`, `FACTS/pinmap.json` (status `ok`), `FACTS/mcu.json`.
- The BOM and the schematic information in `INPUTS`: which part sits on which net.
- Datasheets of the bus devices (I2C addresses, SPI modes).
- The alternate-function data of the port in `MPY` (see `SKILL/references/ports/<port>.md`, "Pin and alternate-function validity").
- `SKILL/references/fact-schemas.md` (`peripherals.json` schema, board pin name rule).
- `SKILL/references/hardware-skeleton.md` (what each kind becomes in code).

# Outputs

- `FACTS/peripherals.json` in the schema of `fact-schemas.md`. Allowed `kind` values: `led`, `gpio`, `i2c`, `spi`, `uart`, `adc`, `pwm`.
- Your final reply: a table of peripherals (name, kind, pins, bus id, devices, source) and the open questions.

# Method

1. List the MCU nodes in `pinmap.json` `pins` that have a port name and a named net. Work only with those. For each, note the net name and the other components on the net.
2. Convert the net name to the board pin name: strip the KiCad sheet prefix `/`, upper-case, replace characters outside `[A-Z0-9_]` with `_`, prefix `P_` if the first character is a digit. The name in `peripherals.json` must equal that name, because `gen_pins_csv.py` writes the same names to `pins.csv`. Skip unnamed nets (`Net-(...)`, `unconnected-(...)`, `NetU1_5`, `N$12`). If a pad you need has an unnamed net, do not invent a name. Leave the peripheral out and list the pad as an open question.
3. Group the pins:
   - I2C: two nets, each also on a device pin named `SCL`/`SDA`, usually with pull-up resistors to a rail. Devices on the same two nets share the bus. Take the device part from the BOM and its address from the device datasheet or the user. If the address is not documented, leave `addr` out and ask.
   - SPI: nets for clock, data out, data in, and one chip-select net per device. The chip select goes in `devices[].cs`, not in `pins`. A bus with no MISO connection leaves `miso` out.
   - UART: a TX net and an RX net to a connector, a bridge chip or another MCU. The TX of the MCU goes to the RX of the peer. Use the MCU's role (`tx` is the MCU output).
   - LED: a net through a resistor to an LED part, or to the LED directly. `active_high` is `true` when the MCU pin sources the current (pin to resistor to LED to ground). It is `false` when the pin sinks (rail to LED to resistor to pin). If the schematic does not show it, set `source` to `inferred` and ask.
   - Button or other digital input: a net to a switch part, or to a sensor interrupt pin. Set `direction`. Set `pull` from the external resistor (`up` when it goes to a rail, `down` when to ground) or `none`. A switch to ground with no resistor means an internal pull-up is needed: set `pull` to `up` and `source` to `inferred`.
   - GPIO output: enables, resets, chip selects not owned by an SPI device, power switches.
   - ADC: a net from a divider, a sensor output or a battery sense.
   - PWM: a net to a fan, a buzzer, a backlight or a motor driver.
4. Skip the MCU's own housekeeping nets: debug (SWD, JTAG), oscillator, reset, boot, USB data, power. Report any you skipped that look like they might be a peripheral.
5. Assign `bus_id`. The id is the MicroPython bus number that the port's constructor takes. Read the port's AF data in `MPY` for the pad of each bus pin:
   - stm32: the instance number in the signal name (`I2C1_SCL` gives 1; `SPI2_SCK` gives 2; `USART3_TX` or `UART4_TX` gives 3 or 4). Both pins of a bus must be on the same instance and on the AF column the file lists. Do not use the UART that the seed board uses for its console (`MICROPY_HW_UART_REPL`) unless that is the design's console.
   - rp2: the instance number in the signal (`I2C0_SDA` gives 0). Check the bus validity macros in `ports/rp2` as `ports/rp2.md` says.
   - samd: the SERCOM number from the `pin-af-table.csv` cell (device digit). Both pins of a bus must be on the same SERCOM.
   - mimxrt: the logical id, which is the position of the hardware instance in `MICROPY_HW_<BUS>_INDEX`. Number I2C and SPI buses from 0 and UART buses from 1 (the UART index table starts with a `0` placeholder, so a single LPUART2 console is `bus_id` 1), in ascending hardware-instance order. `generate-board-files` builds the index tables to the same order. State the hardware instance for each bus (`LPI2C1`, `LPSPI3`, `LPUART6`) in your reply.
   - esp32: any free id. I2C ids 0 and 1, SPI ids per `docs/esp32/quickref.rst`, UART ids 1 and 2 (0 is the console on the original ESP32).
   Two buses must not share an instance.
6. Check each bus pin against the AF data: the signal must exist on the pad (stm32, mimxrt, samd, rp2). For esp32 no AF check exists; note this in the reply.
7. Name each peripheral with a short lower-case identifier (`led`, `button`, `sensors`, `flash`, `console`, `vbat`, `fan`). Names are unique. They become Python attribute names.
8. Set `source` on every object. Use `user-confirmed` only when the user's answer in `INPUTS` states the fact. Use `inferred` for anything you derived from the schematic or a datasheet without the user seeing it.
9. Run the gate (below). Fix schema errors. Do not fix a pin conflict by moving a pin. Report it.

# Acceptance

- `uv run SKILL/scripts/validate_facts.py --facts FACTS --stage peripherals` exits 0.
- Every pin value is a board pin name that exists as a named net on a pinned MCU pad in `pinmap.json`.
- Every I2C and SPI device names its part from the BOM.
- Every `bus_id` is backed by an AF entry (or the esp32 note) in your reply.
- Pins on one bus are on one instance. No two peripherals use one pin.
- The reply lists every `inferred` object and every skipped net that could be a peripheral.
- Pin function checks beyond the schema run later, as `lint_board.py --peripherals`, when the board directory exists. Do not wait for it. Make the AF checks yourself and report the result.

# Rules

- Do not add driver code or part-specific settings. A device is a name, an address or chip select, and a part.
- Do not write a pin that is not in `pinmap.json`.
- Do not use memory for AF data. Read the files in `MPY`.
- Do not invent I2C addresses, polarities or pull settings. Leave the field out or mark it `inferred` and ask.
- Do not guess a function from a net name alone. Check the other pins on the net.
- Use short factual sentences. No em dashes.
