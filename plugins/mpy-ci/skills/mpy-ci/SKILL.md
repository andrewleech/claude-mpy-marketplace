---
name: mpy-ci
description: Run the MicroPython CI pipeline locally using Docker. This skill should be used when working in a MicroPython repository and the user wants to run CI checks, build firmware, or test changes locally before pushing. Triggers on requests like "run CI", "test my changes", "build stm32", "run all checks", "run the linters", or any mention of local CI testing for MicroPython.
---

# MicroPython Local CI

Run the full MicroPython CI pipeline locally in Docker, matching what GitHub Actions runs upstream.

## Setup

The skill bundles two files that must be installed into the MicroPython repo:

1. **`ci/Dockerfile`** — Ubuntu 24.04 image with all toolchains (~15-20 GB)
2. **`ci/ci-local.sh`** — Runner script that invokes `tools/ci.sh` functions inside the container

### Installation

To install the CI runner into a MicroPython repo:

1. Copy the bundled files into the repo:
   ```bash
   mkdir -p ci/
   cp <skill_path>/assets/Dockerfile ci/Dockerfile
   cp <skill_path>/scripts/ci-local.sh ci/ci-local.sh
   chmod +x ci/ci-local.sh
   ```

2. Add to `.gitignore` (build artifacts created by CI):
   ```
   esp-idf
   emsdk
   ```

3. Build the Docker image (takes 30-60 minutes on first run):
   ```bash
   ./ci/ci-local.sh --build
   ```

### Prerequisites

- Docker installed and running
- For the `unix-qemu` target, register binfmt_misc handlers on the host:
  ```bash
  docker run --rm --privileged multiarch/qemu-user-static --reset
  echo -1 | sudo tee /proc/sys/fs/binfmt_misc/qemu-mipsn32 >/dev/null
  echo -1 | sudo tee /proc/sys/fs/binfmt_misc/qemu-mipsn32el >/dev/null
  ```

## Available Targets

### Port Builds and Tests

| Target | Description | Runtime |
|--------|-------------|---------|
| `stm32` | STM32 firmware (pyboard, nucleo, misc boards) | ~15 min |
| `unix` | Unix port: 15+ variant builds and full test suites | ~45 min |
| `unix-qemu` | Cross-compiled unix (MIPS, ARM, RISC-V64) tested via qemu-user | ~30 min |
| `esp32` | ESP32 variants (S2, S3, C3, C2, C5, C6, P4) | ~20 min |
| `esp8266` | ESP8266 firmware and native modules | ~2 min |
| `rp2` | RP2040/RP2350 boards | ~10 min |
| `qemu` | Bare-metal QEMU (ARM Cortex-M/A, RISC-V rv32/rv64) | ~60 min |
| `cc3200` | CC3200 (WiPy) firmware | ~1 min |
| `mimxrt` | i.MX RT boards | ~3 min |
| `nrf` | nRF boards | ~3 min |
| `powerpc` | PowerPC firmware | ~1 min |
| `renesas` | Renesas RA boards | ~3 min |
| `samd` | SAMD boards | ~3 min |
| `alif` | Alif Ensemble boards | ~3 min |
| `webassembly` | WebAssembly/pyscript build and tests | ~5 min |
| `windows` | MinGW cross-compile | ~1 min |
| `zephyr` | Zephyr RTOS (runs on host, pulls own Docker image) | ~30 min |

### Code Quality Checks

| Target | Description |
|--------|-------------|
| `format` | C code formatting (uncrustify) |
| `codespell` | Spell checking |
| `ruff` | Python linting and formatting |
| `biome` | JavaScript/TypeScript linting |
| `docs` | Sphinx documentation build |
| `examples` | Embedding examples build and test |
| `mpy-format` | .mpy file format tools and mpy-cross debug emitter |
| `mpremote` | mpremote wheel packaging |

### Meta Targets

| Target | Description |
|--------|-------------|
| `all-checks` | Run all code quality checks |
| `all` | Run all checks + all port builds |

## Usage

```bash
# Build the Docker image (first time or after Dockerfile changes)
./ci/ci-local.sh --build

# Run a single target
./ci/ci-local.sh unix

# Run multiple targets
./ci/ci-local.sh format codespell ruff stm32

# Run all code quality checks
./ci/ci-local.sh all-checks

# Build image and run targets in one command
./ci/ci-local.sh --build unix stm32

# Override the Docker image name
MICROPYTHON_CI_IMAGE=my-image:tag ./ci/ci-local.sh unix
```

## Known Issues

- **MPS2_AN385 (qemu target)**: The Cortex-M3 softfp board returns empty output for ~50% of tests when run in bulk via `execpty:` inside Docker. Individual tests pass. Other qemu boards (SABRELITE, MPS2_AN500, rv32, rv64) work correctly. Test runs are non-fatal (`|| true`).
- **unix-qemu REPL tests**: `cmdline/repl_*.py` and `misc/sys_settrace_features.py` fail under qemu-user-static emulation due to PTY handling differences. These are non-fatal.
- **unix thread tests**: `thread/stress_schedule.py` is flaky (sporadic timing-dependent failure). Not a ci-local.sh issue.
- **Shared build state**: Sequential variant builds in the `unix` target share `build-*` directories. The script inserts `make clean` calls between incompatible variants (32-bit/64-bit, cross-compiler changes) to prevent incremental build pollution.

## Resources

### scripts/ci-local.sh

The runner script. Handles Docker image building, container lifecycle, and target dispatch. Each target function calls one or more `tools/ci.sh` functions inside the container.

### assets/Dockerfile

Ubuntu 24.04-based Docker image containing all toolchains: ARM GNU 14.3, ESP-IDF (version from repo lockfile), Emscripten SDK, RISC-V, MIPS, MinGW, PowerPC cross-compilers, QEMU, pico-sdk, and linting tools (uncrustify 0.72, codespell, ruff, biome, sphinx).
