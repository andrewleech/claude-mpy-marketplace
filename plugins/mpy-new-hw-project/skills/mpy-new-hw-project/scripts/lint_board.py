#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Lint a MicroPython board directory against the port sources of a MicroPython checkout.

Checks that pins.csv names are unique and that every port name exists in the port's pin
table. With a peripherals file it also checks that each peripheral pin offers the function
the peripheral needs, using the same rules the port code applies when it builds the object:

- stm32: alternate function table (AF_FILE of mpconfigboard.mk) and the
  MICROPY_HW_<BUS><n>_<ROLE> pin macros of mpconfigboard.h.
- mimxrt: boards/<MCU_SERIES>_af.csv and the MICROPY_HW_<BUS>_INDEX tables of
  mpconfigboard.h, which map a MicroPython bus number to the hardware instance.
- samd: mcu/<series>/pin-af-table.csv. A MICROPY_HW_DEFAULT_<KIND>_ID in mpconfigboard.h that
  matches no bus_id of that kind in the peripherals file is a warning.
- rp2: the IS_VALID_* macros of machine_spi.c, machine_uart.c and machine_i2c.h, and the
  ADC base pin of the pico-sdk platform headers. A board without a pico-sdk board header
  (PICO_BOARD none) must define the default I2C0 and SPI0 pins in mpconfigboard.h, and the
  default pin macros of one bus must be complete (I2C scl and sda, SPI sck, mosi and miso,
  UART tx, rx, cts and rts).
- esp32: the GPIO matrix routes any function to any pin; only names are checked, and GPIOn
  must be below NUM_GPIOS of ports/esp32/boards/make-pins.py.

A pins.csv row whose board name equals its pad name is an error on rp2, samd, mimxrt and esp32: those
ports address every pad by its pad name already and make-pins emits a duplicate definition.
A peripheral pin value may be a pins.csv board name or, on these ports and esp32, a pad name
of the port.

Output is JSON with the lists errors, warnings and unchecked. Exit status is 0 without
errors, 1 with errors, 2 for usage problems.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any

from common import (
    CMAKE_PORTS,
    PORTS,
    SELF_NAMED_SKIPPED_PORTS,
    dump_json,
    gpio_limit,
    gpio_range_error,
    load_json,
)

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# kind -> (required roles, optional roles, at least one of these roles)
KIND_ROLES: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "led": (("pin",), (), ()),
    "gpio": (("pin",), (), ()),
    "adc": (("pin",), (), ()),
    "pwm": (("pin",), (), ()),
    "i2c": (("scl", "sda"), (), ()),
    "spi": (("sck",), ("mosi", "miso"), ("mosi", "miso")),
    "uart": ((), ("tx", "rx"), ("tx", "rx")),
}
BUS_KINDS = ("i2c", "spi", "uart")


class UsageError(Exception):
    """Raised for problems with the inputs that stop the lint."""


# ----------------------------------------------------------------------------------------
# Board variables (mpconfigboard.mk / mpconfigboard.cmake) and header macros
# ----------------------------------------------------------------------------------------

_MK_ASSIGN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(\?=|:=|\+=|=)\s*(.*?)\s*$")
_MK_INCLUDE = re.compile(r"^\s*-?include\s+(\S+)")
_CMAKE_SET = re.compile(
    r"^\s*set\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s+(.*?)\s*\)\s*(?:#.*)?$", re.IGNORECASE
)
_CMAKE_INCLUDE = re.compile(
    r"^\s*include\s*\(\s*(\S+?)\s*(?:OPTIONAL\s*)?\)", re.IGNORECASE
)
MAX_INCLUDE_DEPTH = 4

# Names the pin generator accepts for pads that the AF table lists no alternate functions for.
GPIO_ONLY_PATTERNS = {"stm32": r"P[A-Q]\d{1,2}(?:_[A-Z])?", "samd": r"P[A-D]\d{2}"}


def _strip_value(value: str) -> str:
    value = re.sub(r"\s+#.*$", "", value).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


def _read_vars_file(
    path: Path,
    cmake: bool,
    port_dir: Path,
    board_dir: Path,
    values: dict[str, str],
    depth: int,
) -> None:
    """Add the assignments of path to values, following include lines."""
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.lstrip().startswith("#"):
            continue
        inc = (_CMAKE_INCLUDE if cmake else _MK_INCLUDE).match(raw)
        if inc:
            target = Path(expand_vars(inc.group(1), values, board_dir))
            candidates = (
                [target]
                if target.is_absolute()
                else [port_dir / target, board_dir / target]
            )
            found = next((c for c in candidates if c.is_file()), None)
            if found is not None and depth < MAX_INCLUDE_DEPTH:
                _read_vars_file(found, cmake, port_dir, board_dir, values, depth + 1)
            continue
        if cmake:
            m = _CMAKE_SET.match(raw)
            if m:
                values[m.group(1)] = _strip_value(m.group(2))
            continue
        m = _MK_ASSIGN.match(raw)
        if not m:
            continue
        name, op, value = m.group(1), m.group(2), _strip_value(m.group(3))
        if op == "?=":
            values.setdefault(name, value)
        elif op == "+=":
            values[name] = f"{values.get(name, '')} {value}".strip()
        else:
            values[name] = value


def read_board_vars(
    board_dir: Path, port_dir: Path, port: str
) -> tuple[dict[str, str], Path | None]:
    """Return the variables set by the board's mpconfigboard file and the file used.

    Included files are read where the include line stands. The cmake ports include the
    default variant file (mpconfigvariant.cmake) after the board file, so it is read too.
    """
    cmake = port in CMAKE_PORTS
    path = board_dir / ("mpconfigboard.cmake" if cmake else "mpconfigboard.mk")
    if not path.is_file():
        return {}, None
    values: dict[str, str] = {}
    _read_vars_file(path, cmake, port_dir, board_dir, values, 0)
    variant = board_dir / "mpconfigvariant.cmake"
    if cmake and variant.is_file():
        _read_vars_file(variant, cmake, port_dir, board_dir, values, 0)
    return values, path


def expand_vars(value: str, values: dict[str, str], board_dir: Path) -> str:
    """Expand $(NAME) and ${NAME} references; BOARD_DIR and MICROPY_BOARD_DIR are the board."""

    def repl(m: re.Match[str]) -> str:
        key = m.group(1) or m.group(2)
        if key in ("BOARD_DIR", "MICROPY_BOARD_DIR"):
            return str(board_dir)
        return values.get(key, m.group(0))

    return re.sub(r"\$\(([A-Za-z_0-9]+)\)|\$\{([A-Za-z_0-9]+)\}", repl, value)


