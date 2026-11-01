# rp2 port

Port directory: `ports/rp2`. Board directories: `ports/rp2/boards/<BOARD>/`. Build system: cmake, driven by the port Makefile. The reference seeds are `RPI_PICO` (files: `board.json`, `mpconfigboard.cmake`, `mpconfigboard.h`, `pins.csv`) and `RPI_PICO2` (the same plus `mpconfigvariant.cmake` and `mpconfigvariant_RISCV.cmake`).

## Template answers

| Answer | Value |
|---|---|
| `target_port` | `rp2` |
| `template_board` | the seed. Template default: `RPI_PICO`. Use a `RPI_PICO2`-class board for RP2350. |
| `project_board_name` | `<PROJECT_NAME_UPPER>_<template_board>` or a chosen upper-case name |
| `use_mboot`, `bootloader_address` | not asked on this port. Do not set them. |

Test answer file: `rp2.copier-answers.yml` (`template_board: RPI_PICO`).

## What the retarget stage edits

All edits are in `src/system/<BOARD>/`.

### `board.json`

`mcu` is `rp2040` or `rp2350`. Set `product`, `vendor`, `url`, `features` (`Dual-core`, `External Flash`, `USB`, ...). Set `images` and `thumbnail` to empty values when the files do not exist in the project. A `variants` object lists the variant names; each name needs a `mpconfigvariant_<NAME>.cmake` file.

### `mpconfigboard.cmake`

Settings seen in the tree:

| Variable | Rule |
|---|---|
| `PICO_BOARD` | the pico-sdk board name. When unset, the port lowercases the MicroPython board name and uses it. If no pico-sdk header has that name, set `PICO_BOARD` to `none` (as `SIL_RP2040_SHIM` does) or add a header (see below). With `none` the pico-sdk reads no board header, so the board files must supply what the header would: `PICO_PLATFORM` in the cmake file, `PICO_FLASH_SIZE_BYTES` (cmake file and `mpconfigboard.h`), `PICO_BOOT_STAGE2_CHOOSE_<flash type>` in `mpconfigboard.h`, and the default bus pins (see `mpconfigboard.h` below). |
| `PICO_PLATFORM` | `rp2040`, `rp2350` (Arm) or `rp2350-riscv`. With a pico-sdk board header it comes from the header (`pico_board_cmake_set(PICO_PLATFORM, rp2040)` in `boards/pico.h`, `rp2350` in `pico2.h`); `RPI_PICO` also sets it explicitly. With `PICO_BOARD none` or a board directory without a header, set it in `mpconfigboard.cmake`: `set(PICO_PLATFORM "rp2040")`. |
| `PICO_NUM_GPIOS` | `48` for RP2350B packages (QFN-80). Default for RP2040 and RP2350A is 30. |
| `PICO_FLASH_SIZE_BYTES` | flash size of the board when the pico-sdk header does not set it (`SIL_RP2040_SHIM` sets it in cmake and in `mpconfigboard.h`) |
| `MICROPY_HW_FLASH_STORAGE_BYTES` | size of the filesystem area. Written as `if(NOT DEFINED MICROPY_HW_FLASH_STORAGE_BYTES) set(...) endif()`. See the flash decision below. |
| `MICROPY_HW_ENABLE_PSRAM`, `MICROPY_HW_PSRAM_CS_PIN` | PSRAM (RP2350). Set both when PSRAM is fitted; the pin is the QSPI CS2 GPIO. |
| `PICO_BOARD_HEADER_DIRS` | `list(APPEND PICO_BOARD_HEADER_DIRS ${MICROPY_BOARD_DIR})` when the board directory carries its own pico-sdk header |
| `MICROPY_PY_NETWORK_CYW43`, `MICROPY_PY_NETWORK_WIZNET5K`, `MICROPY_PY_NETWORK_NINAW10`, `MICROPY_PY_LWIP`, `MICROPY_PY_BLUETOOTH`, `MICROPY_BLUETOOTH_BTSTACK` | network and radio features. Remove those the hardware lacks. |
| `MICROPY_FROZEN_MANIFEST` | leave. The project include sets it. |

Leave the appended `include(${MICROPY_BOARD_DIR}/../mpconfigproj.cmake)` line in place.

A custom pico-sdk board header carries the board facts that the pico-sdk reads: `PICO_DEFAULT_LED_PIN`, the default UART, I2C and SPI pins, `PICO_FLASH_SIZE_BYTES`, `PICO_BOOT_STAGE2_CHOOSE_<flash type>`, `PICO_FLASH_SPI_CLKDIV`, and `pico_board_cmake_set(PICO_PLATFORM, ...)`. `WAVESHARE_RP2350B_CORE/waveshare_rp2350b_core.h` is a complete example. Write one only when no header in `lib/pico-sdk/src/boards/include/boards/` matches. The boot stage 2 choice depends on the flash chip. Take it from the flash part number and state it as an item to confirm.

