# Review Dimension: API & Portability

Your task is to review changes for API design quality, CPython compatibility,
cross-port consistency, and portability across hardware platforms.

## Before Reviewing

Explore the codebase to understand:
- How similar APIs are implemented across other ports (esp32, stm32, rp2)
- Parameter naming conventions for the same interface on different ports
- CPython signatures for any modules being modified
- Hardware abstraction patterns in extmod/ vs ports/

Use Read, Glob, and Grep to examine equivalent implementations across ports.

## Review Criteria

### 1. CPython Compatibility
- Do APIs named after CPython modules have compatible signatures?
- Are deviations from CPython documented and justified?
- Do basic usage patterns work identically on both platforms?
- Are lazy imports (trading IDE introspection for memory) explicit
  and justified?

### 2. Cross-Port Consistency
- Do parameter names match across all port implementations of the
  same interface? (e.g. if esp32 uses `password`, stm32 should too)
- Are public constants consistent across LAN and WLAN interfaces?
- Do getter/setter method semantics match across similar APIs?

### 3. Hardware Abstraction
- Is port-specific code in `ports/*/` rather than `extmod/` or `py/`?
- Are abstraction layers used instead of direct HAL calls?
- Are enum values stable across build configurations for ABI compatibility?
- Do cross-platform assumptions (`alloca.h` vs `malloc.h`, endianness)
  use `#if`/`#ifdef` with documented rationale?

### 4. API Surface
- Is `mp_obj_get_array()` used to accept both tuples and lists?
- Is `mp_obj_is_true()` used for boolean conversion?
- Are wrapper classes avoided where direct use of `Pin`, `SPI`, etc.
  would suffice?
- Do unimplemented methods raise exceptions rather than returning stubs?
- Are configurable parameters (baudrate, pin mode) not hardcoded?

### 5. Configuration
- Do board configs set final values directly (`MICROPY_HEAP_START`,
  `MICROPY_HEAP_END`) without intermediate variables?
- Is `MICROPY_VERSION` available for third-party library detection?
- Are public constants exposed in the module locals dict?

## Output

Return findings as a JSON array following the schema in shared-context.md.
When flagging inconsistency, cite the specific port or module that differs.
End with a 2-3 sentence summary.