_DEFINE_LINE = re.compile(r"^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)\b[ \t]*(.*)$")


def read_header_macros(path: Path) -> dict[str, str]:
    """Object-like #define values of a board header, comments removed."""
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"\\\n", " ", text)
    macros: dict[str, str] = {}
    for line in text.splitlines():
        m = _DEFINE_LINE.match(line)
        if m:
            macros[m.group(1)] = re.sub(r"//.*$", "", m.group(2)).strip()
    return macros


# ----------------------------------------------------------------------------------------
# C preprocessor subset for the rp2 pin validity macros
# ----------------------------------------------------------------------------------------

_TOKEN = re.compile(
    r"\s*(?:(0[xX][0-9a-fA-F]+|\d+)[uUlL]*|([A-Za-z_]\w*)|(&&|\|\||<<|>>|==|!=|<=|>=|[-+*/%&|^~!<>(),]))"
)


class CEvalError(Exception):
    """An expression uses a name or syntax the evaluator does not know."""


def _tokenize(text: str) -> list[tuple[str, Any]]:
    tokens: list[tuple[str, Any]] = []
    pos = 0
    text = text.rstrip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise CEvalError(f"cannot tokenize {text[pos:]!r}")
        if m.group(1) is not None:
            tokens.append(("num", int(m.group(1), 0)))
        elif m.group(2) is not None:
            tokens.append(("id", m.group(2)))
        else:
            tokens.append(("op", m.group(3)))
        pos = m.end()
    return tokens


# (name, parameters or None for object-like, body tokens)
Macro = tuple[str, "list[str] | None", "list[tuple[str, Any]]"]

_BINARY_LEVELS = (
    ("||",),
    ("&&",),
    ("|",),
    ("^",),
    ("&",),
    ("==", "!="),
    ("<", ">", "<=", ">="),
    ("<<", ">>"),
    ("+", "-"),
    ("*", "/", "%"),
)


class CEval:
    """Evaluate an integer C expression with object-like and function-like macros."""

    def __init__(self, macros: dict[str, Macro]):
        self.macros = macros

    def evaluate(
        self, tokens: list[tuple[str, Any]], env: dict[str, int] | None = None
    ) -> int:
        self._tokens = tokens
        self._pos = 0
        self._env = env or {}
        value = self._binary(0)
        if self._pos != len(tokens):
            raise CEvalError(f"unexpected token {tokens[self._pos][1]!r}")
        return value

    def call(self, name: str, args: list[int]) -> int:
        macro = self.macros.get(name)
        if macro is None or macro[1] is None:
            raise CEvalError(f"no function-like macro {name}")
        params, body = macro[1], macro[2]
        if len(params) != len(args):
            raise CEvalError(f"{name} takes {len(params)} arguments")
        return CEval(self.macros).evaluate(body, dict(zip(params, args)))

    def _peek(self) -> tuple[str, Any] | None:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _take(self) -> tuple[str, Any]:
        tok = self._peek()
        if tok is None:
            raise CEvalError("unexpected end of expression")
        self._pos += 1
        return tok

    def _binary(self, level: int) -> int:
        if level == len(_BINARY_LEVELS):
            return self._unary()
        left = self._binary(level + 1)
        while True:
            tok = self._peek()
            if tok is None or tok[0] != "op" or tok[1] not in _BINARY_LEVELS[level]:
                return left
            self._pos += 1
            right = self._binary(level + 1)
            left = self._apply(tok[1], left, right)

    @staticmethod
    def _apply(op: str, a: int, b: int) -> int:
        match op:
            case "||":
                return int(bool(a) or bool(b))
            case "&&":
                return int(bool(a) and bool(b))
            case "|":
                return a | b
            case "^":
                return a ^ b
            case "&":
                return a & b
            case "==":
                return int(a == b)
            case "!=":
                return int(a != b)
            case "<":
                return int(a < b)
            case ">":
                return int(a > b)
            case "<=":
                return int(a <= b)
            case ">=":
                return int(a >= b)
            case "<<":
                return a << b
            case ">>":
                return a >> b
            case "+":
                return a + b
            case "-":
                return a - b
            case "*":
                return a * b
            case "/":
                if b == 0:
                    raise CEvalError("division by zero")
                return a // b
            case "%":
                if b == 0:
                    raise CEvalError("division by zero")
                return a % b
        raise CEvalError(f"unknown operator {op}")

    def _unary(self) -> int:
        kind, val = self._take()
        if kind == "num":
            return val
        if kind == "op":
            if val == "(":
                value = self._binary(0)
                if self._take() != ("op", ")"):
                    raise CEvalError("missing )")
                return value
            if val == "!":
                return int(not self._unary())
            if val == "~":
                return ~self._unary()
            if val == "-":
                return -self._unary()
            if val == "+":
                return self._unary()
            raise CEvalError(f"unexpected {val!r}")
        # identifier
        if val in self._env:
            return self._env[val]
        macro = self.macros.get(val)
        if macro is None:
            raise CEvalError(f"unknown name {val}")
        if macro[1] is None:
            return CEval(self.macros).evaluate(macro[2])
        if self._peek() != ("op", "("):
            raise CEvalError(f"macro {val} needs arguments")
        self._pos += 1
        args: list[int] = []
        if self._peek() == ("op", ")"):
            self._pos += 1
        else:
            while True:
                args.append(self._binary(0))
                tok = self._take()
                if tok == ("op", ")"):
                    break
                if tok != ("op", ","):
                    raise CEvalError("bad macro argument list")
        return self.call(val, args)


_IF_NAMES = re.compile(r"[A-Za-z_]\w*")