Variant files: `mpconfigvariant.cmake` (default variant additions) and `mpconfigvariant_<NAME>.cmake` (for example `RISCV`: `set(PICO_PLATFORM "rp2350-riscv")`). Keep a variant only when the hardware needs it. Remove the others and the matching `variants` entries in `board.json`.

### `mpconfigboard.h`

| Macro | Rule |
|---|---|
| `MICROPY_HW_BOARD_NAME` | set the name part; keep the `<PROJECT>-` prefix |
| `MICROPY_HW_USB_VID`, `MICROPY_HW_USB_PID` | remove IDs that belong to the seed's vendor; the port default applies. The template leaves USB IDs alone on purpose. |
| `MICROPY_HW_I2C0_SCL`, `_SDA`, `MICROPY_HW_I2C1_*` | default pins of each bus, used when the constructor omits `scl` and `sda`. With `PICO_BOARD none` the I2C0 pair is required: `machine_i2c.h` takes the `PICO_DEFAULT_I2C_SCL_PIN` branch for bus 0 when `PICO_DEFAULT_I2C` is undefined, and the build fails with `'PICO_DEFAULT_I2C_SCL_PIN' undeclared`. Bus 1 has numeric fallbacks (GPIO 7 and 6) that may not match the design, so define it as well. Define both pins of a bus together; the lint reports a half-defined pair. `MICROPY_HW_I2C_NO_DEFAULT_PINS` removes the defaults and the requirement. |
| `MICROPY_HW_SPI0_SCK`, `_MOSI`, `_MISO`, `MICROPY_HW_SPI1_*` | default SPI pins. With `PICO_BOARD none` the SPI0 set is required, for the same reason (`PICO_DEFAULT_SPI_*_PIN`); bus 1 falls back to GPIO 10, 11 and 8. Define all three pins of a bus together. `MICROPY_HW_SPI_NO_DEFAULT_PINS` removes the defaults and the requirement. |
| `MICROPY_HW_UART0_TX`, `_RX`, `_CTS`, `_RTS`, `MICROPY_HW_UART1_*` | default UART pins. Define all four of a UART together. `machine_uart.c` guards the defaults with `#if !defined(MICROPY_HW_UART0_TX)`, so a board that defines only `_TX` and `_RX` leaves `MICROPY_HW_UART0_CTS` and `_RTS` undeclared and the build fails. The lint reports an incomplete set. |
| `MICROPY_HW_PIN_EXT_COUNT`, `MICROPY_HW_PIN_RESERVED(i)` | extra pins behind a radio chip and pins the user must not touch. Remove when the hardware has neither. |
| `PICO_FLASH_SIZE_BYTES`, `PICO_BOOT_STAGE2_CHOOSE_*` | when the board has no pico-sdk header |
| `CYW43_*`, `MICROPY_PY_NETWORK*` | radio and network settings. Remove for a board without the radio. |

Default pins are only defaults. Hardware validity of a bus is decided by the pin number, see below.

### `pins.csv`

Written by `gen_pins_csv.py`. Style: `<BOARD_NAME>,GPIO<n>`. Example lines from `RPI_PICO`: `GP0,GPIO0`, `LED,GPIO25`. The file replaces the seed's. Every GPIO of the chip is available to Python by its `GPIO<n>` name whether listed or not. The file only adds board names. A row whose board name equals the pad name (`GPIO14,GPIO14`) must not be in the file: `make-pins.py` emits `pin_GPIO14` for the pad and again for the board name, and the build fails (`"pin_GPIO14" redefined`, an error under `-Werror`). `gen_pins_csv.py` skips such rows on this port. A pin in `peripherals.json` that names such a pad uses the pad name.

## Clock and power decisions to derive

| Decision | Facts needed | Where it lands |
|---|---|---|
| Crystal: frequency (12 MHz is the reference design) | BOM, schematic | pico-sdk `XOSC_HZ`, `XOSC_KHZ` or `XOSC_MHZ` (default 12 MHz), set in the board header. A different crystal is a pico-sdk setting, not a MicroPython one. State as an item to confirm. |
| Flash size and type | BOM | `PICO_FLASH_SIZE_BYTES`, boot stage 2 choice, `MICROPY_HW_FLASH_STORAGE_BYTES` |
| Filesystem size | flash size and firmware size | `MICROPY_HW_FLASH_STORAGE_BYTES` = flash size minus the firmware area. Seeds use values such as `1441792` (`RPI_PICO`, 1408 KiB) and `3145728` (`RPI_PICO2`, 3 MiB of 4 MiB). Leave room for the firmware image. A 16 MiB flash and `MICROPY_HW_FLASH_STORAGE_BYTES` of 14 MiB is an example in the tree. |
| PSRAM present (RP2350) | BOM | `MICROPY_HW_ENABLE_PSRAM`, `MICROPY_HW_PSRAM_CS_PIN` |
| Chip: RP2040 or RP2350 (A or B) | part number | `PICO_PLATFORM`, `PICO_NUM_GPIOS` |
| USB device | schematic | on by default. USB pins are fixed (`USB_DP`, `USB_DM`). |
| LED pin and polarity | schematic | board names in `pins.csv`, `peripherals.json` |
| Buttons | schematic | `peripherals.json` (plain GPIO). A BOOTSEL button is on the QSPI CS pin, not on a GPIO. |
| Radio module (CYW43) | BOM | cmake network features and `CYW43_*` macros. The pins are fixed by the module's wiring. |
| External wake or power-enable pins | schematic | `peripherals.json` (GPIO) or a code decision for the user |

