# samd port

Port directory: `ports/samd`. Board directories: `ports/samd/boards/<BOARD>/`. Build system: make. Series: SAMD21 (Cortex-M0+) and SAMD51 (Cortex-M4). The reference seed is `ADAFRUIT_ITSYBITSY_M4_EXPRESS` (files: `board.json`, `mpconfigboard.h`, `mpconfigboard.mk`, `pins.csv`). Generic boards without board-specific hardware exist: `SAMD_GENERIC_D21X18`, `SAMD_GENERIC_D51X19`, `SAMD_GENERIC_D51X20`.

## Template answers

| Answer | Value |
|---|---|
| `target_port` | `samd` |
| `template_board` | the seed. Template default: `ADAFRUIT_ITSYBITSY_M4_EXPRESS`. Use the exact MCU match from `pick_seed.py` (same `CMSIS_MCU` as the design). When several boards tie, choose by features. A `SAMD_GENERIC_*` board of another package (`SAMD_GENERIC_D51X19` is `SAMD51P19A`, not `SAMD51J19A`) is a series match only: its `CMSIS_MCU` and `MICROPY_HW_MCU_NAME` must change and its `MICROPY_HW_CODESIZE` comment does not hold for the design's flash size. |
| `project_board_name` | `<PROJECT_NAME_UPPER>_<template_board>` or a chosen upper-case name |
| `use_mboot`, `bootloader_address` | not asked on this port. Do not set them. |

The port has no answer file in the template's test set. It follows the make-based pattern.

Board-specific items to remove from the seed copy, when the design lacks them: `MICROPY_HW_QSPIFLASH`, `MICROPY_HW_MCU_OSC32KULP`, the `board.json` `deploy` path and `images` entry, and the `board.json` `features` entries that describe the seed (`Battery Charging`, `Feather`, `RGB LED`, `External Flash`). The seed's `pins.csv` is replaced by `gen_pins_csv.py`, so its NEOPIXEL, battery sense and QSPI pin names go with it.

## What the retarget stage edits

All edits are in `src/system/<BOARD>/`.

### `board.json`

`mcu` is `samd21` or `samd51`. Set `product`, `vendor`, `url` and `features` (`External Flash`, `RGB LED`, `USB`, ...). Seed boards set `deploy` to `["../deploy.md"]`, a path to `ports/samd/boards/deploy.md` that the project copy does not have, and `images` to a file name that is not copied. Set `deploy` and `images` to empty lists, or to files that exist in the project.

### `mpconfigboard.mk`

| Variable | Rule |
|---|---|
| `MCU_SERIES` | `SAMD21` or `SAMD51`. It selects `mcu/<series lower case>/` (`pin-af-table.csv`, `clock_config.c`, `mpconfigmcu.mk`, `mpconfigmcu.h`). |
| `CMSIS_MCU` | the exact device, for example `SAMD51G19A`, `SAMD21J18A`, `SAMD51P19A`. It becomes `-D__<CMSIS_MCU>__`. |
| `LD_FILES` | `boards/<device class>.ld sections.ld`. Files in the tree: `samd21x18a.ld`, `samd51x19a.ld`, `samd51x20a.ld`. The name follows the part number (`SAMD51x19A`). Open the file and compare the `MEMORY` block with the part's flash and RAM sizes. |
| `TEXT0` | start address of the firmware. It is the size of the UF2 bootloader: `0x2000` on SAMD21 boards, `0x4000` on SAMD51 boards in the tree. Without a bootloader, check the `ORIGIN` of flash in the `.ld` file and ask the user. |
| `MICROPY_HW_CODESIZE` | size of the firmware region, as `?=`. `432K` for the Feather M4 Express and ItsyBitsy M4 seeds, `368K` for `SAMD_GENERIC_D51X19`, `184K` default for SAMD21. The internal filesystem is `_sflash_fs = _flashsize - _codesize - _bootloader - MICROPY_HW_ROMFS_BYTES` (from the `.ld` file): flash size minus bootloader minus firmware region minus ROM filesystem. `samd51x19a.ld` has `_flashsize = 512K` and `_bootloader = 16K`, so the filesystem is `496k - MICROPY_HW_CODESIZE - MICROPY_HW_ROMFS_BYTES`; that is the comment in `SAMD_GENERIC_D51X19`. The Feather M4 Express (`SAMD51J19A`) and ItsyBitsy M4 seed comments say `1008k`, which is the value for a 1 MiB part (`samd51x20a.ld`: `_flashsize = 1024K`); it does not apply to a 512 KiB part. Read `_flashsize` and `_bootloader` from the `.ld` file and compute the result for the part. State it as an item to confirm. |
| `MICROPY_HW_ROMFS_BYTES` | ROM filesystem size, as `?=`. Default `64K` on SAMD51. SAMD21 defaults to `0`, except `12K` when `MICROPY_HW_CODESIZE` is `236K`. |
| `MICROPY_PY_NETWORK`, `MICROPY_PY_NETWORK_NINAW10` | only when a NINA-W10 module is fitted |