def parse_c_macros(text: str, known: dict[str, int]) -> dict[str, Macro]:
    """Collect #define macros from C source text.

    Conditionals whose names are all in known are evaluated; every other conditional
    takes its first branch, which is the branch the pin validity macros sit in.
    """
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"\\\n", " ", text)
    macros: dict[str, Macro] = {}
    # Stack entries: [parent_active, branch_taken, active, decided_by_known]
    stack: list[list[bool]] = []

    def active() -> bool:
        return stack[-1][2] if stack else True

    def cond(expr: str) -> tuple[bool, bool]:
        names = [n for n in _IF_NAMES.findall(expr) if n != "defined"]
        if not names or any(n not in known for n in names):
            return True, False
        expr = re.sub(
            r"defined\s*\(?\s*(\w+)\s*\)?",
            lambda m: "1" if m.group(1) in known else "0",
            expr,
        )
        try:
            return bool(
                CEval({n: (n, None, [("num", v)]) for n, v in known.items()}).evaluate(
                    _tokenize(expr)
                )
            ), True
        except CEvalError:
            return True, False

    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("#"):
            continue
        directive = re.match(r"#\s*(\w+)\s*(.*)$", s)
        if not directive:
            continue
        word, rest = directive.group(1), directive.group(2).strip()
        if word in ("if", "ifdef", "ifndef"):
            parent = active()
            if word == "if":
                value, decided = cond(rest)
            else:
                name = rest.split()[0] if rest else ""
                if name in known:
                    value, decided = (name in known) == (word == "ifdef"), True
                else:
                    value, decided = True, False
            stack.append([parent, value, parent and value, decided])
        elif word == "elif" and stack:
            entry = stack[-1]
            value, decided = cond(rest)
            if entry[1] or not decided:
                entry[2] = False
            else:
                entry[2] = entry[0] and value
                entry[1] = entry[1] or value
        elif word == "else" and stack:
            entry = stack[-1]
            entry[2] = entry[0] and not entry[1]
            entry[1] = True
        elif word == "endif" and stack:
            stack.pop()
        elif word == "define" and active():
            m = re.match(r"(\w+)(\(([^)]*)\))?\s*(.*)$", rest)
            if not m:
                continue
            params = None
            if m.group(2) is not None:
                params = [p.strip() for p in m.group(3).split(",") if p.strip()]
            try:
                body = _tokenize(m.group(4))
            except CEvalError:
                continue
            macros[m.group(1)] = (m.group(1), params, body)
    return macros


# ----------------------------------------------------------------------------------------
# Pin tables
# ----------------------------------------------------------------------------------------


class PinTable:
    """Pad names of a port with the per-pad data the checks need."""

    def __init__(self, source: str):
        self.source = source
        self.pads: dict[str, dict[str, Any]] = {}

    def has(self, name: str) -> bool:
        return name in self.pads

    def signals(self, name: str) -> set[str]:
        return self.pads.get(name, {}).get("signals", set())

    def pads_with(self, wanted: set[str]) -> list[str]:
        return sorted(
            p for p, d in self.pads.items() if d.get("signals", set()) & wanted
        )


def _read_rows(path: Path) -> list[list[str]]:
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        return [row for row in csv.reader(f) if row]


def load_stm32_table(path: Path) -> PinTable:
    rows = _read_rows(path)
    header = [c.strip() for c in rows[0]]
    if "Pin" not in header:
        raise UsageError(f"{path}: no Pin column in header")
    pin_i = header.index("Pin")
    af_cols = [i for i, c in enumerate(header) if re.fullmatch(r"AF\d+", c)]
    adc_i = header.index("ADC") if "ADC" in header else None
    table = PinTable(str(path))
    for row in rows[1:]:
        if len(row) <= pin_i or not row[0].strip() or not row[pin_i].strip():
            continue
        name = row[pin_i].strip()
        signals: set[str] = set()
        for i in af_cols:
            if i < len(row):
                signals.update(t.strip() for t in row[i].split("/") if t.strip())
        adc = adc_i is not None and adc_i < len(row) and bool(row[adc_i].strip())
        table.pads[name] = {"signals": signals, "adc": adc}
    return table


def load_mimxrt_table(path: Path) -> PinTable:
    rows = _read_rows(path)
    header = [c.strip() for c in rows[0]]
    if "Pad" not in header:
        raise UsageError(f"{path}: no Pad column in header")
    alt_cols = [i for i, c in enumerate(header) if re.fullmatch(r"ALT\d+", c)]
    adc_i = header.index("ADC") if "ADC" in header else None
    table = PinTable(str(path))
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        signals = {row[i].strip() for i in alt_cols if i < len(row) and row[i].strip()}
        adc = adc_i is not None and adc_i < len(row) and bool(row[adc_i].strip())
        table.pads[row[0].strip()] = {"signals": signals, "adc": adc}
    return table


def load_samd_table(path: Path) -> PinTable:
    """Read pin-af-table.csv.

    The comment block of the file defines the encoding: eic and adc columns are decimal,
    sercom, tc and tcc columns are two hex digits with the device number first and the pad
    number second, an empty cell means the signal is not available, and only rows starting
    with pa, pb, pc or pd are data.
    """
    lines = [
        ln
        for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    rows = list(csv.reader(lines))
    header = [c.strip().lower() for c in rows[0]]
    table = PinTable(str(path))
    for row in rows[1:]:
        name = row[0].strip().upper()
        if not re.match(r"^P[ABCD]", name):
            continue
        cols = {header[i]: row[i].strip() for i in range(1, min(len(header), len(row)))}
        data: dict[str, Any] = {"signals": set(), "sercom": {}, "tc": [], "adc": False}
        for key in ("sercom1", "sercom2"):
            cell = cols.get(key, "")
            if cell:
                try:
                    value = int(cell, 16)
                except ValueError:
                    raise UsageError(
                        f"{path}: bad {key} cell {cell!r} for {name}"
                    ) from None
                data["sercom"][key] = (value >> 4, value & 0xF)
        data["adc"] = any(cols.get(k) for k in ("adc0", "adc1"))
        data["tc"] = [k for k in ("tc", "tcc1", "tcc2") if cols.get(k)]
        table.pads[name] = data
    return table


def load_rp2_table(path: Path) -> PinTable:
    rows = _read_rows(path)
    table = PinTable(str(path))
    for row in rows[1:]:
        if row and row[0].strip():
            table.pads[row[0].strip()] = {"signals": set()}
    return table


# ----------------------------------------------------------------------------------------
# Lint context
# ----------------------------------------------------------------------------------------


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.unchecked: list[str] = []

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "errors": self.errors,
            "warnings": self.warnings,
            "unchecked": self.unchecked,
        }


def read_pins_csv(path: Path, report: Report) -> tuple[dict[str, str], list[str]]:
    """Parse pins.csv like the port's pin generator (tools/boardgen.py).

    Every row has exactly two entries: a board name, which may be empty, and a port name.
    A leading "-" hides a name from Python and is dropped here. Returns the board name to
    port name mapping and the port names of all rows.
    """
    mapping: dict[str, str] = {}
    port_rows: list[str] = []
    rows = csv.reader(path.read_text(encoding="utf-8").splitlines())
    for lineno, row in enumerate(rows, 1):
        if not row or row[0].startswith("#"):
            continue
        if len(row) != 2:
            report.errors.append(
                f"pins.csv:{lineno}: expecting two entries in each row"
            )
            continue
        name, port_name = (c.strip().lstrip("-") for c in row)
        if not port_name:
            report.errors.append(f"pins.csv:{lineno}: missing port pin name")
            continue
        port_rows.append(port_name)
        if not name:
            continue
        if not IDENT_RE.match(name):
            report.errors.append(
                f"pins.csv:{lineno}: {name!r} is not a valid Python identifier"
            )
        if name in mapping and mapping[name] == port_name:
            report.warnings.append(f"pins.csv:{lineno}: {name} listed more than once")
        elif name in mapping:
            report.errors.append(
                f"pins.csv:{lineno}: duplicate pin name {name} (first maps to {mapping[name]})"
            )
        else:
            mapping[name] = port_name
    if not port_rows:
        report.errors.append("pins.csv: no pin rows")
    return mapping, port_rows


