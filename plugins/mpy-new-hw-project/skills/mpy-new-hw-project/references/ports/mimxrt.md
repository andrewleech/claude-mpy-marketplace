# mimxrt port

Port directory: `ports/mimxrt`. Board directories: `ports/mimxrt/boards/<BOARD>/`. Build system: make. The reference seeds are `TEENSY40` (files: `board.json`, `format.py`, `mpconfigboard.h`, `mpconfigboard.mk`, `pins.csv`) and `MIMXRT1060_EVK` (files: `board.json`, `board.md`, `manifest.py`, `mpconfigboard.h`, `mpconfigboard.mk`, `pins.csv`).

## Template answers

| Answer | Value |
|---|---|
| `target_port` | `mimxrt` |
| `template_board` | the seed. Template default: `TEENSY40`. Pick a seed with the same `MCU_SERIES`. `pick_seed.py` can rank several boards as exact matches for one `MCU_VARIANT` (`TEENSY40`, `TEENSY41` and `MIMXRT1060_EVK` all use `MIMXRT1062DVJ6A`). Choose by features: the seed whose flash, SDRAM, Ethernet, SD card and CAN set is closest to the design needs the fewest removals. `TEENSY40` has 2 MB QSPI flash, an SD card and CAN, and no SDRAM or Ethernet. `MIMXRT1060_EVK` has 8 MB QSPI flash, SDRAM and Ethernet. |
| `project_board_name` | `<PROJECT_NAME_UPPER>_<template_board>` or a chosen upper-case name |
| `use_mboot`, `bootloader_address` | not asked on this port. Do not set them. |

The port has no answer file in the template's test set. The generated project follows the same pattern as the other make-based ports.

## What the retarget stage edits

All edits are in `src/system/<BOARD>/`.

### `board.json`

`mcu` is the literal `mimxrt` for every board. Set `product`, `vendor`, `url` and `features` (`USB`, `External Flash`, `External RAM`, `Ethernet`, `CAN`, `microSD`, ...), and set `images` and `deploy` to empty lists or to files that exist in the project. The seed's `images` entry is a file name that the project copy does not have.

### `mpconfigboard.mk`

| Variable | Rule |
|---|---|
| `MCU_SERIES` | chip series: `MIMXRT1011`, `MIMXRT1015`, `MIMXRT1021`, `MIMXRT1052`, `MIMXRT1062`, `MIMXRT1064`, `MIMXRT1176`. It selects `boards/<MCU_SERIES>_af.csv`, `boards/<MCU_SERIES>.ld` and `boards/<MCU_SERIES>_clock_config.c`. |
| `MCU_VARIANT` | exact device, for example `MIMXRT1062DVJ6A`. Becomes `-DCPU_<variant>` and the J-Link device name. |
| `MICROPY_FLOAT_IMPL` | `double` or `single` |
| `MICROPY_HW_FLASH_TYPE` | `qspi_nor_flash`, `qspi_hyper_flash` or `internal` (`MIMXRT1064_EVK`, internal flash). Selects the FlexSPI driver (`hal/flexspi_nor_flash.c` or `hal/flexspi_hyper_flash.c`). |
| `MICROPY_HW_FLASH_SIZE` | bytes, for example `0x200000` (2 MB) or `0x800000` (8 MB) |
| `MICROPY_HW_FLASH_RESERVED` | bytes at the start of flash reserved for the bootloader or other cores. The `TEENSY40` and `TEENSY41` seeds set `MICROPY_HW_FLASH_RESERVED ?= 0x1000` for the Teensy bootloader; remove it unless the design carries the same bootloader. `0x100000` on RT1170 boards. |
| `MICROPY_HW_FLASH_CLK` | FlexSPI clock, for example `kFlexSpiSerialClk_133MHz`. Take it from the flash chip's maximum. |
| `MICROPY_HW_FLASH_QE_CMD`, `MICROPY_HW_FLASH_QE_ARG` | quad-enable command and argument. They depend on the flash chip's status register layout: the seeds use `0x31`/`0x02` and `0x01`/`0x40`. Take the pair from the flash chip datasheet. |
| `MICROPY_HW_BOARD_FLASH_FILES` | set to `1` when the board carries its own `<flash type>_config.c` and `<BOARD>_flexspi_flash_config.h` (a flash chip that the shared `hal/` config does not cover) |
| `MICROPY_HW_SDRAM_AVAIL`, `MICROPY_HW_SDRAM_SIZE` | external SDRAM through SEMC. Set both, or neither. |
| `MICROPY_HW_ROMFS_BYTES` | ROM filesystem size. `0` for Hyperflash boards. |
| `USE_UF2_BOOTLOADER` | `1` when the board ships the TinyUF2 bootloader (the `TEENSY40`, `TEENSY41` and `MIMXRT1060_EVK` seeds set `1`). Set `0` when the design has no UF2 bootloader. Hyperflash boards set `0`. |
| `MICROPY_PY_LWIP`, `MICROPY_PY_SSL`, `MICROPY_SSL_MBEDTLS` | network features. Keep those the hardware supports. |
| `FROZEN_MANIFEST` | leave. The project include sets it. |
| `deploy` targets (`deploy_jlink`, `JLINK_PATH`) and `JLINK_*` | seed-specific flashing recipes. Remove or adapt. Flashing is out of scope here. |

