# MicroPython port tree

Use this reference to find which chips a MicroPython port supports and to choose a seed board. The tree is the only source of chip data. The skill ships no pin or chip tables.

## Where the checkout comes from

Use the first source that applies:

1. The user's own checkout. Ask for the path. Do not modify it. Check `git -C <dir> describe --tags` and tell the user which version the facts were read from.
2. `src/micropython` inside the scaffolded project. It is a shallow git submodule of `https://github.com/micropython/micropython.git`, present after `initial_setup.py` has run.
3. Before the scaffold exists: the GitHub tree API, read only.
   - `gh api 'repos/micropython/micropython/git/trees/master?recursive=1' --jq '.tree[].path'` lists every path. Filter with `grep '^ports/<port>/boards/'`.
   - Without `gh`: `https://api.github.com/repos/micropython/micropython/git/trees/master?recursive=1`. The response can be truncated for large trees. Check the `truncated` field and fall back to a per-directory request (`.../git/trees/<sha>`).
   - File content: `https://raw.githubusercontent.com/micropython/micropython/master/ports/<port>/boards/<BOARD>/<file>`.
   - `pick_seed.py --remote` does this for you.
   - A shallow clone into a scratch directory is often faster than many raw requests: `git clone --depth 1 --filter=blob:none --sparse https://github.com/micropython/micropython.git <dir>` then `git -C <dir> sparse-checkout set ports/<port> tools docs`.

The scaffold pins whatever commit the submodule clone fetches. Chips and boards can differ between `master` and a release. When the user needs a release, tell them which tag the checkout is on and check that the seed board exists there.

## Ports in scope

`stm32`, `rp2`, `esp32`, `mimxrt`, `samd`. The `unix` and `windows` ports have no `boards/` directory. Other ports with boards (`nrf`, `renesas-ra`, `esp8266`, `cc3200`, and so on) are out of scope. Tell the user if the chip is only supported by one of them.

## A board directory

Path: `ports/<port>/boards/<BOARD>/`. A directory under `boards/` is a board. Files at the `boards/` level are family data shared by many boards (see "Family level data").

File lists in the current tree (verified):

| Board | Files |
|---|---|
| `stm32/NUCLEO_F767ZI` | `board.json`, `board_init.c`, `manifest.py`, `mpconfigboard.h`, `mpconfigboard.mk`, `pins.csv`, `stm32f7xx_hal_conf.h` |
| `rp2/RPI_PICO` | `board.json`, `mpconfigboard.cmake`, `mpconfigboard.h`, `pins.csv` |
| `rp2/RPI_PICO2` | the same, plus `mpconfigvariant.cmake` and `mpconfigvariant_RISCV.cmake` |
| `esp32/ESP32_GENERIC` | `board.json`, `board.md`, `mpconfigboard.cmake`, `mpconfigboard.h`, `mpconfigvariant_{D2WD,OTA,SPIRAM,UNICORE}.cmake`, `sdkconfig.{d2wd,ota,unicore}`. No `pins.csv`. |
| `esp32/ESP32_GENERIC_S3` | `board.json`, `board.md`, `mpconfigboard.cmake`, `mpconfigboard.h`, `mpconfigvariant_SPIRAM_OCT.cmake` |
| `mimxrt/TEENSY40` | `board.json`, `format.py`, `mpconfigboard.h`, `mpconfigboard.mk`, `pins.csv` |
| `mimxrt/MIMXRT1060_EVK` | `board.json`, `board.md`, `manifest.py`, `mpconfigboard.h`, `mpconfigboard.mk`, `pins.csv` |
| `samd/ADAFRUIT_ITSYBITSY_M4_EXPRESS` | `board.json`, `mpconfigboard.h`, `mpconfigboard.mk`, `pins.csv` |

Other boards add `sdkconfig.board` (esp32), `bdev.c` (stm32), `modules/` (esp32, rp2), `deploy*.md`, `mpconfigvariant_*.{mk,cmake}` and linker or flash-config files. Not every board has every file.

Which file does what:

| File | Role |
|---|---|
| `board.json` | metadata for documentation and the download pages, and for board lookup in `mpbuild` |
| `mpconfigboard.mk` (stm32, mimxrt, samd) or `mpconfigboard.cmake` (rp2, esp32) | build variables: MCU identifiers, linker files, flash layout, feature switches |
| `mpconfigboard.h` | C macros: board and MCU name, clocks, peripheral pins, LEDs, USB, storage |
| `pins.csv` | board pin name to port pin name, one pair per line |
| `manifest.py` | frozen modules for the board |
| `mpconfigvariant_<NAME>.{mk,cmake}` | optional build variant, selected with `BOARD_VARIANT=<NAME>` |
| `board_init.c`, `bdev.c` | board code hooks |
| `stm32*_hal_conf.h` | HAL oscillator values (stm32) |
| `sdkconfig.board` | ESP-IDF settings appended by `mpconfigboard.cmake` (esp32) |

### `board.json` fields

