---
---

# MicroPython Development Patterns

Common pitfalls and requirements when developing for MicroPython, distilled
from historical project review data.

## Correctness

* **Parenthesize all C macro arguments** to prevent double evaluation and type mismatches. Verify argument types at call sites match what the macro expects.
  > "This macro is now wrong because the argument is a dma_id_t which is not a channel. So this macro will always evaluate to 0 for the F4/F7."

* **Verify ISR context** -- use appropriate RTOS primitives (`vTaskNotifyGive`, not `mp_sched_schedule`) when running from an interrupt or FreeRTOS task. Do not allocate memory in interrupt handlers.
  > "Is this USB callback actually an ISR? Or should we instead be using `vTaskNotifyGive(mp_main_task_handle)` instead?"

* **Handle tick counter overflow** -- use subtraction-based comparison for timeouts, not direct comparison. Capture scheduler state atomically.

* **Guard NULL pointer access** -- check pointers before dereferencing, especially for socket `pcb` fields and hardware register access. Order compound conditions so NULL checks come first.

* **Check integer overflow in timer/PWM calculations** -- use `long long` multiplication or reorder operations to avoid overflow with 32-bit timer periods.
  > "This could overflow an int if the timer is 32-bit. Could use long long multiplication, or divide the period by 100 first."

* **Respect nested `disable_irq` context** -- do not unconditionally disable interrupts in functions that may be called within an existing `disable_irq`/`enable_irq` block.

* **Verify feature guards match their C definitions** -- `#ifdef MICROPY_HW_USB_CDC` must match the macro that guards the corresponding implementation in the source file.

* **Do not duplicate interrupt handler logic** -- new UART read/write code must not conflict with the existing IRQ handler. Cache status register values to avoid clearing flags that the IRQ handler needs.

## Memory and Code Size

* **Measure code size impact** across `bare-arm`, `minimal`, `unix`, and `stm32` builds. Document any increase and justify the trade-off. CI reports this automatically but catching regressions locally saves review cycles.

* **Use `MP_OBJ_NEW_SMALL_INT()` for values fitting the small-int range** instead of `mp_obj_new_int()` which triggers heap allocation.
  > "Using `mp_obj_new_int()` can lead to heap allocation and so will be slower than using `MP_OBJ_NEW_SMALL_INT()`."

* **Use `m_new`/`m_del` for allocations**, not raw `gc_alloc`/`gc_free`. Ensure pointers passed to external libraries are in GC-scanned memory or stack-allocated.

* **Pack structs tightly** -- reorder fields to minimise padding. Use `const` for immutable data so it stays in flash, not RAM.
  > "This won't work because the objects below are defined `const` (to not use RAM, they live in ROM)."

* **Minimise qstr additions** -- avoid adding qstrs that increase size for ports that don't use them (bare-arm, minimal). Prefix internal constants with underscore.

* **Avoid allocations in hot paths** -- no temporary objects in pixel setters, tight loops, or polling functions.

* **Cache loop-invariant expressions** outside loops. Use `uint32_t` with `mp_hal_ticks_ms` for timeout tracking.

* **Run performance benchmarks** on target hardware before and after changes to verify no regressions.

## API Design

* **Maintain CPython compatibility** -- APIs named after CPython modules must have compatible signatures. Do not diverge without strong justification.
  > "The goal is not to diverge too much with CPython, it makes writing code that runs on both uPy and CPy more difficult."

* **Keep parameter names consistent across all ports** for the same interface. If esp32 uses `password`, stm32 and cyw43 should too.

* **Use `mp_obj_get_array()` to accept both tuples and lists** instead of type-checking for a specific sequence type.

* **Use `mp_obj_is_true()` for boolean conversion**, not manual integer comparison.

* **Avoid unnecessary wrapper classes** -- prefer direct use of `Pin`, `SPI`, etc. over convenience wrappers that add overhead without meaningful abstraction.
  > "I think it's much simpler to just do: `button = Pin(BUTTON, Pin.IN, Pin.PULL_UP)` and not have this class at all."

* **Raise exceptions for unimplemented methods** rather than returning stub values. Do not hardcode configurable parameters like baudrate.

* **Board configs should set final values directly** (e.g. `MICROPY_HEAP_START`, `MICROPY_HEAP_END`) rather than introducing intermediate config variables.

* **Expose public constants in the module locals dict**. Keep constant names consistent across LAN and WLAN interfaces.

## Portability

* **Use abstraction layers** instead of direct HAL calls. Port-specific code belongs in `ports/*/`, not in `extmod/` or `py/`.

* **Keep enum values stable** across build configurations to maintain ABI compatibility.

* **Test cross-platform assumptions** -- `alloca.h` vs `malloc.h`, `__attribute__` availability, endianness. Use `#if`/`#ifdef` with documented rationale.

## Error Handling

* **Return specific errno constants** (`-EIO`, `-EINVAL`) rather than generic `-1`.
  > "It should return a negative errno value (ie `MP_OBJ_NEW_SMALL_INT(-EIO)`) instead of raising an exception."

* **Provide meaningful source names** in error contexts -- do not pass empty `MP_QSTR_` as a filename.

* **Use `MICROPY_ERROR_PRINTER`** for error output, not `snprintf` with `MP_ERROR_TEXT` (they are incompatible).

## Documentation

* **Include MIT license header** in all new files. Verify copyright attribution matches the actual author. Document license origin for vendored code.
  > "Does this file have any copyright/license? I see it originally came from PuTTY."

* **Verify documentation describes MicroPython behaviour**, not CPython. Mark any CPython-specific details explicitly.

* **Use practical code examples** in docs. Place module documentation in `docs/library/`. Document auto-generated constants.

## Build System

* **Do not redefine config defaults** -- if `py/mpconfig.h` already defines a value, do not repeat it in port or board config.
  > "This is already the default (in `py/mpconfig.h`), so can be removed."

* **Place generated files in `$(BUILD)/`** to keep the source tree clean.

* **Builds must not require internet access.** Do not download dependencies at build time.

* **Use git submodules for third-party libraries** rather than checking them into the repository. Verify submodule updates are merged upstream before updating references.

## Testing

* **Test on actual hardware** and name the specific boards/ports in the PR description. Provide a minimal reproduction script for bug fixes.
  > "Thanks, this looks good to me. Did you get a chance to test it?"

* **Extract generic test cases into shared files** usable across all ports. Preserve informative SKIP messages for unsupported platforms.

* **Keep cosmetic and functional changes in separate PRs.** Mixed changes obscure the actual logic and make review harder.
  > "Please, no cosmetic changes in this PR, just functional ones."