Leave the appended `include $(BOARD_DIR)/../mpconfigproj.mk` line in place.

### `mpconfigboard.h`

| Macro | Rule |
|---|---|
| `MICROPY_HW_BOARD_NAME` | set the name part; keep the `<PROJECT>-` prefix |
| `MICROPY_HW_MCU_NAME` | device name (equals `MCU_VARIANT` in the seeds) |
| `MICROPY_HW_LED1_PIN`, `MICROPY_HW_LED_ON(pin)`, `MICROPY_HW_LED_OFF(pin)` | LED pad and polarity. `TEENSY40` drives high to switch on; `MIMXRT1060_EVK` drives low. |
| `MICROPY_HW_NUM_PIN_IRQS` | `(4 * 32 + 3)` for the 1060-class chips. Keep the seed value for the same series. |
| `MICROPY_HW_UART_INDEX`, `MICROPY_HW_UART_NUM`, `IOMUX_TABLE_UART`, `IOMUX_TABLE_UART_CTS_RTS` | UART map, see below |
| `MICROPY_HW_SPI_INDEX`, `IOMUX_TABLE_SPI`, `DMA_REQ_SRC_RX`, `DMA_REQ_SRC_TX` | SPI map |
| `MICROPY_HW_I2C_INDEX`, `IOMUX_TABLE_I2C` | I2C map |
| `MICROPY_HW_CAN*_NAME`, `MICROPY_HW_NUM_CAN`, `MICROPY_HW_CAN_INDEX`, `MICROPY_HW_NUM_CAN_IRQS`, `IOMUX_TABLE_CAN`, `MICROPY_HW_CAN_IS_RESERVED(can_id)` | CAN map. Do not remove it on `MIMXRT1021`, `MIMXRT1052`, `MIMXRT1062`, `MIMXRT1064` and `MIMXRT1176`, see below. |
| `MICROPY_PY_MACHINE_I2S`, `MICROPY_HW_I2S_NUM`, `I2S_GPIO_MAP`, `I2S_*` | I2S map |
| `MICROPY_USDHC1`, `USDHC_DUMMY_PIN` | SD card pads. Removing `MICROPY_USDHC1` also needs `#define MICROPY_PY_MACHINE_SDCARD (0)`. `mpconfigport.h` defaults it to `1`, and the port then builds the SD card code, which needs a `MICROPY_USDHC1` or `MICROPY_USDHC2` pad table. Seeds without an SD card set it to `(0)` (`MIMXRT1010_EVK`, `ADAFRUIT_METRO_M7`). |
| `MIMXRT_IOMUXC_SEMC_*` | SDRAM pads (only with `MICROPY_HW_SDRAM_AVAIL`) |
| `ENET_PHY_ADDRESS`, `ENET_PHY_OPS`, `IOMUX_TABLE_ENET`, `MICROPY_PY_NETWORK_HOSTNAME_DEFAULT` | Ethernet PHY |