The RP2040 and RP2350 run from the pico-sdk's clock tree. MicroPython does not need a clock setting in the board files.

## Pin and alternate-function validity

Two sources, both in the checkout:

1. `boards/rp2040_af.csv`, `rp2350_af.csv` (RP2350A, 30 GPIOs) and `rp2350b_af.csv` (RP2350B, 48 GPIOs). Header `Pin,AF0..AF9`. Cells are signals such as `SPI0_RX`, `UART0_TX`, `I2C0_SDA`, `PWM0_A`. Choose the file by `PICO_PLATFORM` and `PICO_NUM_GPIOS`.
2. Bus validity macros in `machine_spi.c`, `machine_uart.c` and `machine_i2c.h`. `lint_board.py --port rp2` evaluates them for the pin number:
   - I2C: `IS_VALID_SCL(i2c, pin)` is `(pin & 1) == 1 && ((pin & 2) >> 1) == i2c`; `IS_VALID_SDA` has `(pin & 1) == 0`.
   - SPI: `IS_VALID_PERIPH(spi, pin)` is `((pin & 8) >> 3) == spi`; SCK is `(pin & 3) == 2`, MOSI `== 3`, MISO `== 0`.
   - UART: `IS_VALID_PERIPH(uart, pin)` is `((((pin) + 4) & 8) >> 3) == uart`. RP2350 (`#if PICO_RP2350`): TX is `(pin & 1) == 0`, RX is `(pin & 1) == 1`. RP2040: TX is `(pin & 3) == 0`, RX is `(pin & 3) == 1`. CTS is `(pin & 3) == 2`, RTS `== 3`.
   - ADC: GPIOs `ADC_BASE_PIN` to `ADC_BASE_PIN + NUM_ADC_CHANNELS - 1` (`machine_adc.c`). In the pico-sdk `platform_defs.h`, `ADC_BASE_PIN` is 26 on RP2040 and RP2350A, and 40 on RP2350B. `docs/rp2/quickref.rst` lists the channels.

Read the macros from the checkout. The rules above are from the current tree and can change. PWM works on any GPIO; slice and channel come from the pin number (`PWM0_A`, `PWM0_B` in the AF file).

## Machine constructors (verified in `docs/rp2/quickref.rst`)

```python
from machine import I2C, SPI, UART, ADC, PWM, Pin

i2c = I2C(1, scl=Pin(3), sda=Pin(2), freq=400_000)
spi = SPI(0, baudrate=1_000_000, sck=Pin(6), mosi=Pin(7), miso=Pin(4))
uart = UART(1, baudrate=115200, tx=Pin(4), rx=Pin(5))
adc = ADC(Pin(26))
pwm = PWM(Pin(15), freq=25000)
```

Board names work in place of numbers when the name is in `pins.csv`: `Pin("LED")`. `I2C(0)` and `SPI(1, 10_000_000)` with no pins use the defaults from `MICROPY_HW_*` or the pico-sdk header. UART0 can sit on GPIO 0/1, 12/13 and 16/17; UART1 on 4/5 and 8/9 (RP2040). Software `SoftI2C` and `SoftSPI` work on any pin.

## Pitfalls

- The BOOTSEL pin is the flash chip select, not a GPIO. Do not model it as a button.
- On RP2350B, GPIOs 30 to 47 exist. `PICO_NUM_GPIOS` must be `48` and the AF file is `rp2350b_af.csv`.
- `MICROPY_HW_FLASH_STORAGE_BYTES` larger than the free flash makes the link fail or the filesystem overwrite firmware.
- Pins behind the CYW43 radio are not GPIOs (`EXT_GPIO<n>`). A board without the radio must not define `MICROPY_HW_PIN_EXT_COUNT`.
- A wrong boot stage 2 for the flash chip builds but does not boot.
- `PICO_BOARD none` without the I2C0 and SPI0 default pin macros in `mpconfigboard.h` fails to compile (`PICO_DEFAULT_I2C_SCL_PIN` undeclared). A UART macro set without `_CTS` and `_RTS` fails too.
- A self-named row such as `GPIO14,GPIO14` in `pins.csv` fails the build with `"pin_GPIO14" redefined`. `gen_pins_csv.py` leaves such rows out.
- rp2 builds need the container image for `make submodules`, because the port dependencies are resolved through cmake.

## Build and verification commands

```bash
make submodules && make system
make libs-only
make tests
make checks
```

`make mboot` does not exist on this port. Firmware lands in `src/system/build-<BOARD>/` (`firmware.uf2`, `firmware.elf`, `firmware.bin`).
