#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Generate the hardware skeleton of an mpy-app-template project from peripherals.json.

Writes three files under src/firmware:

- application/device_config.py: pin names, bus ids, frequencies and device addresses.
- application/hardware.py: every peripheral constructed with the port's constructor form,
  collected on DeviceCollection.
- test/test_hardware.py: unittest file for the unix port with mock_machine.

It also patches application/device.py and deletes test/test_blink.py when the design has no
led peripheral.

Constructor forms follow docs/<port>/quickref.rst of MicroPython:

- rp2, esp32, samd: the bus pins are constructor arguments.
    I2C(id, scl=Pin(..), sda=Pin(..), freq=..)
    SPI(id, baudrate=.., sck=Pin(..), mosi=Pin(..), miso=Pin(..))
    UART(id, baudrate=.., tx=Pin(..), rx=Pin(..))
- stm32, mimxrt: the board definition fixes the bus pins for each id.
    I2C(id, freq=..), SPI(id, baudrate=..), UART(id, baudrate=..)

Exit status is 0 on success, 1 when the design cannot be generated, 2 for usage problems.
"""

from __future__ import annotations

import argparse
import ast
import keyword
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from common import (
    PORTS,
    SELF_NAMED_SKIPPED_PORTS,
    dump_json,
    load_json,
    port_name_pattern,
)
from lint_board import IDENT_RE, KIND_ROLES

LINE_LENGTH = 99
INDENT = "    "

APP_DIR = Path("src/firmware/application")
TEST_DIR = Path("src/firmware/test")

# Ports whose bus constructors take the pins; stm32 and mimxrt take the id only because the
# board definition fixes the pins of each id.
PIN_ARGUMENT_PORTS = {"rp2", "esp32", "samd"}

# The kinds each port's machine module can construct in the forms above.
SUPPORTED_KINDS = {port: set(KIND_ROLES) for port in PORTS}

DEFAULTS = {"i2c": 400000, "spi": 1000000, "uart": 115200, "pwm": 1000}

# Longest peripheral or device name; the names appear in constants, attributes and test names.
MAX_NAME_LENGTH = 24

# Names hardware.py or the test already uses at module level or on DeviceCollection.
RESERVED = {
    "ADC",
    "Blinky",
    "DeviceCollection",
    "I2C",
    "InvertedPin",
    "PWM",
    "Pin",
    "SPI",
    "UART",
    "asyncio",
    "blinky",
    "device_config",
    "devices",
    "hardware",
    "led",
    "log",
    "logging",
    "machine",
    "shutdown",
}

# device.py text with and without the Blinky task.
DEVICE_EDITS = (
    ("TASKS = (devices.blinky.task,)", "TASKS = ()"),
    ("    start_repl()\n    devices.blinky.start()\n", "    start_repl()\n"),
)

INVERTED_PIN = '''class InvertedPin:
    """Wraps an active-low pin so that value(1) turns it on."""

    def __init__(self, pin):
        self.pin = pin

    def value(self, val=None):
        if val is None:
            return 0 if self.pin.value() else 1
        self.pin.value(0 if val else 1)
        return None'''

COLLECTION_DOC = (
    '"""The device\'s hardware, gathered so tests can substitute the lot."""'
)


class GenError(Exception):
    """The design or the project cannot be turned into code."""


# ----------------------------------------------------------------------------------------
# Source rendering
# ----------------------------------------------------------------------------------------


@dataclass
class Call:
    """A call expression that renders on one line when it fits, else one argument per line."""

    func: str
    args: list[tuple[str | None, str | Call]] = field(default_factory=list)

    def flat(self) -> str:
        parts = [
            (f"{k}=" if k else "") + (v.flat() if isinstance(v, Call) else v)
            for k, v in self.args
        ]
        return f"{self.func}({', '.join(parts)})"

    def classes(self) -> set[str]:
        found = {self.func}
        for _, value in self.args:
            if isinstance(value, Call):
                found |= value.classes()
        return found

    def render(self, indent: int, prefix: str = "", suffix: str = "") -> list[str]:
        """Lines of the statement, each carrying its own indentation."""
        flat = prefix + self.flat() + suffix
        if indent + len(flat) <= LINE_LENGTH:
            return [" " * indent + flat]
        lines = [" " * indent + prefix + self.func + "("]
        for key, value in self.args:
            head = f"{key}=" if key else ""
            if isinstance(value, Call):
                lines += value.render(indent + 4, head, ",")
            else:
                lines.append(" " * (indent + 4) + head + value + ",")
        lines.append(" " * indent + ")" + suffix)
        return lines


