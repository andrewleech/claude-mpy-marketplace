---
paths:
  - "py/**"
  - "extmod/**"
  - "ports/**"
  - "lib/**"
  - "shared/**"
---

# MicroPython Architecture

## Core Components

**py/** - Core Python implementation
- `compile.c`, `parse.c`, `lexer.c` - Python compiler
- `vm.c`, `bc.c` - Virtual machine and bytecode execution
- `obj*.c` - Python object implementations (str, list, dict, etc.)
- `mod*.c` - Built-in modules (sys, gc, struct, etc.)
- `gc.c` - Garbage collector
- `qstr.c` - Interned string system

**extmod/** - Extended modules
- `machine_*.c` - Hardware abstraction layer (GPIO, I2C, SPI, UART, etc.)
- `network_*.c` - Network drivers
- `vfs_*.c` - Virtual filesystem implementations
- `modbluetooth.c` - Bluetooth support
- `machine_usb_*.c` - USB device/host support

**ports/** - Platform-specific implementations
- Each port implements `mphalport.h` and `mpconfigport.h` interfaces
- Contains board-specific configurations in `boards/` subdirectories

**lib/** - External dependencies (git submodules)
- TinyUSB, LWIP, mbedTLS, BTstack, etc.

## Key Design Patterns

1. **QSTR System**: Strings are interned for efficiency. When adding new identifiers:
   - Add to `qstrdefsport.h` or use `MP_QSTR_*` in code
   - Build system automatically extracts and processes QSTRs

2. **Object Model**: All Python objects inherit from `mp_obj_base_t`
   - Use `MP_DEFINE_CONST_*` macros for constant objects
   - Follow existing patterns in `obj*.c` files

3. **Hardware Abstraction**:
   - Generic interface in `extmod/machine_*.c`
   - Port-specific implementation in `ports/*/machine_*.c`

4. **Module Registration**:
   - Static modules in `mpconfigport.h` via `MICROPY_PORT_BUILTIN_MODULES`
   - Dynamic modules via `MP_REGISTER_MODULE`

## Resource Constraints

MicroPython targets microcontrollers with limited flash and RAM. The CI system automatically reports flash size and RAM usage changes on every PR, and reviewers scrutinise any increase. When planning or implementing changes:

* Minimise flash usage -- avoid large lookup tables, verbose strings, or unnecessary code paths. Prefer compact representations.
* Minimise RAM usage -- use `const` data where possible so it stays in flash, avoid heap allocations in hot paths, prefer stack-local variables.
* New features that increase code size must justify the trade-off. Small utility functions shared across ports are generally acceptable; large features should be gated behind config flags (e.g. `MICROPY_PY_*`).
* When a feature can be made optional via a config flag, do so. Default it to off for minimal ports and on for full-featured ports.
* Measure before and after: build the `unix` and `stm32` ports and compare `.text` / `.data` / `.bss` sizes. The CI does this automatically but catching regressions locally saves review cycles.

## Common Development Tasks

### Adding a New Built-in Function
1. Add implementation in appropriate `py/mod*.c` or `py/obj*.c` file
2. Add QSTR definition if needed
3. Register in module's globals dict
4. Add tests in `tests/basics/`

### Adding Hardware Support
1. Implement in port's `machine_*.c` following existing patterns
2. Use `MP_REGISTER_ROOT_POINTER` for GC roots
3. Follow the `machine` module API conventions
4. Add documentation in `docs/library/`

### Debugging
- Use `mp_printf(&mp_plat_print, "debug: %d\n", value)`
- Enable `DEBUG_printf` in specific files
- Use `MP_STACK_CHECK()` to detect stack overflow
- GC debugging: `gc.collect(True)` for verbose output