The IOMUX tables use SDK macros of the form `IOMUXC_<pad>_<signal>`, for example `IOMUXC_GPIO_AD_B1_00_LPI2C1_SCL`. The tables are indexed in hardware order, not in logical order:

- `IOMUX_TABLE_UART` has two entries (TX then RX) for each hardware UART from LPUART1 up. An unused UART is `{ 0 }, { 0 }`. `IOMUX_TABLE_UART_CTS_RTS` has the same layout.
- `MICROPY_HW_UART_INDEX` maps each logical `UART(n)` to a hardware UART number. The position in the list is `n`. A `0` entry means there is no such logical UART. `UART()` without an id uses id 1 (`DEFAULT_UART_ID` in `machine_uart.c`), so position 0 holds a `0` placeholder and the first real UART is `UART(1)`. A design with LPUART2 as its only UART uses `{ 0, 2 }`: `UART(0)` does not exist and `UART(1)` is LPUART2. `TEENSY40` uses `{ 0, 6, 4, 2, 3, 8, 1, 7 }`, so `UART(1)` is LPUART6. `MIMXRT1060_EVK` uses `{ 1, 3, 2, 6, 8 }`, which makes `UART(0)` LPUART1 and leaves `UART(1)` as LPUART3.
- `MICROPY_HW_SPI_INDEX` and `MICROPY_HW_I2C_INDEX` map `SPI(n)` and `I2C(n)` the same way, with no placeholder: `{ 4 }` makes `SPI(0)` LPSPI4, `{ 1 }` makes `I2C(0)` LPI2C1. The SPI table has five entries per hardware LPSPI (SCK, PCS0, SDO, SDI, PCS1). The I2C table has two entries (SCL then SDA) per hardware LPI2C.
- `bus_id` in `peripherals.json` is the position in the index table, not the hardware instance. For the examples above the LPUART2 console has `bus_id` 1, the LPSPI4 bus has `bus_id` 0 and the LPI2C1 bus has `bus_id` 0.
- Each pad and signal pair must exist in the AF file. Use the macro names the NXP SDK defines in `lib/nxp_driver/sdk/devices/<MCU_SERIES>/drivers/fsl_iomuxc.h` (path in the checkout). The AF file and the SDK spell some signals differently. AF file: `LPSPI4_SCK`, `LPSPI4_SOUT` (MOSI), `LPSPI4_SIN` (MISO), `LPUART2_TXD`, `LPUART2_RXD`. SDK macros: `IOMUXC_GPIO_B0_02_LPSPI4_SDO`, `..._SDI`, `IOMUXC_GPIO_AD_B1_02_LPUART2_TX`, `..._RX`. Find the pad in the AF file, then take the macro from `fsl_iomuxc.h`.
- The lint parses `IOMUX_TABLE_UART`, `IOMUX_TABLE_SPI` and `IOMUX_TABLE_I2C`: a pin of `peripherals.json` that the table does not route is an error, and a missing table is listed under `unchecked`. It does not check unused entries, `IOMUX_TABLE_UART_CTS_RTS`, `IOMUX_TABLE_CAN`, the I2S map or the SDRAM pads. Confirm those by hand. A seed row can clash with another bus: the seed's LPUART2 CTS/RTS entries use `GPIO_AD_B1_00` and `GPIO_AD_B1_01`, which are also the LPI2C1 SCL and SDA pads. Replace CTS/RTS entries of UARTs that the design does not use with `{ 0 }`.