def def_lines(indent: int, name: str, params: list[str]) -> list[str]:
    """A def statement, one parameter per line with a trailing comma when it is too long."""
    pad = " " * indent
    line = f"{pad}def {name}({', '.join(params)}):"
    if len(line) <= LINE_LENGTH:
        return [line]
    return [f"{pad}def {name}(", *[f"{pad}{INDENT}{p}," for p in params], f"{pad}):"]


def quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def tuple_lines(indent: str, head: str, items: list[str]) -> list[str]:
    """An assignment of a tuple; one item per line with a trailing comma, as ruff keeps it."""
    if len(items) == 1:
        line = f"{indent}{head}({items[0]},)"
        if len(line) <= LINE_LENGTH:
            return [line]
    return [f"{indent}{head}(", *[f"{indent}{INDENT}{i}," for i in items], f"{indent})"]


# ----------------------------------------------------------------------------------------
# Design model
# ----------------------------------------------------------------------------------------


@dataclass
class Device:
    name: str
    ident: str
    addr: int | None
    part: str | None
    cs: str | None


@dataclass
class Periph:
    name: str
    ident: str  # lower case, the attribute on DeviceCollection
    const: str  # upper case, the constant prefix in device_config
    kind: str
    spec: dict[str, Any]
    pins: dict[str, str]  # role -> board pin name
    devices: list[Device] = field(default_factory=list)


@dataclass
class Attribute:
    """One object DeviceCollection holds."""

    name: str
    cls: str  # machine class the object is an instance of
    call: Call


