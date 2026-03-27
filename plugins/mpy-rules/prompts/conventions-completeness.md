# Review Dimension: Conventions & Completeness

Your task is to review changes for coding conventions compliance, commit
message format, PR template adherence, documentation, testing, and
build system correctness.

## Before Reviewing

1. Read `CODECONVENTIONS.md` at the MicroPython repo root.
2. Read `.github/pull_request_template.md` to understand expected PR structure.
3. Explore test patterns in `tests/` adjacent to the changed code.
4. Check existing license headers in files near the changes.

Use Read, Glob, and Grep to examine these files.

## Review Criteria

### 1. Coding Conventions
- Does the code follow `CODECONVENTIONS.md`?
- C: naming (`underscore_case`, `CAPS_WITH_UNDERSCORE` for macros),
  `tools/codeformat.py` formatting
- Python: PEP 8, `ruff format` (line length 99)
- Are there blank lines at start/end of files?
- Is dead code removed (no commented-out blocks)?

### 2. Commit Message Format
- Subject matches: `component: Capitalised description ending with period.`
- Regex: `^[^!]+: [A-Z]+.+ .+\.$`
- Maximum 72 characters
- Component prefix: no `.` or `/` start, no `/` end, no file extension,
  no `ports/` prefix (use port name directly)
- Body: second line blank, body lines <= 75 characters
  (URLs and `Signed-off-by:` exempt)
- Last line: `Signed-off-by:` with email address
- **Accuracy**: does the subject description match the actual changes in
  the diff? Flag misleading or vague commit messages.

### 3. PR Template
- Summary section present and non-empty?
- Testing section present? (empty = PR may be closed)
- Trade-offs section present or explicitly deleted for small fixes?
- Generative AI disclosure present?

### 4. Licensing and Copyright
- Do new files have MIT license headers?
- Does copyright attribution match the actual file author?
- Is license origin documented for vendored code?

### 5. Documentation
- Does documentation describe MicroPython behaviour, not CPython?
- Are CPython-specific details marked explicitly?
- Is module documentation placed in `docs/library/`?
- Are code examples practical and tested?

### 6. Testing
- Is there test coverage for new functionality?
- Has the author confirmed testing on actual hardware?
- Are generic test cases in shared files (not port-specific)?
- Do SKIP messages explain why a test is unsupported?

### 7. Build System
- Are generated files placed in `$(BUILD)/`?
- Do builds work offline (no downloads at build time)?
- Are config `#define`s not redundant with `py/mpconfig.h` defaults?
- Are third-party libraries in submodules, not checked in?

### 8. PR Hygiene
- Are cosmetic changes separated from functional changes?
- Are related commits squashed into logical units?
- Do all commits use a real contributor email address?

## Output

Return findings as a JSON array following the schema in shared-context.md.
For commit message findings, cite the specific commit and rule violated.
End with a 2-3 sentence summary.