class Context:
    """Everything the port checks need."""

    def __init__(self, mpy: Path, port: str, board_dir: Path, report: Report):
        self.mpy = mpy
        self.port = port
        self.board_dir = board_dir
        self.report = report
        self.port_dir = mpy / "ports" / port
        self.vars: dict[str, str] = {}
        self.table: PinTable | None = None
        self.board_macros = read_header_macros(board_dir / "mpconfigboard.h")
        self.rp2_macros: dict[str, dict[str, Macro]] = {}
        self.rp2_adc: tuple[int, int] | None = None
        self.num_gpios: int | None = None
        self.samd_series = ""
        self.unchecked_seen: set[str] = set()
        self.board_names: dict[str, str] = {}

    # -- loading ---------------------------------------------------------------------------

    def load(self) -> None:
        values, path = read_board_vars(self.board_dir, self.port_dir, self.port)
        self.vars = values
        if path is None:
            kind = (
                "mpconfigboard.cmake"
                if self.port in CMAKE_PORTS
                else "mpconfigboard.mk"
            )
            self.report.errors.append(f"{self.board_dir}: no {kind}")
            return
        loader = getattr(self, f"_load_{self.port}")
        try:
            loader()
        except UsageError as e:
            self.report.errors.append(str(e))

    def _need(self, name: str) -> str:
        value = expand_vars(self.vars.get(name, ""), self.vars, self.board_dir)
        if not value:
            raise UsageError(f"mpconfigboard has no {name}")
        return value

    def _resolve_file(self, rel: str) -> Path:
        p = Path(rel)
        candidates = [p] if p.is_absolute() else [self.port_dir / p, self.board_dir / p]
        for c in candidates:
            if c.is_file():
                return c
        raise UsageError(f"pin table {rel} not found under {self.port_dir}")

    def _load_stm32(self) -> None:
        self.table = load_stm32_table(self._resolve_file(self._need("AF_FILE")))

    def _load_mimxrt(self) -> None:
        series = self._need("MCU_SERIES")
        self.table = load_mimxrt_table(self._resolve_file(f"boards/{series}_af.csv"))

    def _load_samd(self) -> None:
        series = self._need("MCU_SERIES")
        self.samd_series = series.upper()
        self.table = load_samd_table(
            self._resolve_file(f"mcu/{series.lower()}/pin-af-table.csv")
        )

    def _load_rp2(self) -> None:
        platform = self.vars.get("PICO_PLATFORM", "")
        if not platform:
            self.report.warnings.append(
                "mpconfigboard.cmake sets no PICO_PLATFORM; rp2040 assumed"
            )
            platform = "rp2040"
        gpios = self.vars.get("PICO_NUM_GPIOS", "30")
        is2350 = platform.startswith("rp2350")
        if not is2350:
            af = "rp2040_af.csv"
        elif gpios == "48":
            af = "rp2350b_af.csv"
        else:
            af = "rp2350_af.csv"
        self.table = load_rp2_table(self._resolve_file(f"boards/{af}"))
        known = {"PICO_RP2350": int(is2350), "PICO_RP2040": int(not is2350)}
        files = {
            "spi": "machine_spi.c",
            "uart": "machine_uart.c",
            "i2c": "machine_i2c.h",
        }
        for kind, fname in files.items():
            src = self.port_dir / fname
            if not src.is_file():
                raise UsageError(f"{src} not found")
            self.rp2_macros[kind] = parse_c_macros(
                src.read_text(errors="replace"), known
            )
        self.rp2_adc = self._rp2_adc_range(platform, gpios)

    def _rp2_adc_range(self, platform: str, gpios: str) -> tuple[int, int] | None:
        """First ADC gpio and gpio count from the pico-sdk platform_defs.h, or None."""
        chip = "rp2040" if platform == "rp2040" else "rp2350"
        header = (
            self.mpy
            / "lib/pico-sdk/src"
            / chip
            / "hardware_regs/include/hardware/platform_defs.h"
        )
        if not header.is_file():
            return None
        known = {"PICO_RP2350A": int(gpios != "48"), "PICO_RP2350B": int(gpios == "48")}
        macros = parse_c_macros(header.read_text(errors="replace"), known)
        # The SDK wraps its integer constants in _u(), which only adds a type suffix in C.
        macros["_u"] = ("_u", ["x"], [("id", "x")])
        try:
            base = CEval(macros).evaluate([("id", "ADC_BASE_PIN")])
            count = CEval(macros).evaluate([("id", "NUM_ADC_CHANNELS")])
        except CEvalError:
            return None
        # The last channel is the internal temperature sensor.
        return base, count - 1

    def _load_esp32(self) -> None:
        self.table = None
        self.num_gpios = gpio_limit("esp32", self.mpy)
        if self.num_gpios is None:
            self.report.unchecked.append(
                "esp32 pad range not checked; NUM_GPIOS not found in ports/esp32/boards/make-pins.py"
            )

    # -- helpers ---------------------------------------------------------------------------

    def note_unchecked(self, text: str) -> None:
        if text not in self.unchecked_seen:
            self.unchecked_seen.add(text)
            self.report.unchecked.append(text)

    def pad(self, port_name: str) -> str:
        """Port name with the board pin name that selected it, for messages."""
        board_name = self.board_names.get(port_name)
        if board_name and board_name != port_name:
            return f"{board_name} ({port_name})"
        return port_name

    def port_name_status(self, name: str) -> str:
        """Classify a port name: "table" for a pad of the port's table, "gpio-only" for a name
        the port accepts that the AF table has no row for, else "invalid".
        """
        if self.port == "esp32":
            if not re.fullmatch(r"GPIO\d+", name):
                return "invalid"
            return (
                "invalid"
                if gpio_range_error("esp32", name, self.num_gpios)
                else "table"
            )
        if self.table is not None and self.table.has(name):
            return "table"
        if self.port == "rp2" and re.fullmatch(r"EXT_GPIO\d+", name):
            return "table"
        pattern = GPIO_ONLY_PATTERNS.get(self.port)
        if pattern is not None and re.fullmatch(pattern, name):
            return "gpio-only"
        return "invalid"

    def range_reason(self, name: str) -> str:
        """ "; <reason>" when name is a GPIOn above the port's limit, else an empty string."""
        reason = gpio_range_error(self.port, name, self.num_gpios)
        return f"; {reason}" if reason else ""

    def valid_port_name(self, name: str) -> bool:
        return self.port_name_status(name) != "invalid"


