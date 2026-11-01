# esp32 port

Port directory: `ports/esp32`. Board directories: `ports/esp32/boards/<BOARD>/`. Build system: cmake (ESP-IDF). The reference seeds are `ESP32_GENERIC` (files: `board.json`, `board.md`, `mpconfigboard.cmake`, `mpconfigboard.h`, `mpconfigvariant_{D2WD,OTA,SPIRAM,UNICORE}.cmake`, `sdkconfig.{d2wd,ota,unicore}`) and `ESP32_GENERIC_S3` (files: `board.json`, `board.md`, `mpconfigboard.cmake`, `mpconfigboard.h`, `mpconfigvariant_SPIRAM_OCT.cmake`). Neither has a `pins.csv` or a `sdkconfig.board`. Other boards add them: `UM_FEATHERS3`, `LOLIN_S2_MINI`, `SIL_MANT1S`.

## Template answers

| Answer | Value |
|---|---|
| `target_port` | `esp32` |
| `template_board` | the seed. Template default: `ESP32_GENERIC`. Pick the seed that has the same `IDF_TARGET` (`ESP32_GENERIC_S3` for an ESP32-S3, and so on). |
| `project_board_name` | `<PROJECT_NAME_UPPER>_<template_board>` or a chosen upper-case name |
| `use_mboot`, `bootloader_address` | not asked on this port. Do not set them. |

Test answer file: `esp32.copier-answers.yml` (`template_board: ESP32_GENERIC`).

The build container comes from `mpbuild`, and its ESP-IDF version comes from `ports/esp32/lockfiles` in the submodule. Run `make setup` after a submodule bump.

## What the retarget stage edits

All edits are in `src/system/<BOARD>/`.

### `board.json`

`mcu` is the chip (`esp32`, `esp32s2`, `esp32s3`, `esp32c3`, `esp32c6`, ...). `deploy_options.flash_offset` is the first flash offset of the image: `0x1000` for the original ESP32, `0` for the S3 seed. Take the value from the seed and keep it unless the chip differs. Set `product`, `vendor`, `url`, `features` (`BLE`, `WiFi`, `External Flash`, `External RAM`). `variants` lists variant names; each needs a `mpconfigvariant_<NAME>.cmake`. The seed sets `deploy` to `["../deploy.md"]`, a path to `ports/esp32/boards/deploy.md` that the project copy does not have, and `images` to a file name that is not copied. Set `deploy` and `images` to empty lists, or to files that exist in the project.

### `mpconfigboard.cmake`

The seed files are short:

```cmake
include(boards/mpconfigboard_esp32_common.cmake)

list(APPEND SDKCONFIG_DEFAULTS
    boards/sdkconfig.csi)
```

The include sets `IDF_TARGET` and `SDKCONFIG_DEFAULTS` (`boards/sdkconfig.base`, `boards/sdkconfig.ble`, and for S3 `boards/sdkconfig.spiram_quad`). The paths are relative to `ports/esp32`. Board-local files use `${MICROPY_BOARD_DIR}/sdkconfig.board`.

The `ESP32_GENERIC_S3` seed adds `boards/sdkconfig.flash_qio_80m` (QIO flash mode, 80 MHz) and `boards/sdkconfig.csi` after the include. Its common include brings `boards/sdkconfig.spiram_quad`, which enables quad PSRAM with `CONFIG_SPIRAM_IGNORE_NOTFOUND=y`. A module without PSRAM can keep it: the firmware probes for PSRAM at start-up and continues when none answers, and a project built from this seed for a module without PSRAM, with those files kept, builds. A module with octal PSRAM uses the seed's `SPIRAM_OCT` variant (`mpconfigvariant_SPIRAM_OCT.cmake`). `sdkconfig.flash_qio_80m` must match the module's flash chip; take the flash mode and speed from the module datasheet and state them as an item to confirm.

| Setting | Rule |
|---|---|
| `include(boards/mpconfigboard_<target>_common.cmake)` | one include per target. Files in the tree: `esp32`, `esp32c2`, `esp32c3`, `esp32c5`, `esp32c6`, `esp32h2`, `esp32p4`, `esp32s2`, `esp32s3`. Must match the chip. |
| `SDKCONFIG_DEFAULTS` additions | `boards/sdkconfig.flash_qio_80m` (QIO 80 MHz flash), `boards/sdkconfig.flash_2MiB`, `boards/sdkconfig.240mhz`, `boards/sdkconfig.spiram_esp32` (original ESP32 PSRAM), `boards/sdkconfig.spiram_quad` (quad PSRAM on S2, S3, C5), `boards/sdkconfig.spiram_oct` (octal PSRAM on S3), `boards/sdkconfig.ble`, `boards/sdkconfig.csi`, `boards/sdkconfig.free_ram` |
| `${MICROPY_BOARD_DIR}/sdkconfig.board` | project-specific ESP-IDF settings: flash size, partition table, hostname |
| `MICROPY_DEF_BOARD` | `list(APPEND MICROPY_DEF_BOARD MICROPY_HW_BOARD_NAME="...")` sets C defines from cmake (used by variants) |
| `MICROPY_FROZEN_MANIFEST` | leave. The project include sets it. |

