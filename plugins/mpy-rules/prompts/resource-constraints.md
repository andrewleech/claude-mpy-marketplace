# Review Dimension: Resource Constraints

Your task is to review changes for code size impact, memory usage, and
performance on resource-constrained embedded targets.

## Before Reviewing

Explore the codebase around changed files to understand:
- Which ports are affected by the changes (bare-arm, minimal, stm32, esp32, rp2, unix)
- Build configuration flags (`MICROPY_PY_*`) that gate features
- Existing patterns for const data, struct layout, and allocation
- Whether the changed code is in a hot path (polling, IRQ, inner loop)

Use Read, Glob, and Grep to examine build configs and adjacent code.

## Review Criteria

### 1. Code Size
- Will this increase `.text`/`.data`/`.bss` across port builds?
- Are new features gated behind config flags for minimal ports?
- Can large lookup tables or verbose strings be avoided?
- Are there redundant config `#define`s that duplicate defaults
  from `py/mpconfig.h`?

### 2. Heap Allocation
- Is `MP_OBJ_NEW_SMALL_INT()` used for values fitting the small-int range?
  (`mp_obj_new_int()` triggers heap allocation)
- Is `m_new`/`m_del` used instead of raw `gc_alloc`/`gc_free`?
- Are pointers passed to external libraries in GC-scanned memory
  or stack-allocated?
- Are there allocations in hot paths (pixel setters, polling loops,
  tight inner loops)?

### 3. Struct and Data Layout
- Are struct fields ordered to minimise padding?
- Is immutable data declared `const` so it resides in flash, not RAM?
- Are mutable fields separated from const data where needed?

### 4. Qstr Impact
- Do new qstr additions increase size for ports that don't use them
  (bare-arm, minimal)?
- Are internal constants prefixed with underscore to avoid export?
- Are redundant path prefixes stripped to reduce qstr storage?

### 5. Performance
- Are loop-invariant expressions hoisted outside loops?
- Is `uint32_t` used with `mp_hal_ticks_ms` for timeout tracking?
- Are unnecessary NLR (non-local return) setups avoided where GC
  can reclaim memory?
- Would the change benefit from performance benchmarks on target hardware?
  (note this in findings if so)

## Output

Return findings as a JSON array following the schema in shared-context.md.
Quantify impact where possible ("this adds N bytes to bare-arm .text").
End with a 2-3 sentence summary.