def _ident(text: str, what: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", text)
    if not IDENT_RE.match(cleaned) or keyword.iskeyword(cleaned):
        raise GenError(f"{what} {text!r} cannot be used as a Python name")
    return cleaned


def _int(value: Any, what: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise GenError(f"{what} must be an integer, got {value!r}")
    try:
        number = int(value, 0) if isinstance(value, str) else value
    except ValueError:
        raise GenError(f"{what} must be an integer, got {value!r}") from None
    if number < minimum:
        raise GenError(f"{what} must be at least {minimum}, got {number}")
    return number


def parse_design(data: Any, port: str) -> list[Periph]:
    """Validate peripherals.json content and normalise it."""
    items = data.get("peripherals") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise GenError('peripherals file must be {"peripherals": [...]}')
    result: list[Periph] = []
    used: dict[str, str] = {}
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise GenError(f"peripherals[{i}] must be an object")
        name, kind = raw.get("name"), raw.get("kind")
        if not isinstance(name, str) or not name:
            raise GenError(f"peripherals[{i}] has no name")
        if kind not in KIND_ROLES:
            raise GenError(f"peripheral {name!r}: unknown kind {kind!r}")
        if kind not in SUPPORTED_KINDS[port]:
            raise GenError(
                f"kind {kind} is not generated for port {port}; write it by hand"
            )
        # The led peripheral is the Blinky; it has no attribute or constant prefix of its own.
        ident = "led" if kind == "led" else _claim(name, "peripheral name", used)
        required, optional, one_of = KIND_ROLES[kind]
        pins = raw.get("pins")
        if not isinstance(pins, dict):
            raise GenError(f"peripheral {name!r}: pins must be an object")
        for role, pin in pins.items():
            if role not in required + optional:
                raise GenError(f"peripheral {name!r}: unexpected pin role {role!r}")
            if not isinstance(pin, str) or not pin:
                raise GenError(f"peripheral {name!r}: pins.{role} must be a pin name")
        for role in required:
            if role not in pins:
                raise GenError(f"peripheral {name!r}: pins.{role} missing")
        if one_of and not any(r in pins for r in one_of):
            raise GenError(
                f"peripheral {name!r}: needs one of pins.{', pins.'.join(one_of)}"
            )
        periph = Periph(name, ident, ident.upper(), kind, raw, dict(pins))
        if kind in ("i2c", "spi", "uart"):
            if "bus_id" not in raw:
                raise GenError(f"peripheral {name!r}: bus_id missing")
            _int(raw["bus_id"], f"peripheral {name!r} bus_id")
        devices = raw.get("devices") or []
        if not isinstance(devices, list):
            raise GenError(f"peripheral {name!r}: devices must be a list")
        for dev in devices:
            periph.devices.append(_parse_device(periph, dev, used))
        result.append(periph)
    if sum(p.kind == "led" for p in result) > 1:
        raise GenError(
            "only one led peripheral is generated; declare other LEDs as gpio outputs"
        )
    return result


def _claim(name: str, what: str, used: dict[str, str]) -> str:
    """Python identifier for name; rejects reserved or already used identifiers."""
    ident = _ident(name, what).lower()
    if len(ident) > MAX_NAME_LENGTH:
        raise GenError(
            f"{what} {name!r} is longer than {MAX_NAME_LENGTH} characters; "
            "shorter names keep the generated lines inside the line length"
        )
    if ident in RESERVED:
        raise GenError(f"{what} {name!r}: {ident!r} is reserved by hardware.py")
    if ident in used:
        raise GenError(f"{what} {name!r}: {ident!r} is already used by {used[ident]!r}")
    used[ident] = name
    return ident


def _parse_device(periph: Periph, dev: Any, used: dict[str, str]) -> Device:
    if not isinstance(dev, dict) or not isinstance(dev.get("name"), str):
        raise GenError(f"peripheral {periph.name!r}: each device needs a name")
    ident = _claim(dev["name"], "device name", used)
    addr = dev.get("addr")
    if periph.kind == "i2c" and addr is not None:
        addr = _int(addr, f"device {dev['name']!r} addr")
        if addr > 0x7F:
            raise GenError(
                f"device {dev['name']!r}: addr {addr:#x} is not a 7-bit address"
            )
    cs = dev.get("cs")
    if cs is not None and (periph.kind != "spi" or not isinstance(cs, str) or not cs):
        raise GenError(
            f"device {dev['name']!r}: cs applies to spi devices and must be a pin name"
        )
    return Device(
        dev["name"], ident, addr if periph.kind == "i2c" else None, dev.get("part"), cs
    )


# ----------------------------------------------------------------------------------------
# Pins
# ----------------------------------------------------------------------------------------


def read_pins_csv(path: Path) -> dict[str, str]:
    """Board name -> port name; a leading "-" (hidden pin) is dropped from both."""
    mapping: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        cols = [c.strip() for c in line.split(",")]
        if len(cols) >= 2 and cols[0] and cols[1]:
            mapping.setdefault(cols[0].lstrip("-"), cols[1].lstrip("-"))
    return mapping


class PinNames:
    """Turns a board pin name into the value the port's Pin() takes."""

    def __init__(self, port: str, mapping: dict[str, str] | None):
        self.port = port
        self.mapping = mapping
        # Literals produced from names the generated board test can look up, and from names
        # it cannot (see is_unchecked).
        self.checked: set[str] = set()
        self.unchecked: set[str] = set()

    def is_unchecked(self, name: str) -> bool:
        """True for a pin value the board test cannot look up.

        rp2, samd, mimxrt and esp32 accept a pad name (esp32: also a GPIO number) in Pin()
        without a pins.csv row. The test's Pin.board and Pin.cpu are built from pins.csv
        rows only, so such a value has no entry there; lint_board.py covers it.
        """
        if self.port not in SELF_NAMED_SKIPPED_PORTS:
            return False
        if self.mapping is not None and name in self.mapping:
            return False
        return re.fullmatch(r"\d+", name) is not None or (
            port_name_pattern(self.port).match(name) is not None
        )

    def literal(self, name: str) -> str:
        value = quote(name) if self.port != "esp32" else str(self._esp32_number(name))
        (self.unchecked if self.is_unchecked(name) else self.checked).add(value)
        return value

    def board_checked(self, value: str) -> bool:
        """True when some pin of the design with this literal can be looked up in the test."""
        return value in self.checked or value not in self.unchecked

    def _esp32_number(self, name: str) -> int:
        """esp32 Pin() takes the GPIO number; board names come from pins.csv."""
        if re.fullmatch(r"\d+", name):
            return int(name)
        target = self.mapping.get(name, name) if self.mapping is not None else name
        m = re.fullmatch(r"GPIO(\d+)", target)
        if m:
            return int(m.group(1))
        if self.mapping is None or name not in self.mapping:
            raise GenError(
                f"esp32 pin {name!r} has no GPIO number; pass --pins-csv with a row '{name},GPIOn'"
            )
        raise GenError(f"esp32 pin {name!r} maps to {target!r}, which is not GPIOn")


# ----------------------------------------------------------------------------------------
# Reading the template files
# ----------------------------------------------------------------------------------------


def _parse(path: Path) -> tuple[str, ast.Module]:
    source = path.read_text(encoding="utf-8")
    try:
        return source, ast.parse(source)
    except SyntaxError as e:
        raise GenError(f"{path} does not parse: {e}") from None


def _docstring(source: str, tree: ast.Module, path: Path) -> str:
    first = tree.body[0] if tree.body else None
    if not (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        raise GenError(f"{path} has no module docstring; restore it from the template")
    return "\n".join(source.splitlines()[: first.end_lineno])


def _assignment(source: str, tree: ast.Module, name: str) -> str | None:
    """Source of the assignment to name with the comment lines directly above it."""
    lines = source.splitlines()
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == name
        ):
            start = node.lineno - 1
            while start > 0 and lines[start - 1].lstrip().startswith("#"):
                start -= 1
            return "\n".join(lines[start : node.end_lineno])
    return None


def _class_source(source: str, tree: ast.Module, name: str) -> str | None:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return "\n".join(source.splitlines()[node.lineno - 1 : node.end_lineno])
    return None


# ----------------------------------------------------------------------------------------
# device_config.py
# ----------------------------------------------------------------------------------------


class ConfigBuilder:
    """Collects constants and refuses duplicates."""

    def __init__(self) -> None:
        self.owner: dict[str, str] = {}
        self.values: dict[str, str] = {}
        self.pin_constants: list[str] = []

    def const(
        self, name: str, value: str, owner: str, comment: str | None = None
    ) -> str:
        if name in self.owner:
            raise GenError(
                f"constant {name} is generated for both {self.owner[name]} and {owner}"
            )
        self.owner[name] = owner
        self.values[name] = value
        if name.endswith("_PIN"):
            self.pin_constants.append(name)
        return f"{name} = {value}" + (f"  # {comment}" if comment else "")


def gen_device_config(
    existing: Path, design: list[Periph], pins: PinNames, notes: list[str]
) -> tuple[str, list[str]]:
    """Return the text of device_config.py and the names of its *_PIN constants."""
    source, tree = _parse(existing)
    doc = _docstring(source, tree, existing)
    autorun = _assignment(source, tree, "AUTORUN")
    log_level = _assignment(source, tree, "LOG_LEVEL")
    if autorun is None or log_level is None:
        raise GenError(
            f"{existing} lacks AUTORUN or LOG_LEVEL; restore it from the template"
        )
    cfg = ConfigBuilder()
    blocks: list[str] = [doc, "import logging"]

    led = next((p for p in design if p.kind == "led"), None)
    if led is not None:
        polarity = "active high" if led.spec.get("active_high", True) else "active low"
        pin_line = cfg.const("LED_PIN", pins.literal(led.pins["pin"]), led.name)
        blocks.append(f"# Pin driving the status LED, {polarity}.\n{pin_line}")
        timing = [_assignment(source, tree, n) for n in ("LED_ON_TIME", "LED_OFF_TIME")]
        if timing[0] is None or timing[1] is None:
            notes.append(
                "LED_ON_TIME and LED_OFF_TIME were not in device_config.py; set to 1.0"
            )
            timing = [
                "# Blink timing, in seconds.\nLED_ON_TIME = 1.0",
                "LED_OFF_TIME = 1.0",
            ]
        cfg.owner["LED_ON_TIME"] = cfg.owner["LED_OFF_TIME"] = led.name
        blocks.append("\n".join(t for t in timing if t))
    for p in design:
        if p.kind != "led":
            blocks.append(_peripheral_constants(p, pins, cfg))
    blocks += [autorun, log_level]
    board_constants = [
        n for n in cfg.pin_constants if pins.board_checked(cfg.values[n])
    ]
    return "\n\n".join(blocks) + "\n", board_constants


def _peripheral_constants(p: Periph, pins: PinNames, cfg: ConfigBuilder) -> str:
    lines: list[str] = []

    def add(suffix: str, value: str) -> None:
        lines.append(cfg.const(f"{p.const}_{suffix}", value, p.name))

    def add_pins(*roles: str) -> None:
        for role in roles:
            if role in p.pins:
                add(f"{role.upper()}_PIN", pins.literal(p.pins[role]))

    def number(key: str, default: int | None = None) -> str:
        return str(_int(p.spec.get(key, default), f"{p.name} {key}", 1))

    if p.kind == "gpio":
        lines.append(f"# {p.name}: gpio {p.spec.get('direction', 'in')}put")
        add("PIN", pins.literal(p.pins["pin"]))
    elif p.kind == "adc":
        lines.append(f"# {p.name}: analog input")
        add("PIN", pins.literal(p.pins["pin"]))
    elif p.kind == "pwm":
        lines.append(f"# {p.name}: PWM output")
        add("PIN", pins.literal(p.pins["pin"]))
        add("FREQ", number("freq", DEFAULTS["pwm"]))
    elif p.kind == "i2c":
        lines.append(f"# {p.name}: I2C bus")
        add("ID", str(_int(p.spec["bus_id"], f"{p.name} bus_id")))
        add("FREQ", number("freq", DEFAULTS["i2c"]))
        if pins.port in PIN_ARGUMENT_PORTS:
            add_pins("scl", "sda")
        for dev in p.devices:
            if dev.addr is not None:
                name = f"{dev.ident.upper()}_ADDR"
                lines.append(cfg.const(name, f"0x{dev.addr:02x}", dev.name, dev.part))
    elif p.kind == "spi":
        lines.append(f"# {p.name}: SPI bus")
        add("ID", str(_int(p.spec["bus_id"], f"{p.name} bus_id")))
        add("BAUDRATE", number("baudrate", DEFAULTS["spi"]))
        if pins.port in PIN_ARGUMENT_PORTS:
            add_pins("sck", "mosi", "miso")
        for dev in p.devices:
            if dev.cs is not None:
                name = f"{dev.ident.upper()}_CS_PIN"
                lines.append(cfg.const(name, pins.literal(dev.cs), dev.name, dev.part))
    elif p.kind == "uart":
        lines.append(f"# {p.name}: UART")
        add("ID", str(_int(p.spec["bus_id"], f"{p.name} bus_id")))
        add("BAUDRATE", number("baudrate", DEFAULTS["uart"]))
        if pins.port in PIN_ARGUMENT_PORTS:
            add_pins("tx", "rx")
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------
# hardware.py
# ----------------------------------------------------------------------------------------

PIN_PULLS = {"up": "Pin.PULL_UP", "down": "Pin.PULL_DOWN"}


def _pin(const: str) -> Call:
    return Call("Pin", [(None, f"device_config.{const}")])


def _pin_out(const: str, value: int) -> Call:
    return Call(
        "Pin",
        [(None, f"device_config.{const}"), (None, "Pin.OUT"), ("value", str(value))],
    )


def attributes_for(p: Periph, port: str) -> list[Attribute]:
    """The objects p adds to DeviceCollection."""
    c = p.const
    if p.kind == "gpio":
        direction = p.spec.get("direction", "in")
        if direction == "out":
            value = _int(p.spec.get("value", 0), f"{p.name} value")
            return [Attribute(p.ident, "Pin", _pin_out(f"{c}_PIN", 1 if value else 0))]
        if direction != "in":
            raise GenError(f"peripheral {p.name!r}: direction must be in or out")
        pull = p.spec.get("pull")
        if pull not in (None, "none", "up", "down"):
            raise GenError(f"peripheral {p.name!r}: pull must be up, down or none")
        args: list[tuple[str | None, str | Call]] = [
            (None, f"device_config.{c}_PIN"),
            (None, "Pin.IN"),
        ]
        if pull in PIN_PULLS:
            args.append((None, PIN_PULLS[pull]))
        return [Attribute(p.ident, "Pin", Call("Pin", args))]
    if p.kind == "adc":
        return [Attribute(p.ident, "ADC", Call("ADC", [(None, _pin(f"{c}_PIN"))]))]
    if p.kind == "pwm":
        args = [
            (None, _pin(f"{c}_PIN")),
            ("freq", f"device_config.{c}_FREQ"),
            ("duty_u16", "0"),
        ]
        return [Attribute(p.ident, "PWM", Call("PWM", args))]
    if p.kind in ("i2c", "spi", "uart"):
        selects = [
            Attribute(f"{d.ident}_cs", "Pin", _pin_out(f"{d.ident.upper()}_CS_PIN", 1))
            for d in p.devices
            if d.cs is not None
        ]
        return [Attribute(p.ident, p.kind.upper(), _bus_call(p, port)), *selects]
    raise GenError(f"kind {p.kind} is not generated for port {port}")


def _bus_call(p: Periph, port: str) -> Call:
    c = p.const
    if p.kind == "i2c":
        rate_key, rate = "freq", f"device_config.{c}_FREQ"
        roles: tuple[str, ...] = ("scl", "sda")
    else:
        rate_key, rate = "baudrate", f"device_config.{c}_BAUDRATE"
        roles = ("sck", "mosi", "miso") if p.kind == "spi" else ("tx", "rx")
    args: list[tuple[str | None, str | Call]] = [(None, f"device_config.{c}_ID")]
    if port in PIN_ARGUMENT_PORTS:
        pin_args = [(r, _pin(f"{c}_{r.upper()}_PIN")) for r in roles if r in p.pins]
        if p.kind == "i2c":
            # I2C keeps the pins ahead of freq, as in the quickref.
            args += [*pin_args, (rate_key, rate)]
        else:
            args += [(rate_key, rate), *pin_args]
    else:
        args.append((rate_key, rate))
    return Call(p.kind.upper(), args)


def gen_hardware_py(
    existing: Path, design: list[Periph], port: str
) -> tuple[str, list[Attribute], bool]:
    """Return the text of hardware.py, its DeviceCollection attributes and whether it reads
    device_config."""
    source, tree = _parse(existing)
    doc = _docstring(source, tree, existing)
    led = next((p for p in design if p.kind == "led"), None)
    blinky = None
    if led is not None:
        blinky = _class_source(source, tree, "Blinky")
        if blinky is None:
            raise GenError(
                f"{existing} has no Blinky class; restore it from the template"
            )
    active_low = led is not None and not led.spec.get("active_high", True)

    attributes = [a for p in design if p.kind != "led" for a in attributes_for(p, port)]
    seen_names: set[str] = set()
    for a in attributes:
        if a.name in seen_names or a.name in RESERVED:
            raise GenError(
                f"two objects would be named devices.{a.name}; rename a peripheral"
            )
        seen_names.add(a.name)
    classes = {"Pin"} if led is not None else set()
    for a in attributes:
        classes |= a.call.classes()
    machine_names = sorted(classes, key=lambda n: (not n.isupper(), n))
    uses_config = led is not None or bool(attributes)

    out: list[str] = [doc, ""]
    if blinky is not None:
        out.append("import asyncio")
    out.append("import logging")
    if machine_names:
        out += ["", f"from machine import {', '.join(machine_names)}"]
    if uses_config:
        out += ["", "import device_config"]
    out += ["", 'log = logging.getLogger("hardware")', "", ""]
    if blinky is not None:
        out += [blinky, "", ""]
    if active_low:
        out += [INVERTED_PIN, "", ""]

    params = ["self"] + (["blinky"] if led else []) + [a.name for a in attributes]
    out += ["class DeviceCollection:", f"{INDENT}{COLLECTION_DOC}", ""]
    if len(params) > 1:
        out += def_lines(1 * 4, "__init__", params)
        out += [f"{INDENT * 2}self.{n} = {n}" for n in params[1:]]
    else:
        out += [f"{INDENT}def __init__(self):", f"{INDENT * 2}pass"]
    out += ["", ""]

    if led is not None:
        led_pin = Call(
            "Pin",
            [
                (None, "device_config.LED_PIN"),
                (None, "Pin.OUT"),
                ("value", "1" if active_low else "0"),
            ],
        )
        out += [*led_pin.render(0, "led = "), ""]

    members: list[tuple[str, Call]] = []
    if led is not None:
        pin_expr = "InvertedPin(led)" if active_low else "led"
        members.append(
            (
                "blinky",
                Call(
                    "Blinky",
                    [
                        (None, pin_expr),
                        (None, "device_config.LED_ON_TIME"),
                        (None, "device_config.LED_OFF_TIME"),
                    ],
                ),
            )
        )
    members += [(a.name, a.call) for a in attributes]
    if members:
        out.append("devices = DeviceCollection(")
        for key, call in members:
            out += call.render(4, f"{key}=", ",")
        out.append(")")
    else:
        out.append("devices = DeviceCollection()")

    shutdown = [f"{INDENT}devices.blinky.stop()"] if led else []
    shutdown += [
        f"{INDENT}devices.{a.name}.duty_u16(0)" for a in attributes if a.cls == "PWM"
    ]
    out += ["", "", "def shutdown():", *(shutdown or [f"{INDENT}pass"])]
    return "\n".join(out) + "\n", attributes, led is not None


# ----------------------------------------------------------------------------------------
# test_hardware.py
# ----------------------------------------------------------------------------------------


def _test_class(name: str, methods: list[list[str]]) -> list[str]:
    lines = [f"class {name}(unittest.TestCase):"]
    for i, method in enumerate(methods):
        if i:
            lines.append("")
        lines += [INDENT + m for m in method]
    return lines


def gen_test_py(
    design: list[Periph],
    attributes: list[Attribute],
    port: str,
    board_name: str,
    pin_constants: list[str],
    with_board_file: bool,
) -> str:
    led = next((p for p in design if p.kind == "led"), None)
    active_low = led is not None and not led.spec.get("active_high", True)
    on, off = (0, 1) if active_low else (1, 0)
    pwms = [p for p in design if p.kind == "pwm"]
    classes = {a.cls for a in attributes}
    uses_config = False
    methods: list[list[str]] = []

    expected = ['("blinky", hardware.Blinky)'] if led else []
    expected += [f'("{a.name}", {a.cls})' for a in attributes]
    if expected:
        methods.append(
            [
                "def test_devices_have_the_generated_types(self):",
                *tuple_lines("    ", "expected = ", expected),
                "    for name, cls in expected:",
                "        self.assertTrue(hasattr(hardware.devices, name), name)",
                "        self.assertIsInstance(getattr(hardware.devices, name), cls)",
            ]
        )
    if led:
        methods.append(
            [
                "def test_led_follows_its_polarity(self):",
                "    hardware.devices.blinky.pin.value(1)",
                f"    self.assertEqual(hardware.led.value(), {on})",
                "    hardware.devices.blinky.pin.value(0)",
                f"    self.assertEqual(hardware.led.value(), {off})",
            ]
        )
    for p in design:
        if p.kind == "gpio" and p.spec.get("direction", "in") == "out":
            classes.add("Pin")
            value = 1 if _int(p.spec.get("value", 0), f"{p.name} value") else 0
            methods.append(
                [
                    f"def test_{p.ident}_starts_as_an_output_at_{value}(self):",
                    f"    pin = hardware.devices.{p.ident}",
                    "    self.assertEqual(pin.mode(), Pin.OUT)",
                    f"    self.assertEqual(pin.value(), {value})",
                ]
            )
        elif p.kind == "gpio":
            classes.add("Pin")
            methods.append(
                [
                    f"def test_{p.ident}_is_an_input(self):",
                    f"    self.assertEqual(hardware.devices.{p.ident}.mode(), Pin.IN)",
                ]
            )
        elif p.kind == "pwm":
            uses_config = True
            methods.append(
                [
                    f"def test_{p.ident}_starts_off_at_the_configured_frequency(self):",
                    f"    pwm = hardware.devices.{p.ident}",
                    f"    self.assertEqual(pwm.freq(), device_config.{p.const}_FREQ)",
                    "    self.assertEqual(pwm.duty_u16(), 0)",
                ]
            )
        for dev in p.devices:
            if dev.cs is not None:
                classes.add("Pin")
                methods.append(
                    [
                        f"def test_{dev.ident}_chip_select_is_an_idle_high_output(self):",
                        f"    pin = hardware.devices.{dev.ident}_cs",
                        "    self.assertEqual(pin.mode(), Pin.OUT)",
                        "    self.assertEqual(pin.value(), 1)",
                    ]
                )
    if led or pwms:
        body = ["def test_shutdown_turns_the_outputs_off(self):"]
        if led:
            body.append("    hardware.devices.blinky.pin.value(1)")
        body += [f"    hardware.devices.{p.ident}.duty_u16(1000)" for p in pwms]
        body.append("    hardware.shutdown()")
        if led:
            body.append(f"    self.assertEqual(hardware.led.value(), {off})")
        body += [
            f"    self.assertEqual(hardware.devices.{p.ident}.duty_u16(), 0)"
            for p in pwms
        ]
        methods.append(body)
    if not methods:
        methods.append(["def test_shutdown_runs(self):", "    hardware.shutdown()"])

    sections = [_test_class("TestDevices", methods)]
    if with_board_file:
        classes.add("Pin")
        board = [
            [
                "def setUp(self):",
                "    Pin.board.configure(PINS_CSV)  # type: ignore[attr-defined]",
            ],
            [
                "def tearDown(self):",
                "    Pin.board.configure(None)  # type: ignore[attr-defined]",
            ],
            [
                "def test_board_file_is_loaded(self):",
                '    self.assertFalse(hasattr(Pin.board, "NOT_A_BOARD_PIN"))',
            ],
        ]
        if pin_constants:
            uses_config = True
            if port == "esp32":
                check = (
                    '    self.assertTrue(hasattr(Pin.cpu, "GPIO%d" % pin), name)'
                    "  # type: ignore[attr-defined]"
                )
            else:
                check = "    self.assertTrue(hasattr(Pin.board, pin), name)"
            board.append(
                [
                    "def test_pin_constants_exist_on_the_board(self):",
                    "    for name in PIN_CONSTANTS:",
                    "        pin = getattr(device_config, name)",
                    "    " + check,
                ]
            )
        sections.append(_test_class("TestBoardPins", board))

    out = ["import unittest", ""]
    if uses_config:
        out.append("import device_config")
    out.append("import hardware")
    if classes:
        names = sorted(classes, key=lambda n: (not n.isupper(), n))
        out.append(f"from machine import {', '.join(names)}")
    if with_board_file:
        out += [
            "",
            "# Tests run with src/unix/build/frozen_mpy as the working directory.",
            f'PINS_CSV = "../../../../src/system/{board_name}/pins.csv"',
        ]
        if pin_constants:
            out += [
                "",
                *tuple_lines("", "PIN_CONSTANTS = ", [quote(n) for n in pin_constants]),
            ]
    for section in sections:
        out += ["", "", *section]
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------------------
# Project files
# ----------------------------------------------------------------------------------------


def git_changes(project: Path, files: list[Path]) -> list[Path]:
    """Existing files that differ from HEAD; raises when the project is not a git checkout."""
    existing = [f for f in files if (project / f).exists()]
    if not existing:
        return []
    try:
        inside = subprocess.run(
            ["git", "-C", str(project), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as e:
        raise GenError(f"cannot run git: {e}; use --force to overwrite") from None
    if inside.returncode != 0:
        raise GenError(f"{project} is not a git checkout; use --force to overwrite")
    status = subprocess.run(
        ["git", "-C", str(project), "status", "--porcelain", "--", *map(str, existing)],
        capture_output=True,
        text=True,
        check=True,
    )
    changed = {line[3:].strip('"') for line in status.stdout.splitlines()}
    return [f for f in existing if str(f) in changed]


def patch_device_py(text: str, has_led: bool) -> str:
    """Return device.py text for the design.

    Each edit has a led form and a plain form. The text is changed to the form the design
    needs; it fails when neither form is present.
    """
    for led_form, plain_form in DEVICE_EDITS:
        if led_form in text:
            current_led = True
        elif plain_form in text:
            current_led = False
        else:
            raise GenError(
                f"device.py has neither {led_form!r} nor {plain_form!r}; edit by hand"
            )
        if current_led and not has_led:
            text = text.replace(led_form, plain_form, 1)
        elif not current_led and has_led:
            text = text.replace(plain_form, led_form, 1)
    return text


def generate(args: argparse.Namespace) -> dict[str, Any]:
    project: Path = args.project
    port: str = args.port
    app = project / APP_DIR
    for name in ("device_config.py", "hardware.py", "device.py"):
        if not (app / name).is_file():
            raise GenError(f"{app / name} not found; not an app-template project")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.board_name):
        raise GenError(f"board name {args.board_name!r} is not a directory name")
    try:
        design = parse_design(load_json(args.peripherals), port)
    except (OSError, ValueError) as e:
        raise GenError(f"cannot read {args.peripherals}: {e}") from None

    board_file = project / "src/system" / args.board_name / "pins.csv"
    csv_path = args.pins_csv if args.pins_csv is not None else board_file
    mapping = None
    if csv_path.is_file():
        mapping = read_pins_csv(csv_path)
    elif args.pins_csv is not None:
        raise GenError(f"{args.pins_csv} not found")
    notes: list[str] = []
    if args.pins_csv is not None and args.pins_csv.resolve() != board_file.resolve():
        notes.append(
            f"{args.pins_csv} is not {board_file}; test_hardware.py uses the board file"
        )
    if mapping is not None and port != "esp32":
        for p in design:
            for pin in [*p.pins.values(), *[d.cs for d in p.devices if d.cs]]:
                if pin not in mapping:
                    notes.append(f"pin {pin} of {p.name} is not in {csv_path}")

    targets = {
        "device_config": app / "device_config.py",
        "hardware": app / "hardware.py",
        "test": project / TEST_DIR / "test_hardware.py",
    }
    pins = PinNames(port, mapping)
    config_text, pin_constants = gen_device_config(
        targets["device_config"], design, pins, notes
    )
    hardware_text, attributes, has_led = gen_hardware_py(
        targets["hardware"], design, port
    )
    test_text = gen_test_py(
        design, attributes, port, args.board_name, pin_constants, board_file.is_file()
    )
    device_path = app / "device.py"
    device_old = device_path.read_text(encoding="utf-8")
    device_new = patch_device_py(device_old, has_led)
    blink = project / TEST_DIR / "test_blink.py"
    delete_blink = not has_led and blink.exists()

    if not args.force:
        touched = [t.relative_to(project) for t in targets.values()]
        touched.append(device_path.relative_to(project))
        if delete_blink:
            touched.append(blink.relative_to(project))
        changed = git_changes(project, touched)
        if changed:
            raise GenError(
                "these files differ from git HEAD or are not tracked yet: "
                + ", ".join(map(str, changed))
                + ". Commit the previous output, or use --force to overwrite them"
            )

    result: dict[str, Any] = {
        "written": [],
        "patched": [],
        "deleted": [],
        "notes": notes,
    }
    texts = {"device_config": config_text, "hardware": hardware_text, "test": test_text}
    for key, path in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(texts[key], encoding="utf-8")
        result["written"].append(str(path.relative_to(project)))
    if device_new != device_old:
        device_path.write_text(device_new, encoding="utf-8")
        result["patched"].append(str(device_path.relative_to(project)))
    if delete_blink:
        blink.unlink()
        result["deleted"].append(str(blink.relative_to(project)))
    return result


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate device_config.py, hardware.py and test_hardware.py for an "
        "mpy-app-template project from peripherals.json.",
    )
    p.add_argument("--project", required=True, type=Path, help="project root")
    p.add_argument("--port", required=True, choices=PORTS)
    p.add_argument("--peripherals", required=True, type=Path, help="peripherals.json")
    p.add_argument(
        "--board-name", required=True, help="directory name under src/system"
    )
    p.add_argument(
        "--pins-csv", type=Path, help="pins.csv to resolve esp32 pin numbers"
    )
    p.add_argument(
        "--force", action="store_true", help="overwrite files that differ from HEAD"
    )
    p.add_argument(
        "-o", "--output", help="write the JSON summary here instead of stdout"
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.project.is_dir():
        print(f"gen_hardware: {args.project} is not a directory", file=sys.stderr)
        return 2
    try:
        result = generate(args)
    except GenError as e:
        print(f"gen_hardware: {e}", file=sys.stderr)
        dump_json({"errors": [str(e)]}, args.output)
        return 1
    dump_json(result, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
