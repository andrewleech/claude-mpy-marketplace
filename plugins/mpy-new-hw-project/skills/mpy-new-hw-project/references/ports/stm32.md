# stm32 port

Port directory: `ports/stm32`. Board directories: `ports/stm32/boards/<BOARD>/`. Build system: make. Template files: `mpconfigboard.mk`, `mpconfigboard.h`, `pins.csv`, `stm32*_hal_conf.h`, optional `board_init.c`, `bdev.c`. The reference seed in this document is `NUCLEO_F767ZI` (files: `board.json`, `board_init.c`, `manifest.py`, `mpconfigboard.h`, `mpconfigboard.mk`, `pins.csv`, `stm32f7xx_hal_conf.h`).

## Template answers

| Answer | Value |
|---|---|
| `target_port` | `stm32` |
| `template_board` | the seed from `pick_seed.py`. Template default: `PYBV11`. |
| `project_board_name` | `<PROJECT_NAME_UPPER>_<template_board>` or a chosen upper-case name |
| `use_mboot` | `true` when the product uses the mboot bootloader, else `false` |
| `bootloader_address` | with `use_mboot`: flash address of mboot, default `0x08000000` |

Test answer files: `stm32-mboot.copier-answers.yml` (`use_mboot: true`, `bootloader_address: '0x08000000'`) and `stm32-no-mboot.copier-answers.yml` (`use_mboot: false`).

## What the retarget stage edits

All edits are in `src/system/<BOARD>/`.

### `board.json`