# ----------------------------------------------------------------------------------------
# Port function checks. Each returns a list of error strings for one peripheral.
# ----------------------------------------------------------------------------------------


def _offers(table: PinTable, signals: set[str]) -> str:
    """Which pads offer any of the signals, for error messages."""
    label = " or ".join(sorted(signals))
    pads = table.pads_with(signals)
    if not pads:
        return f"no pad offers {label}"
    shown = ", ".join(pads[:8]) + (" ..." if len(pads) > 8 else "")
    return f"{label} is on {shown}"


def _int_bus(bus_id: Any) -> int | None:
    return bus_id if isinstance(bus_id, int) and not isinstance(bus_id, bool) else None


def check_stm32(ctx: Context, per: dict[str, Any], pads: dict[str, str]) -> list[str]:
    kind, bus = per["kind"], _int_bus(per.get("bus_id"))
    table = ctx.table
    assert table is not None
    errors: list[str] = []
    if kind in BUS_KINDS:
        if bus is None:
            ctx.note_unchecked(
                f"{per['name']}: bus_id {per.get('bus_id')!r} is not a number; pins not checked"
            )
            return errors
        for role, pad in pads.items():
            name = role.upper()
            if kind == "uart":
                wanted = {f"USART{bus}_{name}", f"UART{bus}_{name}"}
            else:
                wanted = {f"{kind.upper()}{bus}_{name}"}
            if not table.signals(pad) & wanted:
                errors.append(
                    f"{ctx.pad(pad)} has no {' or '.join(sorted(wanted))} for {role} of {kind} "
                    f"bus {bus}; {_offers(table, wanted)}"
                )
                continue
            hw_macro = f"MICROPY_HW_{kind.upper()}{bus}_{name}"
            declared = ctx.board_macros.get(hw_macro)
            m = re.fullmatch(r"\(?\s*pin_(\w+)\s*\)?", declared or "")
            if declared is None:
                if (ctx.board_dir / "mpconfigboard.h").is_file():
                    errors.append(
                        f"mpconfigboard.h does not define {hw_macro}; "
                        f"{kind.upper()}({bus}) has no {role} pin on this board"
                    )
            elif not m:
                ctx.note_unchecked(
                    f"{hw_macro} has value {declared!r}; not compared with pins.csv"
                )
            elif f"P{m.group(1)}" != pad:
                errors.append(
                    f"{hw_macro} is pin_{m.group(1)} but the peripheral uses {ctx.pad(pad)}"
                )
    elif kind == "adc":
        if not table.pads.get(pads["pin"], {}).get("adc"):
            errors.append(
                f"{ctx.pad(pads['pin'])} has no ADC channel in the ADC column"
            )
    elif kind == "pwm":
        if not any(
            re.fullmatch(r"TIM\d+_CH\d+N?", s) for s in table.signals(pads["pin"])
        ):
            errors.append(f"{ctx.pad(pads['pin'])} has no TIMx_CHy signal for PWM")
    return errors


def _index_table(ctx: Context, kind: str) -> list[int] | None:
    raw = ctx.board_macros.get(f"MICROPY_HW_{kind.upper()}_INDEX")
    if raw is None:
        return None
    m = re.search(r"\{([^}]*)\}", raw)
    if not m:
        return None
    try:
        return [int(v.strip(), 0) for v in m.group(1).split(",") if v.strip()]
    except ValueError:
        return None


_IOMUX_TOKEN = re.compile(r"IOMUXC_(\w+?)_(LP(?:I2C|SPI|UART)\d+)_([A-Z0-9_]+)")
_IOMUX_SIGNALS = {
    "scl": {"SCL"},
    "sda": {"SDA"},
    "sck": {"SCK"},
    "mosi": {"SDO", "SOUT"},
    "miso": {"SDI", "SIN"},
    "tx": {"TX", "TXD"},
    "rx": {"RX", "RXD"},
}


def _iomux_routes(ctx: Context, kind: str) -> set[tuple[str, str, str]] | None:
    """(pad, hardware instance, signal) of the entries in IOMUX_TABLE_<KIND>, or None when the
    board header does not define the table.
    """
    raw = ctx.board_macros.get(f"IOMUX_TABLE_{kind.upper()}")
    if raw is None:
        return None
    return {m.groups() for m in _IOMUX_TOKEN.finditer(raw)}  # type: ignore[misc]


def check_mimxrt(ctx: Context, per: dict[str, Any], pads: dict[str, str]) -> list[str]:
    kind, bus = per["kind"], _int_bus(per.get("bus_id"))
    table = ctx.table
    assert table is not None
    errors: list[str] = []
    if kind in BUS_KINDS:
        if bus is None:
            ctx.note_unchecked(
                f"{per['name']}: bus_id {per.get('bus_id')!r} is not a number; pins not checked"
            )
            return errors
        index = _index_table(ctx, kind)
        if index is None:
            ctx.note_unchecked(
                f"{per['name']}: mpconfigboard.h has no MICROPY_HW_{kind.upper()}_INDEX; "
                "the hardware instance of the bus number is unknown"
            )
            return errors
        if bus < 0 or bus >= len(index) or index[bus] == 0:
            message = (
                f"{kind.upper()}({bus}) does not exist on this board; "
                f"MICROPY_HW_{kind.upper()}_INDEX is {index}"
            )
            return [message]
        hw = index[bus]
        prefix = {"i2c": "LPI2C", "spi": "LPSPI", "uart": "LPUART"}[kind]
        names = {
            "i2c": {"scl": ("SCL",), "sda": ("SDA",)},
            "spi": {"sck": ("SCK",), "mosi": ("SOUT", "SDO"), "miso": ("SIN", "SDI")},
            "uart": {"tx": ("TXD", "TX"), "rx": ("RXD", "RX")},
        }[kind]
        for role, pad in pads.items():
            wanted = {f"{prefix}{hw}_{n}" for n in names[role]}
            if not table.signals(pad) & wanted:
                first = f"{prefix}{hw}_{names[role][0]}"
                errors.append(
                    f"{ctx.pad(pad)} has no {first} for {role} of {kind} bus {bus} "
                    f"({prefix}{hw}); {_offers(table, {first})}"
                )
                continue
            routes = _iomux_routes(ctx, kind)
            if routes is None:
                ctx.note_unchecked(
                    f"{per['name']}: mpconfigboard.h has no IOMUX_TABLE_{kind.upper()}; "
                    "the pad routing of the bus is unknown"
                )
            elif (pad, f"{prefix}{hw}") not in {
                (p, i) for p, i, sig in routes if sig in _IOMUX_SIGNALS[role]
            }:
                routed = sorted(
                    f"{p}"
                    for p, i, sig in routes
                    if i == f"{prefix}{hw}" and sig in _IOMUX_SIGNALS[role]
                )
                errors.append(
                    f"IOMUX_TABLE_{kind.upper()} does not route {ctx.pad(pad)} as {role} of "
                    f"{prefix}{hw} (bus {bus}); "
                    + (
                        f"it routes {', '.join(routed)}"
                        if routed
                        else "it routes no pad"
                    )
                )
    elif kind == "adc":
        if not table.pads.get(pads["pin"], {}).get("adc"):
            errors.append(
                f"{ctx.pad(pads['pin'])} has no ADC channel in the ADC column"
            )
    elif kind == "pwm":
        if not any(
            re.match(r"FLEXPWM\d+_PWM\d+_[ABX]$", s) for s in table.signals(pads["pin"])
        ):
            errors.append(f"{ctx.pad(pads['pin'])} has no FLEXPWM signal for PWM")
    return errors


