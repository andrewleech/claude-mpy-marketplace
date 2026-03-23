---
---

# MicroPython Core Rules

Rules for building, testing, formatting, and committing code in the MicroPython codebase.

## Building MicroPython

### Prerequisites
First build the cross-compiler:
```bash
cd mpy-cross
make
```

### Common Build Commands

**Unix Port (for development/testing):**
```bash
cd ports/unix
make submodules  # Initialize git submodules (first time only)
make             # Standard build
make test        # Run basic tests
make test_full   # Run comprehensive test suite
make clean       # Clean build artifacts
```

**STM32 Port:**
```bash
cd ports/stm32
make submodules                    # Initialize git submodules (first time only)
make BOARD=PYBV10                  # Build for specific board
make BOARD=PYBV10 deploy           # Deploy via DFU
make BOARD=PYBV10 deploy-stlink    # Deploy via ST-Link
make clean                         # Clean build artifacts
```

**ESP32 Port:**
```bash
cd ports/esp32
make submodules        # Initialize git submodules
make BOARD=ESP32_GENERIC
make BOARD=ESP32_GENERIC deploy
```

**RP2 (Raspberry Pi Pico) Port:**
```bash
cd ports/rp2
make submodules
make BOARD=RPI_PICO
make BOARD=RPI_PICO_W  # For Pico W with wireless
```

### Common Make Options
- `V=1` - Verbose build output
- `DEBUG=1` - Debug build with symbols
- `FROZEN_MANIFEST=path/to/manifest.py` - Include frozen Python modules

## Running Tests

```bash
# Run all tests for Unix port
cd ports/unix
make test_full

# Run specific test
../../tests/run-tests.py basics/builtin_str.py

# Run tests with specific options
../../tests/run-tests.py --target unix --via-mpy

# Run multi-instance tests
../../tests/run-multitests.py

# Run performance benchmarks
../../tests/run-perfbench.py
```

## Unit Tests
The unit tests are in tests/<category> folders.
They are generally written as python scripts that are run under both
micropython a (c)python with the print outputs compared for consistency.
For tests that can only run on micropython a unittest based test is preferred else
 a <test name>.py script is accompanied by a <test name>.py.exp where the .exp file
contains the expected print outputs to compare the test output against.

## Code Formatting and Style

All new C/python/sh files should have a newline at the end of the file.

**Before committing code:**
```bash
# Format C code (requires uncrustify v0.72)
tools/codeformat.py

# Format specific files only
tools/codeformat.py path/to/file.c

# Check formatting without modifying
tools/codeformat.py -c

# Python code is formatted with ruff
ruff format

# Run spell check
codespell

# Run lint and formatting checks (if using pre-commit)
pre-commit run --files [files...]
```

**Use pre-commit hooks for automatic checks (recommended):**
```bash
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

**Commit message format:**
```
component/subcomponent: Brief description ending with period.

Detailed explanation if needed, wrapped at 75 characters.

Signed-off-by: Your Name <your.email@example.com>
```

Example:
```
py/objstr: Add splitlines() method.

This implements the splitlines() method for str objects, compatible
with CPython behavior.

Signed-off-by: Developer Name <dev@example.com>
```

## Code Style Guidelines

**General:**
* Follow conventions in existing code.
* See `CODECONVENTIONS.md` for detailed C and Python style guides.

**Python:**
* Follow PEP 8.
* Use `ruff format` for auto-formatting (line length 99).
* Naming: `module_name`, `ClassName`, `function_name`, `CONSTANT_NAME`.

**C:**
* Use `tools/codeformat.py` for auto-formatting.
* Naming: `underscore_case`, `CAPS_WITH_UNDERSCORE` for enums/macros, `type_name_t`.
* Memory allocation: Use `m_new`, `m_renew`, `m_del`.
* Integer types: Use `mp_int_t`, `mp_uint_t` for general integers, `size_t` for sizes.
