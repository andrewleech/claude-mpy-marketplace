# mpy-ci

Run the MicroPython CI pipeline locally in Docker, matching the upstream GitHub Actions workflow.

A single Docker image (~15-20 GB) contains all cross-compiler toolchains, QEMU, ESP-IDF, Emscripten SDK, and linting tools. A runner script invokes the same `tools/ci.sh` functions that GitHub Actions uses.

## Usage

The skill installs two files into any MicroPython repo's `ci/` directory. From there:

```bash
# Build the Docker image (first time, ~30-60 min)
./ci/ci-local.sh --build

# Run a target
./ci/ci-local.sh unix

# Run multiple targets
./ci/ci-local.sh format codespell stm32

# All linting/formatting checks
./ci/ci-local.sh all-checks

# Everything
./ci/ci-local.sh all
```

## Targets

### Port Builds and Tests

| Target | What it does | ~Time |
|--------|-------------|-------|
| `unix` | 15+ variant builds, full test suites, sanitizers | 45 min |
| `unix-qemu` | Cross-compiled unix (MIPS, ARM, RISC-V64) via qemu-user | 30 min |
| `qemu` | Bare-metal ARM Cortex-M/A, RISC-V rv32/rv64 | 60 min |
| `stm32` | Pyboard, Nucleo, misc boards | 15 min |
| `esp32` | ESP32, S2, S3, C3, C2, C5, C6, P4 | 20 min |
| `rp2` | RP2040/RP2350 boards via pico-sdk | 10 min |
| `webassembly` | Pyscript variant build and tests | 5 min |
| `esp8266` | Firmware and native modules | 2 min |
| `cc3200` | WiPy firmware | 1 min |
| `mimxrt` | i.MX RT boards | 3 min |
| `nrf` | nRF boards | 3 min |
| `powerpc` | PowerPC firmware | 1 min |
| `renesas` | Renesas RA boards | 3 min |
| `samd` | SAMD boards | 3 min |
| `alif` | Alif Ensemble boards | 3 min |
| `windows` | MinGW cross-compile | 1 min |
| `zephyr` | Zephyr RTOS (runs on host, pulls own image) | 30 min |

### Code Quality Checks

| Target | What it checks |
|--------|---------------|
| `format` | C code formatting (uncrustify 0.72, matching upstream CI) |
| `codespell` | Spelling errors, MicroPython capitalisation |
| `ruff` | Python linting and formatting |
| `biome` | JavaScript/TypeScript linting |
| `docs` | Sphinx HTML documentation build |
| `examples` | Embedding examples build and test |
| `mpy-format` | .mpy file format tools, mpy-cross debug emitter |
| `mpremote` | mpremote wheel packaging |

### Meta Targets

- `all-checks` — all code quality checks
- `all` — all checks + all port builds

## Prerequisites

- Docker
- For `unix-qemu`: binfmt_misc handlers registered on the host:
  ```bash
  docker run --rm --privileged multiarch/qemu-user-static --reset
  echo -1 | sudo tee /proc/sys/fs/binfmt_misc/qemu-mipsn32 >/dev/null
  echo -1 | sudo tee /proc/sys/fs/binfmt_misc/qemu-mipsn32el >/dev/null
  ```

## Docker Image Contents

Ubuntu 24.04 base with:

- ARM GNU Toolchain 14.3 (STM32, Alif, Cortex-M55)
- ESP-IDF (version derived from repo lockfile)
- Emscripten SDK (latest)
- pico-sdk + picotool (RP2)
- ESP8266 xtensa toolchain
- Cross-compilers: MIPS, ARM, RISC-V (32/64), PowerPC, MinGW
- QEMU system + user-static
- gcc-multilib, clang (32-bit unix builds)
- Python: pyelftools, esptool, sphinx, codespell, ruff
- Node.js 18, npm, biome 1.5.3
- uncrustify 0.72 (built from source, matching upstream CI's ubuntu-22.04)

## Notes

- `esp32` and `webassembly` targets create symlinks in the repo root (`esp-idf` → `/opt/esp-idf`, `emsdk` → `/opt/emsdk`) so that `source` calls in `ci.sh` resolve inside the container. Both are gitignored.
- `zephyr` runs on the host — `ci.sh` manages its own Docker container and ~15 GB west workspace.
- The `unix` target runs variants sequentially in a shared workspace. The script inserts `make clean` calls between incompatible variants (32/64-bit, cross-compiler changes) to prevent incremental build pollution.
- Override the image name: `MICROPYTHON_CI_IMAGE=my-image:tag ./ci/ci-local.sh unix`
- Pass make parallelism: `MAKEOPTS="-j8" ./ci/ci-local.sh stm32`

## Known Issues

- **qemu MPS2_AN385**: Returns empty output for ~50% of tests when run in bulk via `execpty:` inside Docker. Individual tests pass. Other qemu boards work. Test runs are non-fatal.
- **unix-qemu REPL tests**: `cmdline/repl_*.py` fails under qemu-user-static. Non-fatal.
- **unix thread tests**: `thread/stress_schedule.py` is flaky. Not a ci-local.sh issue.