# SPI mosi/sck pad pairs and UART tx pads accepted by ports/samd/machine_spi.c and
# machine_uart.c.
_SAMD_SPI_PADS = {
    "SAMD21": {(0, 1), (2, 3), (3, 1), (0, 3)},
    "SAMD51": {(0, 1), (3, 1)},
}
_SAMD_UART_TX_PADS = {"SAMD21": {0, 2}, "SAMD51": {0}}


def _samd_pad(table: PinTable, pad: str, sercom: int) -> int | None:
    """Pad number the pin has on the given SERCOM; first match like get_sercom_config()."""
    cells = table.pads.get(pad, {}).get("sercom", {})
    for key in ("sercom1", "sercom2"):
        if key in cells and cells[key][0] == sercom:
            return cells[key][1]
    return None


def check_samd(ctx: Context, per: dict[str, Any], pads: dict[str, str]) -> list[str]:
    kind, bus = per["kind"], _int_bus(per.get("bus_id"))
    table = ctx.table
    assert table is not None
    errors: list[str] = []
    if kind in BUS_KINDS:
        if bus is None:
            ctx.note_unchecked(
                f"{per['name']}: bus_id {per.get('bus_id')!r} is not a number; pins not checked"
            )
            return errors
        found: dict[str, int] = {}
        for role, pad in pads.items():
            num = _samd_pad(table, pad, bus)
            if num is None:
                where = sorted(
                    f"{p}(SERCOM{d}:{n})"
                    for p, data in table.pads.items()
                    for d, n in data.get("sercom", {}).values()
                    if d == bus
                )
                errors.append(
                    f"{ctx.pad(pad)} has no SERCOM{bus} pad for {role} of {kind} bus {bus}; "
                    + (
                        f"SERCOM{bus} pins: {', '.join(where)}"
                        if where
                        else "no SERCOM pins"
                    )
                )
            else:
                found[role] = num
        series = ctx.samd_series if ctx.samd_series in _SAMD_SPI_PADS else "SAMD51"
        if kind == "i2c":
            for role, want in (("sda", 0), ("scl", 1)):
                if role in found and found[role] != want:
                    errors.append(
                        f"{ctx.pad(pads[role])} is SERCOM{bus} pad {found[role]}; "
                        f"I2C {role} needs pad {want}"
                    )
        elif kind == "spi":
            if "mosi" not in pads:
                errors.append(
                    "samd SPI needs mosi; the port raises ValueError without it"
                )
            elif (
                "mosi" in found
                and "sck" in found
                and (found["mosi"], found["sck"]) not in _SAMD_SPI_PADS[series]
            ):
                allowed = ", ".join(
                    f"mosi={m}/sck={s}" for m, s in sorted(_SAMD_SPI_PADS[series])
                )
                errors.append(
                    f"SERCOM{bus} pads mosi={found['mosi']}, sck={found['sck']} are not a "
                    f"supported pair on {series}; allowed: {allowed}"
                )
        elif kind == "uart":
            if "tx" not in pads:
                errors.append(
                    "samd UART needs tx; the port rejects a UART without a tx pad"
                )
            elif "tx" in found and found["tx"] not in _SAMD_UART_TX_PADS[series]:
                allowed = sorted(_SAMD_UART_TX_PADS[series])
                errors.append(
                    f"{ctx.pad(pads['tx'])} is SERCOM{bus} pad {found['tx']}; "
                    f"UART tx needs pad {allowed}"
                )
    elif kind == "adc":
        if not table.pads.get(pads["pin"], {}).get("adc"):
            errors.append(
                f"{ctx.pad(pads['pin'])} has no ADC channel (adc0/adc1 columns)"
            )
    elif kind == "pwm":
        if not table.pads.get(pads["pin"], {}).get("tc"):
            errors.append(f"{ctx.pad(pads['pin'])} has no TC/TCC signal for PWM")
    return errors


_RP2_MACROS = {
    ("i2c", "scl"): "IS_VALID_SCL",
    ("i2c", "sda"): "IS_VALID_SDA",
    ("spi", "sck"): "IS_VALID_SCK",
    ("spi", "mosi"): "IS_VALID_MOSI",
    ("spi", "miso"): "IS_VALID_MISO",
    ("uart", "tx"): "IS_VALID_TX",
    ("uart", "rx"): "IS_VALID_RX",
}


