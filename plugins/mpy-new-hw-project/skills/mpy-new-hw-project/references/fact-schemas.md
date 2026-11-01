# Fact files

The facts live in `<project>/hardware/facts/`. Before the project exists, write them in a scratch directory with the same file names and copy them into the project at the retarget step. Scripts take explicit paths, so the directory can be anywhere.

`validate_facts.py --facts DIR [--stage mcu|pinmap|peripherals|all]` checks the JSON files below. It reports missing required keys, unknown `kind` values, duplicate board pin names and missing `source`. Exit 1 on any error.

## Provenance: `source`

Every row or object that a person or the agent supplied carries `"source"`:

| Value | Meaning |
|---|---|
| `script` | produced by a script from the input files, with no agent edit |
| `user-confirmed` | the user saw the value and said it is right |
| `inferred` | the agent derived it by reasoning, or read it from a document without the user seeing it |

Rules:

- Use the weakest source that applies. A value built from a script output and an agent edit is `inferred`.
- Change `inferred` to `user-confirmed` only after the user answered about that item.
- Every `inferred` item is listed as an open question in the report.
- A script-written file has no `source` key unless the script adds one. Do not add `source` to a file that a script wrote and you did not edit.

## `nets.json`

Output of `parse_netlist.py`. Write it by hand only for formats the script does not read (see `input-intake.md`).

```json
{
  "format": "kicad|protel|csv",
  "components": {"U1": {"value": "STM32F767ZIT6", "footprint": "LQFP-144"}},
  "nets": {"PA3": [{"ref": "U1", "pin": "34", "pinfunction": "PA3"}]}
}
```

- `components`: reference designator to `value` and `footprint`.
- `nets`: net name to the list of nodes. A node has `ref`, `pin` (package pin, as a string) and `pinfunction`.
- `pinfunction` is `null` when the format does not carry it.
- Net names are stored exactly as in the source. KiCad names can start with `/` (the sheet prefix).
- A file built by reasoning has `"format"` set to the closest of the three values, a top-level `"source": "inferred"` and `"source"` on each node you wrote.

## Pin table CSV

Input of `resolve_pinmap.py --pin-table`. Name: `pin-table.csv`.

```csv
package_pin,port_name
34,PA3
35,PC4
```

`port_name` is the port's name for the pad: `PA3` (stm32, samd), `GPIO3` (rp2, esp32), `GPIO_AD_B0_03` (mimxrt). A CSV has no `source` column. Record how the table was made in `mcu.json` (`source`) and in the report.

## `mcu.json`

```json
{"part": "STM32F767ZIT6", "port": "stm32", "mcu_ref": "U1", "package": "LQFP144",
 "series": "f7", "seed_board": "NUCLEO_F767ZI", "source": "user-confirmed"}
```

| Key | Content |
|---|---|
| `part` | orderable part number as the user confirmed it |
| `port` | `stm32`, `rp2`, `esp32`, `mimxrt` or `samd` |
| `mcu_ref` | reference designator of the MCU in the netlist |
| `package` | package name and pin count |
| `series` | the port's series or variant name: stm32 `f7`, mimxrt `MIMXRT1062`, samd `SAMD51`, rp2 `rp2040` or `rp2350`, esp32 `esp32s3` |
| `seed_board` | board directory name chosen by `pick_seed.py` and the user. It may be empty until the seed choice: `validate_facts.py --stage mcu` then warns, `--stage all` reports an error. The extract step leaves it empty; the main agent fills it after the seed choice. |
| `source` | `user-confirmed` or `inferred`. Required. |

## `pinmap.json`

Output of `resolve_pinmap.py`. Do not edit it.

```json
{"port": "stm32", "mcu_ref": "U1", "status": "ok",
 "pins": [{"package_pin": "34", "port_name": "PA3", "net": "ADC_IN", "anchor": false}],
 "anchors": [{"package_pin": "34", "port_name": "PA3", "net": "PA3"}],
 "errors": []}
```

- `status` is `ok` or `fail`. `fail` means exit 1 and no downstream step may use the file; `gen_pins_csv.py` refuses it.
- `pins`: one entry per MCU package pin that has a port name. `net` is the net name as in `nets.json`. `anchor` is true when the net name equals the port name.
- `anchors`: the nets that carry a port pin name and so prove the table.
- `errors`: the gate's messages.
- `confirmed`: present and `true` only when the script ran with `--confirmed`.

On success `resolve_pinmap.py` also prints `resolve_pinmap: ok, N pins, M anchors` on stderr. The messages in `errors` go to stderr as well.

## `peripherals.json`

Written by the agent. Read by `lint_board.py` and `gen_hardware.py`.

```json
{"peripherals": [
  {"name": "led", "kind": "led", "pins": {"pin": "LED_GREEN"}, "active_high": true, "source": "user-confirmed"},
  {"name": "button", "kind": "gpio", "direction": "in", "pull": "up", "pins": {"pin": "USER_BTN"}, "source": "user-confirmed"},
  {"name": "sensors", "kind": "i2c", "bus_id": 1, "freq": 400000,
   "pins": {"scl": "I2C1_SCL", "sda": "I2C1_SDA"},
   "devices": [{"name": "imu", "addr": "0x68", "part": "ICM-42688"}], "source": "inferred"},
  {"name": "flash", "kind": "spi", "bus_id": 2, "baudrate": 1000000,
   "pins": {"sck": "SPI2_SCK", "mosi": "SPI2_MOSI", "miso": "SPI2_MISO"},
   "devices": [{"name": "nor", "cs": "FLASH_CS", "part": "W25Q128"}], "source": "inferred"},
  {"name": "console", "kind": "uart", "bus_id": 4, "baudrate": 115200, "pins": {"tx": "U4_TX", "rx": "U4_RX"}, "source": "user-confirmed"},
  {"name": "vbat", "kind": "adc", "pins": {"pin": "VBAT_SENSE"}, "source": "inferred"},
  {"name": "fan", "kind": "pwm", "freq": 25000, "pins": {"pin": "FAN_PWM"}, "source": "inferred"}
]}
```