CAN cannot be removed on `MIMXRT1021`, `MIMXRT1052`, `MIMXRT1062`, `MIMXRT1064` and `MIMXRT1176`. The port Makefile sets `MICROPY_PY_MACHINE_CAN = 1` for them, so `machine_can.c` is always built and needs `MICROPY_HW_CAN_INDEX`, `MICROPY_HW_NUM_CAN_IRQS` and `IOMUX_TABLE_CAN`, and `extmod/machine_can.c` needs `MICROPY_HW_NUM_CAN`. For a board without a CAN transceiver keep all of them as in the seed, mark every controller reserved with `MICROPY_HW_CAN_IS_RESERVED` so the application cannot open it, and route no pad. Example for the two controllers of `TEENSY40`:

```c
#define MICROPY_HW_CAN1_NAME "CAN1"
#define MICROPY_HW_CAN2_NAME "CAN2"
#define MICROPY_HW_NUM_CAN (2)
#define MICROPY_HW_CAN_INDEX { 1, 2 }
#define MICROPY_HW_NUM_CAN_IRQS (2)
#define MICROPY_HW_CAN_IS_RESERVED(can_id) (true)

#define IOMUX_TABLE_CAN \
    { 0 }, { 0 }, \
    { 0 }, { 0 },
```

Remove every table entry, I2S map line, USDHC pad and `MIMXRT_IOMUXC_SEMC_*` line that names a pad the new board does not use. Replace removed table entries with `{ 0 }`, so the tables keep their size. The CAN macros stay (see above).

The seed's comments (`// SDA/SCL HW-I2C Logical I2C`) describe the seed's wiring. Update them to the new wiring.

### `pins.csv`

Written by `gen_pins_csv.py`. Style: `<BOARD_NAME>,<pad>`. Examples from `TEENSY40`: `D0,GPIO_AD_B0_03`, `LED,GPIO_B0_03`. The file replaces the seed's. Every pad in `<MCU_SERIES>_af.csv` is implicitly available by its pad name. The file only adds board names. A row whose board name equals the pad name (`GPIO_B0_03,GPIO_B0_03`) must not be in the file: the pad already has `pin_GPIO_B0_03`, and the second definition fails the build. `gen_pins_csv.py` skips such rows on this port. A pin in `peripherals.json` that names such a pad uses the pad name.

### Board files per flash chip

`TEENSY40`, `MIMXRT1060_EVK` and most boards use the shared FlexSPI configuration in `ports/mimxrt/hal/`. A board with an unusual flash chip sets `MICROPY_HW_BOARD_FLASH_FILES = 1` and carries its own config files. Use the shared configuration unless the flash chip needs different lookup tables. State this as an item to confirm from the flash datasheet.

## Clock and power decisions to derive

| Decision | Facts needed | Where it lands |
|---|---|---|
| Crystal | BOM | The port fixes it per series: `BOARD_XTAL0_CLK_HZ` is 24 MHz and `BOARD_XTAL32K_CLK_HZ` is 32768 Hz in `boards/<MCU_SERIES>_clock_config.h`. A different crystal needs port code. Raise it to the user. |
| Core clock | the series defaults | `boards/<MCU_SERIES>_clock_config.c` is shared by all boards of the series. Do not edit it per board. |
| Boot flash: type, size, clock, QE command | BOM, flash datasheet | `MICROPY_HW_FLASH_*` |
| Reserved flash | bootloader choice | `MICROPY_HW_FLASH_RESERVED` |
| SDRAM size | BOM | `MICROPY_HW_SDRAM_*`, `MIMXRT_IOMUXC_SEMC_*` |
| UF2 bootloader | user | `USE_UF2_BOOTLOADER` |
| UARTs, SPI, I2C, CAN, I2S, SD, Ethernet used | schematic | IOMUX tables, index tables |
| LED and polarity | schematic | `MICROPY_HW_LED1_PIN`, `MICROPY_HW_LED_ON/OFF` |
| Power rails controlled by firmware | schematic | `peripherals.json` (GPIO) |

## Pin and alternate-function validity