def check_rp2(ctx: Context, per: dict[str, Any], pads: dict[str, str]) -> list[str]:
    kind, bus = per["kind"], _int_bus(per.get("bus_id"))
    errors: list[str] = []
    number = {
        pad: int(m.group(1))
        for pad in pads.values()
        if (m := re.fullmatch(r"GPIO(\d+)", pad))
    }
    if kind in BUS_KINDS:
        if bus is None:
            ctx.note_unchecked(
                f"{per['name']}: bus_id {per.get('bus_id')!r} is not a number; pins not checked"
            )
            return errors
        macros = ctx.rp2_macros[kind]
        for role, pad in pads.items():
            if pad not in number:
                errors.append(
                    f"{ctx.pad(pad)} is not a GPIO pad; {kind} {role} needs GPIOn"
                )
                continue
            macro = _RP2_MACROS[(kind, role)]
            try:
                ok = CEval(macros).call(macro, [bus, number[pad]])
            except CEvalError as e:
                ctx.note_unchecked(f"{per['name']}: cannot evaluate {macro}: {e}")
                continue
            if not ok:
                errors.append(
                    f"{ctx.pad(pad)} cannot be {role} of {kind.upper()}({bus}); "
                    f"{macro}({bus}, {number[pad]}) is false"
                )
    elif kind == "adc":
        pad = pads["pin"]
        if pad not in number:
            errors.append(f"{ctx.pad(pad)} is not a GPIO pad; ADC needs GPIOn")
        elif ctx.rp2_adc is None:
            ctx.note_unchecked(
                f"{per['name']}: ADC pins not checked; lib/pico-sdk platform_defs.h not in checkout"
            )
        else:
            base, count = ctx.rp2_adc
            if not base <= number[pad] < base + count:
                errors.append(
                    f"{ctx.pad(pad)} is not an ADC pin; ADC gpios are {base} to {base + count - 1}"
                )
    elif kind == "pwm":
        if pads["pin"] not in number:
            errors.append(f"{ctx.pad(pads['pin'])} is not a GPIO pad; PWM needs GPIOn")
    return errors


def check_rp2_defaults(ctx: Context) -> None:
    """Default pin macros of mpconfigboard.h that machine_i2c.h, machine_spi.c and
    machine_uart.c need.

    Each bus guards on its first macro (#ifndef MICROPY_HW_I2C0_SCL, #if !defined(
    MICROPY_HW_UART0_TX)), so the others must come with it. Without a pico-sdk board header
    PICO_DEFAULT_I2C and PICO_DEFAULT_SPI are undefined, which the preprocessor reads as 0:
    I2C0 and SPI0 then fall back to PICO_DEFAULT_*_PIN names that do not exist.
    """
    if not (ctx.board_dir / "mpconfigboard.h").is_file():
        return
    macros = ctx.board_macros
    report = ctx.report
    no_header = ctx.vars.get("PICO_BOARD", "none").lower() == "none"
    if no_header and ctx.vars.get("PICO_BOARD_HEADER_DIRS"):
        no_header = False
        ctx.note_unchecked(
            "PICO_BOARD_HEADER_DIRS is set; whether a board header supplies the default "
            "I2C and SPI pins is not checked"
        )
    groups = {
        "I2C": (("SCL", "SDA"), "MICROPY_HW_I2C_NO_DEFAULT_PINS"),
        "SPI": (("SCK", "MOSI", "MISO"), "MICROPY_HW_SPI_NO_DEFAULT_PINS"),
    }
    for kind, (roles, no_default) in groups.items():
        for bus in (0, 1):
            names = [f"MICROPY_HW_{kind}{bus}_{r}" for r in roles]
            have = [n for n in names if n in macros]
            if no_default in macros:
                continue
            if no_header and bus == 0 and not have:
                report.errors.append(
                    f"mpconfigboard.h defines no {names[0]}; without a pico-sdk board header "
                    f"{kind}0 default pins fall back to PICO_DEFAULT_* names that do not exist. "
                    f"Define {', '.join(names)} or {no_default}"
                )
            elif have and len(have) != len(names):
                missing = [n for n in names if n not in macros]
                report.errors.append(
                    f"mpconfigboard.h defines {', '.join(have)} but not {', '.join(missing)}; "
                    f"define all of {', '.join(names)}"
                )
    for bus in (0, 1):
        names = [f"MICROPY_HW_UART{bus}_{r}" for r in ("TX", "RX", "CTS", "RTS")]
        have = [n for n in names if n in macros]
        if have and len(have) != len(names):
            missing = [n for n in names if n not in macros]
            report.errors.append(
                f"mpconfigboard.h defines {', '.join(have)} but not {', '.join(missing)}; "
                f"machine_uart.c needs all of {', '.join(names)} once any is defined"
            )


def check_samd_defaults(ctx: Context, peripherals: list[Any]) -> None:
    """Warn when MICROPY_HW_DEFAULT_<KIND>_ID names a bus no peripheral declares."""
    for kind in BUS_KINDS:
        macro = f"MICROPY_HW_DEFAULT_{kind.upper()}_ID"
        raw = ctx.board_macros.get(macro)
        if raw is None:
            continue
        m = re.fullmatch(r"\(?\s*(-?\d+)\s*\)?", raw)
        if not m:
            ctx.note_unchecked(
                f"{macro} has value {raw!r}; not compared with peripherals.json"
            )
            continue
        value = int(m.group(1))
        if value < 0:
            continue
        ids = {
            per.get("bus_id")
            for per in peripherals
            if isinstance(per, dict) and per.get("kind") == kind
        }
        if value not in ids:
            ctx.report.warnings.append(
                f"{macro} is {value} but no {kind} peripheral has bus_id {value}"
            )


def check_esp32(ctx: Context, per: dict[str, Any], pads: dict[str, str]) -> list[str]:
    if per["kind"] in ("i2c", "spi", "uart", "adc", "pwm"):
        ctx.note_unchecked(
            f"{per['name']}: {per['kind']} pin functions not checked; the esp32 GPIO matrix "
            "routes bus and PWM functions to any pin (ADC pins depend on the exact chip, see "
            "the chip datasheet)"
        )
    return []


CHECKERS = {
    "stm32": check_stm32,
    "mimxrt": check_mimxrt,
    "samd": check_samd,
    "rp2": check_rp2,
    "esp32": check_esp32,
}


# ----------------------------------------------------------------------------------------
# Peripherals
# ----------------------------------------------------------------------------------------