Set `mcu` to the family (`stm32f7`), `product`, `vendor` (the project's company), `url`, `features`. Set `images` and `thumbnail` to empty values when the files do not exist in the project. Set `deploy` to an empty list or to deploy notes that exist in the project. Keep the key set.

### `mpconfigboard.mk`

| Variable | Rule |
|---|---|
| `MCU_SERIES` | family: `f0`, `f4`, `f7`, `g0`, `g4`, `h5`, `h7`, `l0`, `l1`, `l4`, `n6`, `u5`, `wb`, `wl`. It selects `boards/stm32<series>xx_hal_conf_base.h`. |
| `CMSIS_MCU` | the device define of the exact part, for example `STM32F767xx`. It must exist in the CMSIS headers in `lib/stm32lib`. |
| `AF_FILE` | `boards/stm32<xxx>_af.csv` for the part. List `ports/stm32/boards/*_af.csv` and pick the file that covers the part. |
| `LD_FILES` | `boards/<mcu>.ld` plus a common file (`common_basic.ld`, `common_ifs.ld`, `common_bl.ld`, `common_blifs.ld`). The first file defines `MEMORY` (`FLASH`, `FLASH_APP`, `FLASH_FS`, `FLASH_TEXT`, `RAM`). Compare its sizes to the part's flash and RAM. Use another existing `.ld` file when it matches the part; stm32 boards in the tree use files under `boards/` only. |
| `TEXT0_ADDR`, `TEXT1_ADDR` | where the firmware sits. `TEXT0_ADDR` MUST equal the `ORIGIN` of the region that the linker file puts the vector table in: `FLASH_TEXT` for `common_ifs.ld` and `common_blifs.ld`, `FLASH_APP` for `common_bl.ld`. The Makefile uses `TEXT0_ADDR` for `MICROPY_HW_VTOR` and for the DFU and hex addresses, not for the link, so a mismatch builds and does not boot. In `stm32f767.ld` `FLASH_TEXT` starts at `0x08020000`, so `stm32f767.ld` with `common_blifs.ld` needs `TEXT0_ADDR = 0x08020000`. The `common_bl.ld` example in `ports/stm32/mboot/README.md` (`TEXT0_ADDR = 0x08008000`) is another layout: there the code starts at `FLASH_APP` (`0x08008000` in `stm32f767.ld`), which overlaps `FLASH_FS`. With `common_ifs.ld` the interrupt vectors and code split between `TEXT0_ADDR` and `TEXT1_ADDR`. Read the `ORIGIN` from the `.ld` file in use, and keep the pair consistent with the flash sector boundaries of the part. |
| `MICROPY_FLOAT_IMPL` | `single` or `double`, by FPU of the part |
| `OPENOCD_CONFIG`, `USE_PYDFU`, `BOOTLOADER_DFU_USB_*` | flash tool settings. Change only with the user's programming method in view. |
| `MICROPY_VFS_LFS2`, `MICROPY_PY_LWIP`, `MICROPY_PY_SSL`, `MICROPY_SSL_MBEDTLS`, `MICROPY_PY_BLUETOOTH` | features. Keep those the hardware supports. Remove networking features when the board has no network path. |
| `MICROPY_HW_ENABLE_ISR_UART_FLASH_FUNCS_IN_RAM` | keep for parts that need it (seed boards of the same family set it) |
| `FROZEN_MANIFEST` | leave. The project include sets it to `$(BOARD_DIR)/manifest.py`. |

Leave the appended `include $(BOARD_DIR)/../mpconfigproj.mk` line in place.

### mboot (`use_mboot: true`)

`mpconfigproj.mk` sets `USE_MBOOT = 1`. A seed board must then use the mboot link layout. Boards that support it carry a conditional, as in `PYBV11` and `NUCLEO_H743ZI`:

```make
ifeq ($(USE_MBOOT),1)
LD_FILES = boards/stm32f405.ld boards/common_blifs.ld
TEXT0_ADDR = 0x08020000
else
LD_FILES = boards/stm32f405.ld boards/common_ifs.ld
TEXT0_ADDR = 0x08000000
TEXT1_ADDR = 0x08020000
endif
```

`NUCLEO_F767ZI` has no such conditional. If the seed has none, add it. Pick `common_bl.ld` or `common_blifs.ld` to match the non-mboot file (`common_basic.ld` becomes `common_bl.ld`; `common_ifs.ld` becomes `common_blifs.ld`), and set `TEXT0_ADDR` to the `ORIGIN` of `FLASH_TEXT` (`common_blifs.ld`) or `FLASH_APP` (`common_bl.ld`) in the `.ld` file, which is a flash sector boundary after the bootloader region. The bootloader needs 16 KiB to 32 KiB depending on features, and mboot sits at `bootloader_address`. Take the sector layout from the part's reference manual. State it as an item to confirm.

The mboot version footer is in the template files `mboot_footer.c` and `mboot_footer.ld` in the board directory. Leave them in place. Mboot options (`MBOOT_I2C_*`, `MBOOT_BOOTPIN_*`, `MBOOT_SPIFLASH_*`, `MBOOT_FSLOAD`) go in `mpconfigboard.h`. See `ports/stm32/mboot/README.md` in the checkout. Add them only when the hardware has the matching pins or memory.

### `mpconfigboard.h`

| Macro | Rule |
|---|---|
| `MICROPY_HW_BOARD_NAME` | set the name part; keep the `<PROJECT>-` prefix the template added |
| `MICROPY_HW_MCU_NAME` | the part's name |
| `MICROPY_HW_HAS_SWITCH` | `1` only when a user button is defined |
| `MICROPY_HW_HAS_FLASH`, `MICROPY_HW_ENABLE_INTERNAL_FLASH_STORAGE` | internal or external flash storage |
| `MICROPY_HW_ENABLE_RNG`, `_RTC`, `_DAC`, `_USB`, `_SDCARD`, `_SERVO` | peripherals the part has and the board uses |
| `MICROPY_HW_RTC_USE_LSE`, `MICROPY_HW_RTC_USE_BYPASS` | RTC source, see clock decisions |
| `MICROPY_HW_CLK_PLLM`, `_PLLN`, `_PLLP`, `_PLLQ` (and `_PLLR` on some families) | PLL settings |
| `MICROPY_HW_CLK_USE_BYPASS`, `MICROPY_HW_CLK_USE_HSI`, `MICROPY_HW_CLK_USE_HSI48` | clock source switches |
| `MICROPY_HW_FLASH_LATENCY` | wait states for the chosen system clock |
| `MICROPY_HW_UART<n>_TX`, `_RX`, `_RTS`, `_CTS` | UART pins, as `pin_<P><n>` objects |
| `MICROPY_HW_UART_REPL`, `MICROPY_HW_UART_REPL_BAUD` | console UART |
| `MICROPY_HW_I2C<n>_SCL`, `_SDA` | I2C pins |
| `MICROPY_HW_SPI<n>_NSS`, `_SCK`, `_MISO`, `_MOSI` | SPI pins |
| `MICROPY_HW_CAN<n>_TX`, `_RX` | CAN pins |
| `MICROPY_HW_LED1`..`LED4`, `MICROPY_HW_LED_ON(pin)`, `MICROPY_HW_LED_OFF(pin)` | LEDs and their polarity |
| `MICROPY_HW_USRSW_PIN`, `_PULL`, `_EXTI_MODE`, `_PRESSED` | user button |
| `MICROPY_HW_USB_FS` or `_HS`, `MICROPY_HW_USB_VBUS_DETECT_PIN`, `MICROPY_HW_USB_OTG_ID_PIN` | USB |
| `MICROPY_HW_SDCARD_DETECT_PIN`, `_PULL`, `_PRESENT`, `MICROPY_HW_SDMMC<n>_*` | SD card |
| `MICROPY_HW_ETH_*` | Ethernet RMII pins |
| `MICROPY_HW_SPIFLASH_*`, `MICROPY_HW_BDEV_SPIFLASH*`, `MICROPY_HW_QSPIFLASH_*` | external flash storage (also needs `bdev.c` or a `spi_bdev` definition) |
| `MICROPY_BOARD_EARLY_INIT` | name of the board init function (see `board_init.c`) |

Pin objects are written `pin_<port letter><number>`: `pin_B8` for `PB8`. A macro that names a pad the part does not have fails the build. Remove every macro that names a pad of the seed board that the new board does not use, and every `MICROPY_HW_ETH_*`, `MICROPY_HW_SDCARD_*` or `MICROPY_HW_USB_*` group the hardware lacks.

Remove USB vendor and product ID macros (`MICROPY_HW_USB_VID`, `_PID`) that belong to the seed's vendor. The port defaults apply. The template leaves these IDs alone on purpose.

### `stm32<family>xx_hal_conf.h`

Set `HSE_VALUE` (Hz, the crystal or external clock frequency), `LSE_VALUE` (32768), `EXTERNAL_CLOCK_VALUE` (I2S external clock, only if one exists), `HSE_STARTUP_TIMEOUT`, `LSE_STARTUP_TIMEOUT`. Keep the include of `boards/stm32<family>xx_hal_conf_base.h`.

### `board_init.c`

Optional board hook, named by `MICROPY_BOARD_EARLY_INIT` in `mpconfigboard.h`. The seed's function is named `<SEED>_board_early_init` and drives a board-specific rail (`NUCLEO_F767ZI` turns off a USB power switch on `PG6`). Rename the function for the new board and replace the body with the real early actions (power rails, external chip resets, chip selects held high), or delete both the file and the `MICROPY_BOARD_EARLY_INIT` lines when nothing is needed. Keep the macro and the function name in step.

### `pins.csv`

Written by `gen_pins_csv.py`. Style: `<BOARD_NAME>,<Pxn>`. Example lines from `NUCLEO_F767ZI`: `A0,PA3`, `I2C1_SDA,PB9`, `SWDIO,PA13`. The file replaces the seed's file completely. On stm32 only the pads listed in `pins.csv` get a `pin_<Pxn>` object (`make-pins.py` and `tools/boardgen.py` generate objects for listed pads only). Every pad that a macro in `mpconfigboard.h` names (`pin_B8` and so on) must therefore be in `pins.csv`, or the build fails. `gen_pins_csv.py` skips unnamed nets, so list a used pad that has no net name with `--include-pad PB8` (board name `PB8`) or `--include-pad PB8=NAME`. Do not add such lines by hand. A self-named row (`PE2,PE2`) is valid on stm32: the pad object is `pin_E2` and the board name defines `pin_PE2`, so there is no duplicate. `gen_pins_csv.py` keeps self-named rows on this port.

### `manifest_base.py` and `manifest.py`

`manifest_base.py` is the seed manifest (`include("$(PORT_DIR)/boards/manifest.py")` and `require("bundle-networking")`). Keep it. Remove `require("bundle-networking")` only when the board has no network path and the user agrees. Do not edit the project `manifest.py`.

## Clock and power decisions to derive

Each decision gets a value, a source and a status in `clock-power.md`.

| Decision | Facts needed | Where it lands |
|---|---|---|
| HSE: crystal, external clock or none; frequency | BOM, schematic | `HSE_VALUE`, `MICROPY_HW_CLK_PLLM` |
| HSE bypass (external clock driven, not a crystal) | schematic | `MICROPY_HW_CLK_USE_BYPASS` |
| HSI only (no HSE fitted) | schematic | `MICROPY_HW_CLK_USE_HSI` |
| PLL M, N, P, Q (R) | HSE frequency, target system clock, USB 48 MHz need | `MICROPY_HW_CLK_PLL*` |
| Flash latency | system clock and supply voltage range of the part | `MICROPY_HW_FLASH_LATENCY` |
| LSE present | 32.768 kHz crystal in BOM | `MICROPY_HW_RTC_USE_LSE`, `LSE_VALUE` |
| Internal flash and RAM size | part number, datasheet | `.ld` file choice |
| External SPI or QSPI flash | BOM, schematic | `MICROPY_HW_SPIFLASH_*` or `MICROPY_HW_QSPIFLASH_*`, `bdev.c` |
| USB FS or HS, VBUS sense pin, ID pin | schematic | `MICROPY_HW_USB_*` |
| SD card, detect pin and polarity | schematic | `MICROPY_HW_SDCARD_*` |
| LEDs and polarity | schematic | `MICROPY_HW_LED*`, `MICROPY_HW_LED_ON/OFF` |
| Buttons, polarity and pull | schematic | `MICROPY_HW_USRSW_*` |
| Console UART | schematic | `MICROPY_HW_UART_REPL` |

Compute PLL values with `ports/stm32/boards/pllvalues.py` from the checkout, not by hand. It knows the VCO and divider ranges of each family. Usage: `python3 ports/stm32/boards/pllvalues.py [-c] [-m <mcu_series>] <hse in MHz>`. It lists the PLL settings and the resulting system clocks (`-c` prints C code). Pick the setting for the target system clock. State the result as an item to confirm: the allowed maximum frequency depends on the exact part, voltage scaling and temperature grade. Take the limit from the part's datasheet.

Items to confirm from the datasheet and schematic, not from memory: the exact system-clock maximum, the voltage range, whether VBUS sensing is wired, and whether a pad doubles as a boot-mode or debug pin.

## Pin and alternate-function validity

`AF_FILE` (for example `boards/stm32f767_af.csv`) lists each pad with its functions per AF index. Columns `Port,Pin,AF0..AF15,ADC`; the first data row is a comment row; the `Pin` cell is space-padded.

`lint_board.py --port stm32` checks:

- the `pins.csv` port names exist in the AF file;
- for each peripheral pin, the signal exists on that pad: `I2C1_SDA`, `SPI2_SCK`, `USART3_TX`, `UART4_RX`;
- the ADC column holds an `ADCn_INm` entry for ADC pads.

By hand: `grep -n '^ *PB8' ports/stm32/boards/stm32f767_af.csv` shows the signals of `PB8`. The `MICROPY_HW_I2C1_SCL` macro and the pad's `I2C1_SCL` entry must agree. UART and USART appear under both names; the board macros call both `UART<n>`.

`make-pins.py` also only enables an AF when the matching `MICROPY_HW_*` macro exists in `mpconfigboard.h`, so a missing macro hides that bus on the pad.

## Machine constructors (verified)

`docs/pyboard/quickref.rst` and the port sources (`machine_i2c.c`, `machine_spi.c`, `machine_uart.c`, `machine_adc.c`, `machine_pwm.c`):

```python
from machine import I2C, SPI, UART, ADC, PWM, Pin

i2c = I2C(1, freq=400000)  # pins from MICROPY_HW_I2C1_SCL/SDA
spi = SPI(1, baudrate=1000000)  # pins from MICROPY_HW_SPI1_*
uart = UART(4, baudrate=115200)  # pins from MICROPY_HW_UART4_TX/RX
adc = ADC(Pin("VBAT_SENSE"))
pwm = PWM(Pin("FAN_PWM"), freq=25000)  # pad needs a timer channel
```

I2C also has a software form `I2C(scl=Pin(..), sda=Pin(..), freq=..)`. `pyb.SPI`, `pyb.UART` and `pyb.Timer` are the older interfaces; the generated code uses `machine`.

## Pitfalls

- A bus is available only when its `MICROPY_HW_<BUS>_*` macros are defined.
- Pads used by the debug port (`SWDIO`, `SWDCLK`) and by the oscillator (`OSC_IN`, `OSC_OUT`) must not be given a function in `mpconfigboard.h`.
- A seed board's `board_init.c` or `MICROPY_HW_*` macros for its own on-board parts (ST-LINK UART, Ethernet PHY, SD slot) do not belong in the new board.
- With mboot, the application link address and the vector table address (`MICROPY_HW_VTOR`) follow `TEXT0_ADDR`. A mismatch builds but does not boot.
- The flash sector layout differs between parts of the same family. Check it before you change `TEXT0_ADDR` or the `.ld` file.
- `make mboot` builds only for families that mboot supports. Boards that already set `USE_MBOOT` in their `mpconfigboard.mk` (`grep -l USE_MBOOT ports/stm32/boards/*/mpconfigboard.mk`) show which families work.

## Build and verification commands

Run from the project root:

```bash
make submodules && make system
make libs-only
make mboot        # only when use_mboot is true
make tests
make checks
```

Firmware lands in `src/system/build-<BOARD>/` (`firmware.hex`, `firmware.dfu`, `firmware.elf`). With mboot the bootloader lands in `build-<BOARD>/bootloader.{bin,hex,dfu}`. The first build pulls the container image named in `src/system/build_containers.mk`.