Leave the appended `include $(BOARD_DIR)/../mpconfigproj.mk` line in place.

Filesystem location: when none of `MICROPY_HW_QSPIFLASH`, `MICROPY_HW_SPIFLASH` (with `MICROPY_HW_SPIFLASH_ID`) or `MICROPY_HW_MCUFLASH` is defined, `mpconfigport.h` puts the filesystem in internal flash. The 512 KiB SAMD51 seeds with QSPI flash use `MICROPY_HW_CODESIZE ?= 432K`, which leaves `512K - 16K - 432K - 64K = 0` of internal flash. A board that drops `MICROPY_HW_QSPIFLASH` must reduce `MICROPY_HW_CODESIZE` to make room. With `368K` a 512 KiB part keeps a 64K filesystem (`496k - 368K - 64K`).

### `mpconfigboard.h`

| Macro | Rule |
|---|---|
| `MICROPY_HW_BOARD_NAME` | set the name part; keep the `<PROJECT>-` prefix |
| `MICROPY_HW_MCU_NAME` | the part name (equal to `CMSIS_MCU` in the seeds) |
| `MICROPY_HW_XOSC32K` | `1` when a 32.768 kHz crystal is fitted. With it, the crystal clocks `GCLK1` and the DFLL48M reference. |
| `MICROPY_HW_MCU_OSC32KULP` | SAMD51 only. With `XOSC32K`, drives `GCLK1` from the internal 32 kHz ultra-low-power oscillator and not from the crystal. Set it only for a known crystal disturbance problem. The Feather M4 Express seed sets it for its own hardware; remove it unless the design has the same problem. |
| `MICROPY_HW_DFLL_USB_SYNC` | `1` synchronises DFLL48M to USB start-of-frame. It is the usual choice for USB boards. Without USB, leave it out or set `0`. |
| `MICROPY_HW_DEFAULT_UART_ID`, `MICROPY_HW_DEFAULT_I2C_ID`, `MICROPY_HW_DEFAULT_SPI_ID` | SERCOM index of the default buses. Set to the SERCOMs the board uses for its main UART, I2C and SPI. A value `< 0` removes the default. The lint warns when a value matches no `bus_id` of that kind in `peripherals.json`. |
| `MICROPY_HW_QSPIFLASH` | QSPI flash part names, for example `W25Q32JV_IQ` or `GD25Q16C, W25Q16JV_IQ` (SAMD51). Remove it when no QSPI flash is fitted, and adjust `MICROPY_HW_CODESIZE` (see above). |
| `MICROPY_HW_SPIFLASH`, `MICROPY_HW_SPIFLASH_ID`, `MICROPY_HW_SPIFLASH_BAUDRATE` | SPI flash on a SERCOM (SAMD21): `SPIFLASH` is `1`, `_ID` is the SERCOM number |
| `MICROPY_HW_ADC_VREF` | ADC reference when not the default |
| `MICROPY_HW_NINA_*`, `MICROPY_HW_WIFI_*`, `MICROPY_HW_BLE_*` | radio module pins and buses |

The clock decisions are documented in the comment block of `mcu/samd51/clock_config.c` and `mcu/samd21/clock_config.c`. Read it. Without the defines, the part runs from the internal oscillators.

### `pins.csv`

Written by `gen_pins_csv.py`. Style: `<BOARD_NAME>,<Pxn>`. Examples from the seed: `D0,PA16`, `D13,PA22`. The file replaces the seed's. Every pad in `mcu/<series>/pin-af-table.csv` is available by its `Pxn` name. The file adds board names. A row whose board name equals the pad name (`PB08,PB08`) must not be in the file: `make-pins.py` emits `pin_PB08` for the pad and for the board name, and the build fails with `pin_PB08 redefined`. `gen_pins_csv.py` skips such rows on this port; `--keep-self-named` overrides that and is not wanted here.

Default pins for the buses come from board pin names. In `machine_i2c.c`, when `pin_SCL` and `pin_SDA` are defined, they are the defaults for `I2C()`. The same pattern holds for SPI (`SCK`, `MOSI`, `MISO`) and UART (`TX`, `RX`). A board with default buses needs those names in `pins.csv`. A board without them needs `scl`, `sda`, `tx`, `rx` and the SPI pins in every constructor, which is what the generated `hardware.py` passes.

## Clock and power decisions to derive