def check_peripherals(
    ctx: Context, board_pins: dict[str, str] | None, peripherals: list[Any]
) -> None:
    report = ctx.report
    names: set[str] = set()
    usage: dict[str, list[str]] = {}

    def resolve(pin: Any, where: str) -> str | None:
        if not isinstance(pin, str) or not pin:
            report.errors.append(f"{where}: pin name must be a non-empty string")
            return None
        if board_pins is None:
            if ctx.port in CMAKE_PORTS and ctx.valid_port_name(pin):
                return pin
            if ctx.port == "esp32" and re.fullmatch(r"\d+", pin):
                return f"GPIO{pin}"
            report.errors.append(
                f"{where}: pin {pin} cannot be resolved without pins.csv"
                + ctx.range_reason(pin)
            )
            return None
        if (
            pin not in board_pins
            and ctx.port != "stm32"
            and ctx.port_name_status(pin) == "table"
        ):
            return pin
        if pin not in board_pins:
            report.errors.append(f"{where}: pin {pin} is not in pins.csv")
            return None
        return board_pins[pin]

    for i, per in enumerate(peripherals):
        if not isinstance(per, dict):
            report.errors.append(f"peripherals[{i}]: must be an object")
            continue
        name = per.get("name")
        kind = per.get("kind")
        label = f"peripheral {name!r}" if name else f"peripherals[{i}]"
        if not isinstance(name, str) or not IDENT_RE.match(name):
            report.errors.append(f"{label}: name must be a Python identifier")
            continue
        if name in names:
            report.errors.append(f"{label}: duplicate peripheral name")
        names.add(name)
        if kind not in KIND_ROLES:
            report.errors.append(
                f"{label}: unknown kind {kind!r}; expected one of {list(KIND_ROLES)}"
            )
            continue
        required, optional, one_of = KIND_ROLES[kind]
        pins = per.get("pins")
        if not isinstance(pins, dict):
            report.errors.append(f"{label}: pins must be an object")
            continue
        for role in pins:
            if role not in required + optional:
                report.errors.append(
                    f"{label}: unexpected pin role {role!r} for kind {kind}"
                )
        for role in required:
            if role not in pins:
                report.errors.append(f"{label}: pins.{role} missing")
        if one_of and not any(r in pins for r in one_of):
            report.errors.append(
                f"{label}: needs at least one of pins.{', pins.'.join(one_of)}"
            )
        if kind in BUS_KINDS and "bus_id" not in per:
            report.errors.append(f"{label}: bus_id missing")

        resolved: dict[str, str] = {}
        for role, pin in pins.items():
            if role not in required + optional:
                continue
            port_name = resolve(pin, f"{label} pins.{role}")
            if port_name is None:
                continue
            if not ctx.valid_port_name(port_name):
                report.errors.append(
                    f"{label} pins.{role}: {pin} maps to {port_name}, not a pad of this port"
                    + ctx.range_reason(port_name)
                )
                continue
            resolved[role] = port_name
            ctx.board_names[port_name] = pin
            usage.setdefault(port_name, []).append(f"{name}.{role}")

        for dev in (
            per.get("devices", []) if isinstance(per.get("devices"), list) else []
        ):
            cs = dev.get("cs") if isinstance(dev, dict) else None
            if cs is None:
                continue
            port_name = resolve(cs, f"{label} device {dev.get('name')!r} cs")
            if port_name is not None:
                if not ctx.valid_port_name(port_name):
                    report.errors.append(
                        f"{label} device {dev.get('name')!r} cs: {cs} maps to {port_name}, "
                        "not a pad of this port"
                    )
                else:
                    usage.setdefault(port_name, []).append(
                        f"{name}.{dev.get('name')}.cs"
                    )

        complete = all(r in resolved for r in pins if r in required + optional)
        if complete and not any(e.startswith(label) for e in report.errors):
            for err in CHECKERS[ctx.port](ctx, per, resolved):
                report.errors.append(f"{label}: {err}")

    if ctx.port == "samd":
        check_samd_defaults(ctx, peripherals)

    for port_name, users in sorted(usage.items()):
        if len(users) > 1:
            report.warnings.append(f"{port_name} is used by {', '.join(users)}")


# ----------------------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------------------


def lint_board(
    micropython: Path, port: str, board_dir: Path, peripherals_file: Path | None = None
) -> dict[str, list[str]]:
    if port not in PORTS:
        raise UsageError(f"port must be one of {', '.join(PORTS)}")
    if not (micropython / "ports" / port).is_dir():
        raise UsageError(f"{micropython}/ports/{port} not found")
    if not board_dir.is_dir():
        raise UsageError(f"board directory {board_dir} not found")
    report = Report()
    ctx = Context(micropython, port, board_dir, report)
    ctx.load()

    pins_csv = board_dir / "pins.csv"
    board_pins: dict[str, str] | None = None
    if pins_csv.is_file():
        board_pins, port_rows = read_pins_csv(pins_csv, report)
        seen_gpio_only: set[str] = set()
        table_name = ctx.table.source if ctx.table else "the table"
        for port_name in port_rows:
            status = ctx.port_name_status(port_name)
            if status == "invalid":
                report.errors.append(
                    f"pins.csv: {port_name} is not a pad of the {port} port"
                    + ctx.range_reason(port_name)
                )
            elif status == "gpio-only" and port_name not in seen_gpio_only:
                seen_gpio_only.add(port_name)
                report.warnings.append(
                    f"pins.csv: {port_name} has no row in {table_name}; only plain GPIO use "
                    "is possible"
                )
    elif port in CMAKE_PORTS:
        report.warnings.append(
            f"no pins.csv; {port} boards may use {port} pin names directly"
        )
    else:
        report.errors.append(f"{pins_csv} not found")
    if board_pins and port in SELF_NAMED_SKIPPED_PORTS:
        for name, port_name in board_pins.items():
            if name == port_name:
                report.errors.append(
                    f"pins.csv: {name} is listed under its own pad name; the {port} port "
                    f"defines pin_{name} for every pad, so make-pins emits a duplicate "
                    "definition. Remove the row"
                )

    if port == "rp2" and ctx.table is not None:
        check_rp2_defaults(ctx)

    if peripherals_file is not None:
        try:
            data = load_json(peripherals_file)
        except (OSError, ValueError) as e:
            raise UsageError(f"cannot read {peripherals_file}: {e}") from None
        items = data.get("peripherals") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise UsageError(
                f'{peripherals_file}: top level must be {{"peripherals": [...]}}'
            )
        if ctx.table is not None or port == "esp32":
            check_peripherals(ctx, board_pins, items)
        else:
            report.unchecked.append(
                "peripherals not checked; the pin table could not be loaded"
            )
    return report.as_dict()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Lint a MicroPython board directory against the port sources.",
    )
    p.add_argument(
        "--micropython", required=True, type=Path, help="MicroPython checkout"
    )
    p.add_argument("--port", required=True, choices=PORTS)
    p.add_argument(
        "--board-dir", required=True, type=Path, help="board definition directory"
    )
    p.add_argument(
        "--peripherals", type=Path, help="peripherals.json to check against the board"
    )
    p.add_argument(
        "-o", "--output", help="write the JSON report here instead of stdout"
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = lint_board(
            args.micropython, args.port, args.board_dir, args.peripherals
        )
    except UsageError as e:
        print(f"lint_board: {e}", file=sys.stderr)
        return 2
    dump_json(result, args.output)
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
