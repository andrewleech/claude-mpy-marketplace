# Hardware skeleton

`gen_hardware.py` writes the application hardware layer of an app-template project from `peripherals.json`. It does not write driver code for parts.

```bash
uv run <skill-dir>/scripts/gen_hardware.py --project <dir> --port <port> \
  --peripherals hardware/facts/peripherals.json --board-name <BOARD> \
  [--pins-csv src/system/<BOARD>/pins.csv] [--force]
```

Exit 0 on success, 1 on failure, 2 on bad arguments. It refuses to overwrite a target file that differs from `git HEAD` of the project unless `--force` is given. A generated file that the user edited by hand is therefore safe until `--force`.

## Files written

All paths are relative to the project.

### `src/firmware/application/device_config.py`

Keeps the original docstring, `AUTORUN`, `LOG_LEVEL`, `LED_ON_TIME` and `LED_OFF_TIME`. Adds:

- pin constants `<NAME>_PIN`: string board pin names. On esp32 they are integer GPIO numbers, resolved through `--pins-csv`;
- bus constants `<NAME>_ID`, and `<NAME>_FREQ` (I2C, PWM) or `<NAME>_BAUDRATE` (SPI, UART);
- device constants `<NAME>_ADDR` for I2C devices, and chip-select pin constants for SPI devices.

`LED_PIN` exists only when a `led` peripheral exists.

### `src/firmware/application/hardware.py`

- Keeps `Blinky` and the `led` object only when a `led` peripheral exists.
- Constructs each peripheral with the port's constructor form and adds it as an attribute of `DeviceCollection`.
- Keeps `shutdown()`. It stops the blinky when there is one and sets the duty of every PWM to 0 (`duty_u16(0)`).
- Adds no driver code. A recognised part gets a bus and an address constant and nothing else.

Chip select and plain GPIO are `Pin(name, Pin.OUT, value=1)` and `Pin(name, Pin.IN, Pin.PULL_UP)`. ADC is `ADC(Pin(name))`. PWM is `PWM(Pin(name), freq=..., duty_u16=0)`: the output starts off.

### `src/firmware/test/test_hardware.py`

A `unittest` file:

1. Imports `hardware` under the mock and checks that every generated `devices` attribute exists with the generated type, and that outputs and PWM start in their idle state (`duty_u16() == 0` for PWM, chip selects high).
2. When a `pins.csv` exists for the board, calls `Pin.board.configure(<relative path>)` and asserts that every `*_PIN` constant in `device_config` resolves through `Pin.board.<NAME>`. This checks the config against the board file. The `Pin.board.configure` calls carry `# type: ignore[attr-defined]`, because the port stubs used by mypy have no `Pin.board`.

Pin constants that hold a pad name instead of a `pins.csv` name (rp2, samd, mimxrt, for a pad that `pins.csv` leaves out) are not checked against `Pin.board`. They are cpu names, and `lint_board.py` checks them against the port tables. On esp32 the constants are GPIO numbers, checked through `Pin.cpu`.

Tests run with the working directory `src/unix/build/frozen_mpy`, so the path is `../../../../src/system/<BOARD>/pins.csv`. The file has no test that only echoes a constant.

### Patches when there is no LED

If `peripherals.json` has no `led` peripheral:

- `device.py` is patched: `TASKS = ()` and the `devices.blinky.start()` line are removed.
- `test_blink.py` is deleted.

The patch is exact string replacement and fails if the expected text is absent. If the template changed and the patch fails, apply the change by hand and tell the user.

## Constructor forms by port

Verified against `docs/<port>/quickref.rst` and the port sources in the MicroPython tree. Re-check when the tree is newer.