| Decision | Facts needed | Where it lands |
|---|---|---|
| 32.768 kHz crystal fitted | BOM | `MICROPY_HW_XOSC32K` |
| Crystal disturbed by other signals | schematic, user | `MICROPY_HW_MCU_OSC32KULP` |
| USB device used | schematic | `MICROPY_HW_DFLL_USB_SYNC` |
| Part, flash size, RAM size | part number | `CMSIS_MCU`, `LD_FILES`, `MICROPY_HW_CODESIZE` |
| Bootloader (UF2) | user | `TEXT0` |
| Filesystem: internal flash, QSPI flash, SPI flash | BOM | `MICROPY_HW_QSPIFLASH`, `MICROPY_HW_SPIFLASH*` |
| Default buses | schematic | `MICROPY_HW_DEFAULT_*_ID`, board pin names |
| LED and button pins | schematic | `pins.csv`, `peripherals.json` |
| Radio module | BOM | `MICROPY_HW_NINA_*` and friends |

The CPU clock is a runtime setting of `machine.freq()`. The board files only choose the clock source.

## Pin and alternate-function validity

`mcu/<series lower case>/pin-af-table.csv`. Header `Pin,EIC,ADC0,ADC1,SERCOM1,SERCOM2,TC,TCC1,TCC2` (SAMD51). The comment block at the top of the file explains the encoding. Read it and do not guess. Summary from that block:

- The first column is the chip pad name (`PA16`), not a board pin name.
- `EIC` and `ADC` cells hold a decimal number.
- `SERCOM`, `TC` and `TCC` cells hold the device number in the first digit and the pad number in the second digit. `51` is SERCOM5, pad 1. An empty cell means the signal is not available.
- Rows that do not start with `pa`, `pb`, `pc` or `pd` are ignored.
- The column number is the mux class.

`lint_board.py --port samd` checks that each peripheral pin has the matching SERCOM and pad for the bus id. A SERCOM pad can serve only the roles the port supports:

- SPI (`machine_spi.c`): MOSI and SCK pad pairs (MOSI pad, SCK pad) of (0, 1), (2, 3), (3, 1) or (0, 3) on SAMD21, and (0, 1) or (3, 1) on SAMD51. MISO uses its pad of the same SERCOM.
- UART (`machine_uart.c`): TX is on pad 0, or on pad 0 or 2 on SAMD21. RX uses its pad of the same SERCOM. RTS and CTS use pads 2 and 3.
- I2C: pins come from the SERCOM pads in the table.
- ADC: pads with a number in the `ADC0` or `ADC1` column.
- PWM: pads with a `TC`, `TCC1` or `TCC2` entry.

The bus id in `peripherals.json` is the SERCOM number.

Read the sources in the checkout, because the rules are code. The SERCOM and pad numbers from the table are what the lint uses.

## Machine constructors (verified in `docs/samd/quickref.rst`)

```python
from machine import I2C, SPI, UART, ADC, PWM, Pin

i2c = I2C(2, scl=Pin("SCL"), sda=Pin("SDA"), freq=400_000)
spi = SPI(1, sck=Pin("SCK"), mosi=Pin("MOSI"), miso=Pin("MISO"), baudrate=10_000_000)
uart = UART(3, tx=Pin("D1"), rx=Pin("D0"), baudrate=115200)
adc = ADC(Pin("A0"))  # average=16 by default, 12 bit
pwm = PWM(Pin("D4"), freq=25000)  # see docs/samd/quickref.rst for the pad rules
```

The first positional argument is the SERCOM id. If the id and the pins are omitted, the defaults from `MICROPY_HW_DEFAULT_*_ID` and the default pin names apply. When the frequency or baudrate is given and the id is omitted, it must be a keyword. `miso=None` omits MISO. ADC pads are the ones the board names `Ann`.

## Pitfalls

- Two buses cannot use the same SERCOM. A SERCOM pad pair that suits SPI can conflict with UART on the same SERCOM.
- `TEXT0` and `LD_FILES` must agree with the bootloader that is on the chip. A mismatch builds but does not run.
- `MICROPY_HW_CODESIZE` too small fails the link. Too large reduces the filesystem, and with the bootloader and `MICROPY_HW_ROMFS_BYTES` it can leave none (see the filesystem formula above).
- A pad that the AF table lacks cannot take a peripheral function.
- SAMD21 has less RAM and flash. Network and TLS features do not fit.
- SAMD51 boards with QSPI flash must name the flash part in `MICROPY_HW_QSPIFLASH`. A wrong part causes a failed flash probe.
- A self-named row in `pins.csv` (`PB08,PB08`) fails the build with `pin_PB08 redefined`. `gen_pins_csv.py` leaves such rows out; do not add them by hand.

## Build and verification commands

```bash
make submodules && make system
make libs-only
make tests
make checks
```

`make mboot` does not exist on this port. Firmware lands in `src/system/build-<BOARD>/` (`firmware.bin`, `firmware.elf`, `firmware.uf2`).
