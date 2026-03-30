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

**Install the pre-push hook (strongly recommended):**

Pre-commit hooks do NOT run during `git rebase` (git uses implicit `--no-verify`
for cherry-picked commits). This means rebased code bypasses all linting, formatting,
and commit message checks. The pre-push hook catches these issues before they reach
the remote.

```bash
ln -sf ../../tools/pre-push-check.sh .git/hooks/pre-push
```

For worktrees, git shares hooks from the main repo's `.git/hooks/` directory via
`core.hooksPath`, so the hook only needs to be installed once in the main repo.

The pre-push hook runs on the commit range being pushed and checks:
1. Commit message format (`verifygitlog.py`) including Signed-off-by
2. C code formatting (`codeformat.py`)
3. Python linting and formatting (`ruff`)
4. Spelling (`codespell`)

To bypass in emergencies: `git push --no-verify`

**Required host tools for pre-push checks:**
```bash
pipx install ruff      # or: pip install --user ruff
pipx install codespell # or: pip install --user codespell
# codeformat.py and verifygitlog.py are in-tree (tools/)
```

**Commit message format (enforced by `tools/verifygitlog.py` via pre-commit):**

Subject line rules:
* Must match: `component: Capitalised description ending with period.`
* Regex: `^[^!]+: [A-Z]+.+ .+\.$`
* Maximum 72 characters
* First word after the colon must be capitalised
* Must contain more than one word after the colon
* Component prefix must not start with `.` or `/`, must not end with `/`
* Component prefix must not start with `ports/` -- use the port name directly (e.g. `stm32:` not `ports/stm32:`)
* Component prefix must not end with a file extension -- use the filename without extension

Body rules:
* Second line must be blank (separates subject from body)
* Body lines must be 75 characters or fewer (URLs and `Signed-off-by:`/`Co-authored-by:` lines are exempt)
* Last line must be `Signed-off-by:` with an email address (use `git commit -s`)
* Keep descriptions terse -- one or two sentences is usually enough. The diff provides the detail.

Example:
```
py/objstr: Add splitlines() method.

Implements splitlines() for str objects, compatible with CPython.

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