| Port | I2C | SPI | UART |
|---|---|---|---|
| rp2, esp32 | `I2C(id, scl=Pin(..), sda=Pin(..), freq=..)` | `SPI(id, baudrate=.., sck=Pin(..), mosi=Pin(..), miso=Pin(..))` | `UART(id, baudrate=.., tx=Pin(..), rx=Pin(..))` |
| stm32 | `I2C(id, freq=..)` | `SPI(id, baudrate=..)` | `UART(id, baudrate=..)` |
| mimxrt | `I2C(id, freq=..)` | `SPI(id, baudrate=..)` | `UART(id, baudrate=..)` |
| samd | `I2C(id, scl=Pin(..), sda=Pin(..), freq=..)` | `SPI(id, sck=Pin(..), mosi=Pin(..), miso=Pin(..), baudrate=..)` | `UART(id, tx=Pin(..), rx=Pin(..), baudrate=..)` |

For stm32 and mimxrt the pins are fixed by the bus id. On stm32 the pins come from the `MICROPY_HW_<BUS>_*` macros in the board's `mpconfigboard.h`, so the ids in `peripherals.json` must match the macros. `lint_board.py` checks that the pins match the id. On mimxrt they come from the `IOMUX_TABLE_*` and `MICROPY_HW_*_INDEX` macros.

ADC and PWM:

| Port | `ADC` | `PWM` |
|---|---|---|
| rp2, esp32, samd | `ADC(Pin(name))` | `PWM(Pin(name), freq=.., duty_u16=0)` |
| stm32 | `ADC(Pin(name))`. The pad needs an ADC channel. | `PWM(Pin(name), freq=.., duty_u16=0)`. The pad needs a timer channel. |
| mimxrt | `ADC(Pin(name))`. The pad needs an `ADC` cell in the AF row. | `PWM(Pin(name), freq=.., duty_u16=0)`. See `docs/mimxrt/quickref.rst` for the pad rules. |

When the script has no form for a kind on a port, it exits 1 with a message that names the kind and the port. Write the construction by hand (below).

## Example output

For a project with a green LED and one I2C sensor on rp2:

```python
# device_config.py (added lines)
LED_PIN = "LED"

SENSORS_ID = 0
SENSORS_FREQ = 400_000
SENSORS_SCL_PIN = "I2C0_SCL"
SENSORS_SDA_PIN = "I2C0_SDA"
IMU_ADDR = 0x68
```

```python
# hardware.py (added lines)
from machine import I2C, Pin

sensors = I2C(
    device_config.SENSORS_ID,
    scl=Pin(device_config.SENSORS_SCL_PIN),
    sda=Pin(device_config.SENSORS_SDA_PIN),
    freq=device_config.SENSORS_FREQ,
)
```

The exact text is the script's. Treat this as the pattern: constants in `device_config.py`, construction in `hardware.py`, one attribute per peripheral on `DeviceCollection`.

## When to hand-edit

Edit by hand when:

- the script has no constructor form for a kind on this port;
- the peripheral needs more than the generic form (for example SPI with `polarity` and `phase`, UART with flow control, SDMMC, I2S, CAN, a timer-based capture);
- the user wants driver code for a part.

Rules for hand edits:

1. Keep every peripheral construction in `hardware.py`. Never construct hardware in `device.py` or `main.py`.
2. Put numbers and names in `device_config.py`. Use the `<NAME>_PIN`, `<NAME>_ID`, `<NAME>_FREQ` or `<NAME>_BAUDRATE`, `<NAME>_ADDR` pattern.
3. Add the object as an attribute of `DeviceCollection` and update `__init__`.
4. Extend `test_hardware.py` so the new attribute and its pin constants are checked.
5. If a class in `mock_machine` does not model the peripheral, test only that the object constructs and write nothing that restates the mock.
6. Keep the code formatted for ruff (line length 99, double quotes, 4-space indent) and typed for the project's mypy configuration.
7. Commit by hand edits separately from the generated files, or note them in the commit message, so the next `gen_hardware.py` run without `--force` stops instead of overwriting them.

## Checks after generation

```bash
make tests
make checks
```

`make tests` runs `test_hardware.py` on the unix port. `make checks` runs ruff and mypy. Fix findings in the generated files by editing `peripherals.json` and generating again, or by hand when the fix is one of the cases above.