| Key | Content |
|---|---|
| `name` | Python-safe lower-case identifier, unique. It becomes an attribute of `DeviceCollection` and part of constant names (`<NAME>_PIN`, `<NAME>_ID`, `<NAME>_FREQ` or `<NAME>_BAUDRATE`, `<NAME>_ADDR`). |
| `kind` | `led`, `gpio`, `i2c`, `spi`, `uart`, `adc` or `pwm`. No other value is valid. |
| `pins` | role to pin name. Roles by kind: `led`, `gpio`, `adc`, `pwm`: `pin`. `i2c`: `scl`, `sda`. `spi`: `sck` (required), `mosi`, `miso` (at least one of the two). `uart`: `tx`, `rx` (at least one), and `rts`, `cts`, which `validate_facts.py` accepts and `gen_hardware.py` does not use. |
| `bus_id` | the MicroPython bus number the port uses. stm32 `I2C(1)`; rp2 `I2C(0)`; samd the id the port maps to a SERCOM (read the board's `MICROPY_HW_DEFAULT_*_ID` and the `SERCOM` columns of the AF table); mimxrt the logical index from `MICROPY_HW_*_INDEX`; esp32 any free id. |
| `freq`, `baudrate` | numeric. I2C and PWM use `freq`. SPI and UART use `baudrate`. |
| `active_high` | LED only. `true` when a high level turns the LED on. |
| `direction`, `pull`, `value` | GPIO only. `direction` is `in` or `out` and is required. `pull` is `up`, `down` or `none` (no pull); omitting it means no pull. `value` is the initial level of an output (`0` or `1`, default `0`). |
| `devices` | I2C: `name`, `addr` (hex string), `part`. SPI: `name`, `cs` (board pin name), `part`. |
| `source` | `user-confirmed` or `inferred`. Required on every peripheral. |

Pin values are board pin names, as they appear in the first column of the board's `pins.csv`. They follow the rule for board pin names below, applied to net names in the netlist. On rp2, samd, mimxrt and esp32 a value can also be a pad name of the port (`GPIO14`, `PB08`, `GPIO_B0_03`). Pads whose board name equals the pad name are not in `pins.csv` on these ports, so their nets are referenced by pad name. On stm32 every pin value needs a `pins.csv` row.

## Board `pins.csv`

`<BOARD_PIN_NAME>,<port_name>` per line. Names are unique. See each port's seed board for the style. The file is written by `gen_pins_csv.py` from `pinmap.json`. Do not write it by hand.

Board pin names come from net names:

1. Strip the KiCad sheet prefix `/`.
2. Upper-case.
3. Replace characters outside `[A-Z0-9_]` with `_`.
4. Prefix `P_` if the first character is a digit.
5. Skip unnamed nets: KiCad `Net-(...)` and `unconnected-(...)`, Protel `NetU1_5`, and `N$12`.

`gen_pins_csv.py` options:

- `--exclude NAME ...` leaves named nets out.
- `--include-pad PAD[=NAME]` (repeatable) adds a pad with an unnamed net under `NAME` (default: the pad name). It is ignored, with a warning, when the pad's net is named.
- `--keep-self-named` keeps rows whose board name equals the pad name. They are left out by default on rp2, samd, mimxrt and esp32, where such a row makes `make-pins.py` emit a duplicate `pin_<PAD>` define; stm32 keeps them.
- `--af-file CSV` adds the pad names of the port's AF table as valid port names.

The script skips the MCU's power, ground and other non-port pins. It exits 1 on a name collision, an invalid port name, or a `pinmap.json` whose `status` is not `ok`. With `-o` it prints a JSON summary: `written`, `count`, `skipped` (package pin and net of each skipped pin) and `warnings`.

## Free-form records

These files are not schema-checked. Write them in plain markdown, one decision per row, with the source of each.

| File | Writer | Content |
|---|---|---|
| `clock-power.md` | `derive-clock-power` | clock, memory, USB, storage and power decisions: item, value, source, evidence, status |
| `review.md` | `verify-board-profile` | findings with severity and evidence, and the list of open questions |

The final report `hardware/board-profile-report.md` summarises these.

## Which script gates which file

| File | Gate |
|---|---|
| `nets.json` | `parse_netlist.py` output, or checked by hand against the source |
| `mcu.json` | `validate_facts.py --stage mcu` |
| `pinmap.json` | `resolve_pinmap.py` exit code and `status`, then `validate_facts.py --stage pinmap` |
| `peripherals.json` | `validate_facts.py --stage peripherals`, then `lint_board.py --peripherals` once the board directory exists |
| `pins.csv` | `gen_pins_csv.py` exit code, then `lint_board.py` |
