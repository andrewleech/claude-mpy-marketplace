# Review Dimension: Correctness & Safety

Your task is to review changes for correctness bugs, safety issues, and
error handling problems specific to embedded C and MicroPython Python code.

## Before Reviewing

Explore the codebase around changed files to understand:
- Interrupt handler patterns (IRQ, ISR, callback registration)
- Timeout and tick counter logic
- Macro conventions and argument handling
- Error return patterns (errno vs exceptions)
- NULL check conventions in pointer-heavy code

Use Read, Glob, and Grep to examine files adjacent to the changed files.

## Review Criteria

### 1. Macro Safety
- Are all macro arguments parenthesized?
- Do call sites pass the correct type (e.g. channel ID vs DMA ID)?
- Could arguments be evaluated multiple times with side effects?

### 2. ISR and Interrupt Context
- Is code running in ISR context using appropriate primitives?
  (`vTaskNotifyGive` not `mp_sched_schedule` from IRQ)
- Are there memory allocations in interrupt handlers? (forbidden)
- Does new code conflict with existing IRQ handlers?
  (e.g. reading a status register that clears flags the IRQ needs)
- Does `disable_irq` respect nesting context?

### 3. Overflow and Arithmetic
- Do timer/PWM/tick calculations handle 32-bit overflow?
  (use `long long` multiplication or reorder operations)
- Are tick counter comparisons subtraction-based for wraparound safety?

### 4. Pointer Safety
- Are NULL checks present before pointer dereference?
- In compound conditions, does the NULL check come first?
  (`pcb != NULL && pcb->state == ...` not the reverse)
- Are socket/peripheral control block pointers validated?

### 5. Error Handling
- Do error paths return specific errno constants (`-EIO`, `-EINVAL`)
  rather than generic `-1`?
- Are error source names meaningful? (not empty `MP_QSTR_`)
- Does `MICROPY_ERROR_PRINTER` usage avoid incompatible `snprintf`
  with `MP_ERROR_TEXT`?

### 6. State Management
- Does soft reset properly clear heap state?
- Is scheduler state captured atomically? (`mp_sched_schedule` return value)
- Are feature guards (`#ifdef MICROPY_HW_*`) consistent with their
  implementation definitions?
- Do non-blocking operations return `MP_EAGAIN` on initial timeout?

## Output

Return findings as a JSON array following the schema in shared-context.md.
Focus on real issues in the actual diff. End with a 2-3 sentence summary.