Leave the appended `include(${MICROPY_BOARD_DIR}/../mpconfigproj.cmake)` line in place.

### `sdkconfig.board`

Create it when the board needs settings that no shared `sdkconfig.*` file in `ports/esp32/boards/` provides. Pattern from `SIL_MANT1S` and `UM_FEATHERS3` (the partition file named here is one of the port's shared tables; `SIL_MANT1S` keeps its own file under `boards/`):

```text
CONFIG_ESPTOOLPY_FLASHSIZE_4MB=
CONFIG_ESPTOOLPY_FLASHSIZE_8MB=y
CONFIG_ESPTOOLPY_FLASHSIZE_16MB=
CONFIG_ESPTOOLPY_FLASHSIZE="8MB"
CONFIG_PARTITION_TABLE_CUSTOM=y
CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="partitions-8MiBplus-ota.csv"
CONFIG_LWIP_LOCAL_HOSTNAME="MyBoard"
```

`sdkconfig.base` defaults to 4 MB flash and `partitions-4MiBplus.csv`. Partition tables in `ports/esp32`: `partitions-2MiB.csv`, `partitions-4MiB-ota.csv`, `partitions-4MiB-romfs.csv`, `partitions-4MiBplus.csv`, `partitions-8MiBplus-ota.csv`. Use one of these. The IDF project directory is `ports/esp32`, so a partition file name must resolve from there. If the flash size has no matching table, tell the user; do not make up offsets. The block above (8 MB flash, `partitions-8MiBplus-ota.csv`) is the complete `sdkconfig.board` of an 8 MB module without PSRAM; with 4 MB flash the three `CONFIG_ESPTOOLPY_FLASHSIZE*` lines and the partition lines change to the 4 MB values and table.

The flash mode and frequency (`CONFIG_ESPTOOLPY_FLASHMODE_*`, `CONFIG_ESPTOOLPY_FLASHFREQ_*`) depend on the flash chip and on the module. State them as items to confirm.

### `mpconfigboard.h`

| Macro | Rule |
|---|---|
| `MICROPY_HW_BOARD_NAME` | set the name part; keep the `<PROJECT>-` prefix. The seed wraps it in `#ifndef`; keep the `#define` that the template edited. |
| `MICROPY_HW_MCU_NAME` | the chip name, for example `"ESP32-S3"` |
| `MICROPY_HW_I2C0_SCL`, `_SDA`, `MICROPY_HW_I2C1_*` | default I2C pins (S3 seed: `9` and `8`) |
| `MICROPY_HW_SPI1_SCK`, `_MOSI`, `_MISO`, `MICROPY_HW_SPI2_*` | default SPI pins |
| `MICROPY_HW_ENABLE_UART_REPL` | `1` when the console goes through an external USB-UART bridge and not native USB |
| `MICROPY_HW_ENABLE_USBDEV` | native USB device. Set from the chip's USB support and the schematic. |
| `MICROPY_HW_USB_VID`, `_PID`, `_MANUFACTURER_STRING`, `_PRODUCT_FS_STRING` | remove values that belong to the seed's vendor. The template leaves USB IDs alone on purpose. |
| `MICROPY_HW_SDCARD_SPI_SCK`, `_MOSI`, `_MISO`, `_CS` | SD card on SPI |
| `MICROPY_PY_NETWORK_HOSTNAME_DEFAULT` | default hostname |

### `pins.csv`

Optional on this port. The cmake file uses it only when it exists. Style: `<BOARD_NAME>,GPIO<n>`. Example from `UM_FEATHERS3`: `I2C_SCL,GPIO9`, `LED_BLUE,GPIO13`, `UART0_TX,GPIO43`. Written by `gen_pins_csv.py`. The file only adds board names; every GPIO is available as `Pin(<n>)` and as `GPIO<n>` whether listed or not, and an integer GPIO on a pad with no board name needs no row. `make-pins.py` accepts `GPIO<n>` names below its `NUM_GPIOS` (55 in this tree); pads at or above the limit in `ports/esp32/boards/make-pins.py` are rejected at build time, and the lint reads that limit when it has `--micropython`. With a `pins.csv`, `Pin("NAME")` and `Pin.board.NAME` work. Generated `device_config.py` uses integer GPIO numbers on this port.

A row whose board name equals the pad name (`GPIO4,GPIO4`) must not be in the file. `make-pins.py` already emits `#define pin_GPIO4 (&machine_pin_obj_table[GPIO_NUM_4])` for the pad; the board-name row adds `#define pin_GPIO4 pin_GPIO4`, which redefines it as a reference to itself, and `pins.c` fails with `'pin_GPIO4' undeclared`. `gen_pins_csv.py` skips such rows on this port.

## Clock and power decisions to derive

The ESP-IDF handles the clock tree. MicroPython needs flash, memory and pin facts.

| Decision | Facts needed | Where it lands |
|---|---|---|
| Chip and variant (`esp32`, `esp32s3`, ...) | part number, module name | `IDF_TARGET` through the common include, `board.json` |
| Flash size | module datasheet | `sdkconfig.board`, partition table |
| Flash mode and speed | module datasheet | `boards/sdkconfig.flash_qio_80m` or `sdkconfig.board` |
| PSRAM: none, quad, octal; size | module datasheet | `boards/sdkconfig.spiram_*` |
| Module or bare chip | BOM | determines which GPIOs are used by flash and PSRAM |
| USB: native device, UART bridge | schematic | `MICROPY_HW_ENABLE_USBDEV`, `MICROPY_HW_ENABLE_UART_REPL` |
| Crystal frequency | BOM | `CONFIG_XTAL_FREQ_AUTO=y` in `sdkconfig.base` detects it. Set explicitly only when the chip needs it. |
| SD card (SPI or SDMMC) | schematic | `MICROPY_HW_SDCARD_SPI_*` |
| LED and button pins | schematic | `pins.csv`, `peripherals.json` |
| BLE, WiFi | chip features | `boards/sdkconfig.ble`, `board.json` features |
| Power-enable or reset pins for external parts | schematic | `peripherals.json` (GPIO) |

## Pin and alternate-function validity

esp32 has no AF table. The GPIO matrix routes most peripheral signals to any GPIO, so the only checks that `lint_board.py --port esp32` makes are name format (`GPIO<n>`) and uniqueness. It lists peripheral checks under `unchecked` with the reason.

These limits are not in the tree as a table. Confirm each from the chip datasheet (the technical reference and the GPIO table) for the exact chip and module. Do not rely on a list from memory. `docs/esp32/quickref.rst` states them for the original ESP32 only:

- Input-only GPIOs: the quickref says pins 34 to 39 on the original ESP32, with no internal pull-up. Confirm the set for the actual chip.
- Strapping pins: pads that set boot mode, flash voltage or boot log level while reset is released. A load or a driver on a strapping pad can stop the chip from booting. Confirm which pads strap on the chip and what the schematic does to them.
- Flash and PSRAM pads: the quickref says GPIOs 6, 7, 8, 11, 16 and 17 connect the embedded flash on the original ESP32. Octal PSRAM and some modules use more pads. Confirm from the module datasheet.
- USB and JTAG pads (S2, S3, C3, C6): confirm which GPIOs belong to native USB and the USB serial JTAG.
- ADC2 and Wi-Fi: the quickref says ADC block 2 cannot be read while Wi-Fi is active on the original ESP32. Confirm for the chip, and tell the user which ADC pins of the design are on that block.
- ADC-capable pads: the quickref lists pins 32 to 39 (block 1) and 0, 2, 4, 12 to 15, 25 to 27 (block 2) for the original ESP32. Confirm for the chip.
- Console pins: GPIO 1 and 3 (original ESP32) are the REPL UART.

Raise each as an item in `clock-power.md` or the open questions. Flag every peripheral pin that sits on a pad the datasheet marks input-only, strapping, flash or PSRAM.

## Machine constructors (verified in `docs/esp32/quickref.rst`)

```python
from machine import I2C, SPI, UART, ADC, PWM, Pin

i2c = I2C(1, scl=Pin(5), sda=Pin(4), freq=400000)
spi = SPI(2, baudrate=1000000, sck=Pin(18), mosi=Pin(23), miso=Pin(19))
uart = UART(1, baudrate=115200, tx=Pin(33), rx=Pin(32))
adc = ADC(Pin(32))
pwm = PWM(Pin(15), freq=25000, duty_u16=32768)
```

Hardware I2C ids are 0 and 1. SPI ids are 1 (HSPI) and 2 (VSPI) on the original ESP32; the chip's SPI host list differs on other chips. UART ids are 0, 1 and 2 on the original ESP32. Any GPIO works for UART through the matrix; the quickref notes that input-only pins can only be `rx`. SPI on non-default pins is limited to 40 MHz. `SoftI2C` and `SoftSPI` work on any pin. PWM works on any output-capable pin.

## Pitfalls

- Pads that are input-only cannot drive chip selects, enables or LEDs.
- A strapping pad that a peripheral pulls at reset changes the boot mode.
- A partition table that does not match the flash size builds but does not boot.
- ADC readings on block 2 pads fail while Wi-Fi is active.
- Octal PSRAM takes extra pads that the module datasheet names.
- A self-named `pins.csv` row (`GPIO4,GPIO4`) makes `pin_GPIO4` refer to itself and fails the build in `pins.c`. `gen_pins_csv.py` leaves such rows out.
- The container image for esp32 is large. On a cold machine the scaffold and the first `make submodules` can take about 30 minutes, because of the image pull. Run them in the background. `make system` after that takes minutes.

## Build and verification commands

```bash
make submodules && make system
make libs-only
make tests
make checks
```

`make mboot` does not exist on this port. Firmware lands in `src/system/build-<BOARD>/` (`firmware.bin`, `bootloader/bootloader.bin`, `partition_table/partition-table.bin`).