`deploy` (list of paths to deploy notes), `docs` (string), `features` (list of strings such as `USB`, `WiFi`, `External Flash`), `images` (list of file names), `mcu` (string, see below), `product`, `thumbnail`, `url`, `vendor`. Optional: `variants` (object, variant name to description), `deploy_options` (esp32: `flash_offset`), `old_variants`.

`mcu` values in the current tree: stm32 uses the family (`stm32f4`, `stm32f7`, `stm32h7`, `stm32l4`, `stm32wb`, `stm32u5`, `stm32l0`, `stm32wl`); rp2 uses `rp2040` or `rp2350`; esp32 uses the chip (`esp32`, `esp32s2`, `esp32s3`, `esp32c3`, `esp32c6`, and so on); mimxrt uses the literal `mimxrt`; samd uses `samd21` or `samd51`. Some stm32 boards (for example `NUCLEO_N657X0`, `PYBV3`) have no `board.json`, so do not rely on it alone.

### MCU identifiers per port

These variables name the chip. `pick_seed.py` reads them. Read them by hand when the script cannot.

| Port | File | Variables | Example |
|---|---|---|---|
| stm32 | `mpconfigboard.mk` | `MCU_SERIES` (family: `f4`, `f7`, `h7`, `l4`, ...), `CMSIS_MCU` (device define), `AF_FILE` | `f7`, `STM32F767xx`, `boards/stm32f767_af.csv` |
| stm32 | `mpconfigboard.h` | `MICROPY_HW_MCU_NAME` | `"STM32F767"` |
| rp2 | `mpconfigboard.cmake` | `PICO_PLATFORM` (`rp2040`, `rp2350`, `rp2350-riscv`), `PICO_BOARD`, `PICO_NUM_GPIOS`, `PICO_FLASH_SIZE_BYTES` | `PICO_PLATFORM` is set by `mpconfigboard.cmake` or a variant file. When unset, the pico-sdk board header named by `PICO_BOARD` supplies it with `pico_board_cmake_set(PICO_PLATFORM, ...)`: read `lib/pico-sdk/src/boards/include/boards/<board>.h` |
| esp32 | `mpconfigboard.cmake` | `IDF_TARGET`, usually through `include(boards/mpconfigboard_esp32<target>_common.cmake)` | `esp32s3` |
| mimxrt | `mpconfigboard.mk` | `MCU_SERIES` (`MIMXRT1062`), `MCU_VARIANT` (`MIMXRT1062DVJ6A`) | |
| samd | `mpconfigboard.mk` | `MCU_SERIES` (`SAMD21` or `SAMD51`), `CMSIS_MCU` (`SAMD51G19A`) | |

Two details:

- rp2 board directories can leave `PICO_BOARD` unset. `ports/rp2/CMakeLists.txt` then lowercases the board name and uses it as the pico-sdk board name. Check `lib/pico-sdk/src/boards/include/boards/` in the checkout for a matching header.
- esp32 `mpconfigboard.cmake` files are often one `include(...)` line plus `SDKCONFIG_DEFAULTS` additions. The chip is the include's `IDF_TARGET`. Read the included `boards/mpconfigboard_esp32*_common.cmake`.

### Family level data

Pin and alternate-function data is not in the board directory. Read it from the tree:

| Port | Location | Shape |
|---|---|---|
| stm32 | `ports/stm32/boards/<mcu>_af.csv`, named by `AF_FILE` | columns `Port,Pin,AF0..AF15,ADC`. The first data row is a comment row. The `Pin` cell is space-padded. Signals look like `I2C1_SDA`, `SPI2_SCK`, `USART3_TX`, `UART4_RX`. The `ADC` cell looks like `ADC123_IN3`. |
| mimxrt | `ports/mimxrt/boards/<MCU_SERIES>_af.csv` | header `Pad,ALT0,...,ALT9,ADC,ACMP,Default`. One row per pad (`GPIO_AD_B0_03`). Signals look like `LPI2C1_SCL`, `LPSPI3_SCK`, `LPUART1_TX`. The `Default` column names the ALT used for GPIO (`ALT5`). |
| samd | `ports/samd/mcu/<series lower case>/pin-af-table.csv` | header `Pin,EIC,ADC0,ADC1,SERCOM1,SERCOM2,TC,TCC1,TCC2`. The comment block at the top of the file explains the cell encoding (SERCOM, TC and TCC cells hold device number then pad number). Read the comment block. |
| rp2 | `ports/rp2/boards/rp2040_af.csv`, `rp2350_af.csv`, `rp2350b_af.csv` and C macros | the AF csv has `Pin,AF0..AF9` with signals such as `SPI0_RX`, `UART0_TX`, `I2C0_SDA`, `PWM0_A`. Hardware bus validity is also enforced by `IS_VALID_*` macros in `machine_spi.c`, `machine_uart.c` and `machine_i2c.h`. |
| esp32 | none | the GPIO matrix routes most functions to any GPIO. `boards/make-pins.py` only checks the `GPIOn` name range against the IDF `GPIO_NUM_MAX`. Limits (input-only pads, strapping pins, flash and PSRAM pads) come from the chip datasheet. |

Each port's `boards/make-pins.py` (built on `tools/boardgen.py`) turns `pins.csv` plus the AF table into the generated pin tables. The `pins.csv` rules are the same on all ports:

- Each non-comment line has exactly two fields: `<board pin name>,<port pin name>`.
- Lines that start with `#` are comments. Empty lines are skipped.
- A leading `-` on either name hides it from Python but keeps it in C.
- An empty board name (`,PA3`) makes the pad available by its port name only.
- stm32 makes only the pads listed in `pins.csv` available. rp2, esp32, samd and mimxrt make every pad of the chip available whether listed or not.

## Listing the supported chips

Collect the chips a port supports from the boards:

```bash
cd <checkout>/ports/stm32/boards
grep -H '^\(MCU_SERIES\|CMSIS_MCU\)' */mpconfigboard.mk
```

For other ports:

```bash
cd <checkout>/ports/rp2/boards    && grep -H 'PICO_PLATFORM' */*.cmake
cd <checkout>/ports/esp32/boards  && grep -H 'IDF_TARGET' *.cmake */mpconfigboard.cmake
cd <checkout>/ports/mimxrt/boards && grep -H '^MCU_\(SERIES\|VARIANT\)' */mpconfigboard.mk
cd <checkout>/ports/samd/boards   && grep -H '^\(MCU_SERIES\|CMSIS_MCU\)' */mpconfigboard.mk
```

The AF csv files also list what the port can drive. For stm32, one `*_af.csv` per MCU family sub-type exists: `stm32f767_af.csv` covers the F76x/F77x devices. A chip is supported when the port has its AF file (stm32, mimxrt), a `pin-af-table.csv` for its series (samd), its platform (rp2), or its `IDF_TARGET` (esp32).

## Choosing a seed board

The seed is a board definition that the template copies into `src/system/<BOARD>/`. The retarget stage edits that copy. Rank candidates in this order:

1. Exact MCU match: same `CMSIS_MCU` (stm32, samd), same `MCU_VARIANT` (mimxrt), same `PICO_PLATFORM` (rp2), same `IDF_TARGET` (esp32). Among exact matches, prefer the board whose flash size, RAM size and peripherals are closest to the new hardware.
2. Same series or variant family: same `MCU_SERIES` with a different device (stm32 `f7`, mimxrt `MIMXRT1062`, samd `SAMD51`), or an esp32 target in the same family. The AF file and linker script may differ. The retarget stage must change them.
3. Same port default: the template's default for the port (`PYBV11` stm32, `RPI_PICO` rp2, `ESP32_GENERIC` esp32, `TEENSY40` mimxrt, `ADAFRUIT_ITSYBITSY_M4_EXPRESS` samd). Use this only when the chip is in the port but no board uses a similar chip.

Prefer a development board or generic module that is close in function to the new hardware. A generic board carries fewer board-specific edits to remove (for example `ESP32_GENERIC`, `SAMD_GENERIC_D51X19`). Prefer boards that already carry an `USE_MBOOT` conditional when the project uses mboot (stm32).

If no board in any in-scope port uses the chip, or the port has no AF data for it, stop. Tell the user which ports exist and which chips they cover. Do not guess a nearby chip. A new chip needs port-level work in MicroPython (AF table, linker script, clock code) which this skill does not do.

Show the ranked candidates and the reason for each rank. Get the user's choice before the scaffold. `template_board` must name a directory that exists under `ports/<port>/boards/` in the submodule the scaffold fetches.

## By hand, when `pick_seed.py` cannot

Use this when the script fails on an unusual board layout or the tree is not local.

1. List boards: `ls <checkout>/ports/<port>/boards | grep -v '\.'` (directories only).
2. Find boards with the chip. stm32: `grep -l 'CMSIS_MCU *= *STM32F767' <checkout>/ports/stm32/boards/*/mpconfigboard.mk`. Use the shortest unique prefix of the device name; one board can match several devices in a family.
3. For ports where the chip is set by an included file (esp32), open the board's `mpconfigboard.cmake` and follow the `include(...)`.
4. Confirm the AF data exists: `ls <checkout>/ports/stm32/boards/stm32f767_af.csv`.
5. Compare flash and RAM: stm32 linker script `boards/<mcu>.ld` (`MEMORY` block); samd `boards/samd51x19a.ld`; mimxrt `MICROPY_HW_FLASH_SIZE` in `mpconfigboard.mk`; rp2 `MICROPY_HW_FLASH_STORAGE_BYTES` and `PICO_FLASH_SIZE_BYTES`; esp32 `CONFIG_ESPTOOLPY_FLASHSIZE_*` in the sdkconfig files.
6. Without a local checkout, fetch the two or three files you need with `gh api repos/micropython/micropython/contents/ports/<port>/boards/<BOARD>/mpconfigboard.mk --jq .content | base64 -d`.
7. Record the ranking and the reason for each candidate in the report, as `pick_seed.py` would.

## Reading a seed board before retarget

Open every file in the seed directory. For each setting, decide whether it is a property of the chip (keep or adjust per port reference), a property of the seed hardware (replace or remove), or a project setting (leave alone: the `mpconfigproj` include and the `MICROPY_HW_BOARD_NAME` prefix that `initial_setup.py` adds). The per-port references list the settings in each group.