`boards/<MCU_SERIES>_af.csv` (header `Pad,ALT0..ALT9,ADC,ACMP,Default`). Each row is one pad. Cells hold signals such as `LPI2C1_SCL`, `LPSPI4_SCK`, `LPSPI4_SOUT` (MOSI), `LPSPI4_SIN` (MISO), `LPUART2_TXD` and `LPUART2_RXD`. Read the file for the exact spelling. The `Default` column names the ALT that selects GPIO.

`lint_board.py --port mimxrt` checks:

- `pins.csv` port names exist as `Pad` rows, and no row has a board name equal to its pad name;
- for each peripheral pin (a board name from `pins.csv` or a pad name), the signal exists on that pad;
- the `ADC` column has a value for an ADC pin.

By hand: `grep -n '^GPIO_AD_B1_00' ports/mimxrt/boards/MIMXRT1062_af.csv`.

The IOMUX tables in `mpconfigboard.h` decide which pads the buses use. The generated `hardware.py` uses `I2C(id)`, `SPI(id)` and `UART(id)` with no pin arguments, so the ids in `peripherals.json` must match the index tables (the id is the position in `MICROPY_HW_<BUS>_INDEX`). The lint checks that the pins of each peripheral match the AF signals of the hardware instance for that id, and that the used IOMUX table routes them. Other table entries are not checked, see above.

## Machine constructors (verified in `docs/mimxrt/quickref.rst`)

```python
from machine import I2C, SPI, UART, ADC, PWM, Pin

i2c = I2C(0, 400_000)  # or I2C(0, freq=400_000); pins fixed by IOMUX_TABLE_I2C
spi = SPI(0, 10_000_000)  # or SPI(0, baudrate=...); pins fixed by IOMUX_TABLE_SPI
uart = UART(1, baudrate=115200)  # pins fixed by IOMUX_TABLE_UART
adc = ADC(Pin("A2"))  # pad needs an ADC cell in the AF file
pwm = PWM(Pin("D2"), freq=25000)  # see docs/mimxrt/quickref.rst for the pad rules
cs = Pin("D6", Pin.OUT, value=1)  # chip select as plain GPIO
```

When `id` is omitted, `I2C`, `SPI` use id 0 and `UART` uses id 1, and the other parameter must be a keyword. The keyword `cs=n` on `SPI` enables automatic chip select 0 or 1. The default `cs=-1` leaves chip select to the script. `SoftI2C` and `SoftSPI` work on any pin. ADC pads are the ones the board labels `Ann`.

## Pitfalls

- A bus works only for ids that have a non-zero entry in its `MICROPY_HW_*_INDEX` table and non-zero IOMUX entries.
- IOMUX table sizes must stay at the full layout. Delete entries by replacing them with `{ 0 }`.
- The index tables are positions, not hardware numbers: `MICROPY_HW_UART_INDEX { 0, 2 }` makes LPUART2 `UART(1)`, so `bus_id` is 1.
- Seed entries left in the tables can route a pad that the design uses for another function. Check the remaining entries (CTS/RTS, other LPUARTs, other LPI2C and LPSPI instances) against the pads the design uses.
- A pad-named net is not in `pins.csv`, so `Pin.board` in the unix tests does not list it. The generated tests do not check pad-form pin values against `Pin.board`.
- A wrong `MICROPY_HW_FLASH_QE_CMD` or `MICROPY_HW_FLASH_CLK` builds but does not boot, or the flash is slow or unreliable.
- `MICROPY_HW_FLASH_SIZE` must match the fitted flash. The filesystem is sized from it.
- Teensy-style and UF2 boards may expect a bootloader in the first flash bytes (`MICROPY_HW_FLASH_RESERVED`).
- The USB device pads are fixed for the chip. A board with no USB cannot use REPL over USB; tell the user how the console is reached.

## Build and verification commands

```bash
make submodules && make system
make libs-only
make tests
make checks
```

`make mboot` does not exist on this port. Firmware lands in `src/system/build-<BOARD>/` (`firmware.bin`, `firmware.hex`, and `firmware.uf2` with `USE_UF2_BOOTLOADER`).
