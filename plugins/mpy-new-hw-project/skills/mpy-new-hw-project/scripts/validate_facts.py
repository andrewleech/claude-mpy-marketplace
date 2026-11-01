#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Check the JSON fact files of a generated project (hardware/facts/).

Stages:
  mcu          mcu.json (and nets.json when present)
  pinmap       pinmap.json
  peripherals  peripherals.json
  all          mcu, then pinmap when pinmap.json or nets.json exists, then peripherals

Prints {"ok", "errors", "warnings"} as JSON. Exit 1 when there is any error.
"""

from __future__ import annotations

import argparse
import keyword
import re
import sys
from pathlib import Path
from typing import Any

from common import (
    PORTS,
    SOURCES,
    board_pin_name,
    dump_json,
    is_unnamed_net,
    load_json,
    port_name_pattern,
)

KINDS = ("led", "gpio", "i2c", "spi", "uart", "adc", "pwm")
BUS_KINDS = ("i2c", "spi", "uart")
# kind -> (required pin roles, pin roles of which at least one is required)
PIN_ROLES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "led": (("pin",), ()),
    "gpio": (("pin",), ()),
    "i2c": (("scl", "sda"), ()),
    "spi": (("sck",), ("mosi", "miso")),
    "uart": ((), ("tx", "rx")),
    "adc": (("pin",), ()),
    "pwm": (("pin",), ()),
}
ALLOWED_ROLES = {
    "led": {"pin"},
    "gpio": {"pin"},
    "i2c": {"scl", "sda"},
    "spi": {"sck", "mosi", "miso"},
    "uart": {"tx", "rx", "rts", "cts"},
    "adc": {"pin"},
    "pwm": {"pin"},
}
STAGES = ("mcu", "pinmap", "peripherals", "all")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")


def _load(path: Path, rep: Report, required: bool) -> Any | None:
    if not path.is_file():
        if required:
            rep.error(path.name, "file is missing")
        return None
    try:
        return load_json(path)
    except ValueError as e:
        rep.error(path.name, f"invalid JSON: {e}")
        return None


def _require(
    obj: dict[str, Any], keys: tuple[str, ...], where: str, rep: Report
) -> None:
    for k in keys:
        if k not in obj:
            rep.error(where, f"missing required key '{k}'")
        elif obj[k] in (None, ""):
            rep.error(where, f"key '{k}' is empty")


def _check_source(obj: dict[str, Any], where: str, rep: Report) -> None:
    if "source" not in obj:
        rep.error(where, "missing required key 'source'")
    elif obj["source"] not in SOURCES:
        rep.error(where, f"source '{obj['source']}' is not one of {', '.join(SOURCES)}")


def check_nets(doc: Any, rep: Report) -> None:
    where = "nets.json"
    if not isinstance(doc, dict):
        rep.error(where, "top level must be an object")
        return
    _require(doc, ("format", "components", "nets"), where, rep)
    if doc.get("format") not in (None, "kicad", "protel", "csv"):
        rep.error(where, f"unknown format '{doc.get('format')}'")
    nets = doc.get("nets")
    if isinstance(nets, dict):
        for name, nodes in nets.items():
            if not isinstance(nodes, list):
                rep.error(where, f"net '{name}' must be a list of nodes")
                continue
            for n in nodes:
                if not isinstance(n, dict) or "ref" not in n or "pin" not in n:
                    rep.error(where, f"net '{name}' has a node without ref or pin")
                    break


def check_mcu(
    doc: Any, nets: Any | None, rep: Report, seed_required: bool = True
) -> dict[str, Any] | None:
    where = "mcu.json"
    if not isinstance(doc, dict):
        rep.error(where, "top level must be an object")
        return None
    _require(doc, ("part", "port", "mcu_ref", "package"), where, rep)
    if "seed_board" not in doc:
        rep.error(where, "missing required key 'seed_board'")
    elif doc["seed_board"] in (None, ""):
        # The seed board is chosen after extraction, so it is empty until then.
        if seed_required:
            rep.error(where, "key 'seed_board' is empty")
        else:
            rep.warn(
                where,
                "key 'seed_board' is empty; pick the seed board before stage 'all'",
            )
    _check_source(doc, where, rep)
    port = doc.get("port")
    if port is not None and port not in PORTS:
        rep.error(where, f"port '{port}' is not one of {', '.join(PORTS)}")
    if port in ("stm32", "mimxrt", "samd") and not doc.get("series"):
        rep.warn(where, f"no 'series' for port {port}")
    if isinstance(nets, dict) and doc.get("mcu_ref"):
        comps = nets.get("components", {})
        used = any(
            n.get("ref") == doc["mcu_ref"]
            for nodes in nets.get("nets", {}).values()
            if isinstance(nodes, list)
            for n in nodes
            if isinstance(n, dict)
        )
        if doc["mcu_ref"] not in comps and not used:
            rep.error(where, f"mcu_ref '{doc['mcu_ref']}' is not in nets.json")
    return doc


def check_pinmap(doc: Any, mcu: dict[str, Any] | None, rep: Report) -> None:
    where = "pinmap.json"
    if not isinstance(doc, dict):
        rep.error(where, "top level must be an object")
        return
    _require(doc, ("port", "mcu_ref", "status"), where, rep)
    for key in ("pins", "anchors", "errors"):
        if not isinstance(doc.get(key), list):
            rep.error(where, f"key '{key}' must be a list")
    if doc.get("status") not in (None, "ok"):
        rep.error(
            where, f"status is '{doc.get('status')}'; the pin gate has not passed"
        )
    port = doc.get("port")
    if port is not None and port not in PORTS:
        rep.error(where, f"port '{port}' is not one of {', '.join(PORTS)}")
        return
    if mcu:
        for key in ("port", "mcu_ref"):
            if key in mcu and key in doc and mcu[key] != doc[key]:
                rep.error(
                    where, f"{key} '{doc[key]}' differs from mcu.json '{mcu[key]}'"
                )
    if (
        doc.get("status") == "ok"
        and not doc.get("anchors")
        and not doc.get("confirmed")
    ):
        rep.error(where, "no anchors and the table is not marked confirmed")
    if not isinstance(doc.get("pins"), list) or port is None:
        return
    pat = port_name_pattern(port)
    seen_pins: set[str] = set()
    seen_ports: set[str] = set()
    owner: dict[str, str] = {}
    for p in doc["pins"]:
        if not isinstance(p, dict):
            rep.error(where, "pins entry is not an object")
            continue
        missing = [
            k for k in ("package_pin", "port_name", "net", "anchor") if k not in p
        ]
        if missing:
            rep.error(where, f"pins entry lacks {', '.join(missing)}")
            continue
        if p["package_pin"] in seen_pins:
            rep.error(where, f"duplicate package pin {p['package_pin']}")
        seen_pins.add(p["package_pin"])
        if p["port_name"] in seen_ports:
            rep.error(where, f"duplicate port name {p['port_name']}")
        seen_ports.add(p["port_name"])
        if not pat.match(p["port_name"]) and port != "mimxrt":
            rep.error(where, f"'{p['port_name']}' is not a valid {port} port name")
        if not is_unnamed_net(p["net"]):
            name = board_pin_name(p["net"])
            if name in owner and owner[name] != p["net"]:
                rep.error(
                    where,
                    f"duplicate board pin name {name} from nets '{owner[name]}' and '{p['net']}'",
                )
            owner.setdefault(name, p["net"])
    for a in doc.get("anchors", []):
        if not isinstance(a, dict) or not {"package_pin", "port_name", "net"} <= set(a):
            rep.error(where, "anchors entry lacks package_pin, port_name or net")


def _check_devices(per: dict[str, Any], where: str, rep: Report) -> None:
    devices = per.get("devices")
    if devices is None:
        return
    if not isinstance(devices, list):
        rep.error(where, "'devices' must be a list")
        return
    names: set[str] = set()
    for d in devices:
        if not isinstance(d, dict) or not d.get("name"):
            rep.error(where, "a device lacks 'name'")
            continue
        if d["name"] in names:
            rep.error(where, f"duplicate device name '{d['name']}'")
        names.add(d["name"])
        if per.get("kind") == "i2c":
            addr = d.get("addr")
            if addr is None:
                rep.error(where, f"device '{d['name']}' lacks 'addr'")
            else:
                try:
                    int(str(addr), 0)
                except ValueError:
                    rep.error(
                        where, f"device '{d['name']}' addr '{addr}' is not a number"
                    )
        if per.get("kind") == "spi" and not d.get("cs"):
            rep.error(where, f"device '{d['name']}' lacks 'cs'")


def check_peripherals(doc: Any, rep: Report) -> None:
    where_top = "peripherals.json"
    if not isinstance(doc, dict) or not isinstance(doc.get("peripherals"), list):
        rep.error(where_top, "top level must be an object with a 'peripherals' list")
        return
    names: set[str] = set()
    pin_users: dict[str, str] = {}
    for i, per in enumerate(doc["peripherals"]):
        if not isinstance(per, dict):
            rep.error(where_top, f"entry {i} is not an object")
            continue
        name = per.get("name")
        where = f"peripherals.json[{name or i}]"
        _require(per, ("name", "kind", "pins"), where, rep)
        _check_source(per, where, rep)
        if isinstance(name, str):
            if (
                not name.isidentifier()
                or keyword.iskeyword(name)
                or not re.match(r"^[a-z_]", name)
            ):
                rep.error(where, "name must be a lower case Python identifier")
            if name in names:
                rep.error(where, "duplicate peripheral name")
            names.add(name)
        kind = per.get("kind")
        if kind is None:
            continue
        if kind not in KINDS:
            rep.error(
                where, f"unknown kind '{kind}', expected one of {', '.join(KINDS)}"
            )
            continue
        pins = per.get("pins")
        if not isinstance(pins, dict):
            rep.error(where, "'pins' must be an object")
            continue
        required, any_of = PIN_ROLES[kind]
        for role in required:
            if not pins.get(role):
                rep.error(where, f"{kind} needs pin role '{role}'")
        if any_of and not any(pins.get(r) for r in any_of):
            rep.error(where, f"{kind} needs at least one of: {', '.join(any_of)}")
        for role in pins:
            if role not in ALLOWED_ROLES[kind]:
                rep.error(where, f"unknown pin role '{role}' for kind {kind}")
        for role, pin in pins.items():
            if not isinstance(pin, str) or not pin:
                rep.error(where, f"pin role '{role}' must be a non-empty string")
                continue
            prev = pin_users.get(pin)
            if prev and prev != name:
                rep.warn(where, f"pin {pin} is also used by '{prev}'")
            pin_users.setdefault(pin, str(name))
        if kind in BUS_KINDS and not isinstance(per.get("bus_id"), int):
            rep.error(where, f"{kind} needs integer 'bus_id'")
        if kind == "gpio" and per.get("direction") not in ("in", "out"):
            rep.error(where, "gpio needs 'direction' of 'in' or 'out'")
        if per.get("pull") not in (None, "up", "down", "none"):
            rep.error(where, f"pull '{per.get('pull')}' is not 'up', 'down' or 'none'")
        if (
            kind == "led"
            and "active_high" in per
            and not isinstance(per["active_high"], bool)
        ):
            rep.error(where, "'active_high' must be true or false")
        if (
            kind in ("pwm", "i2c")
            and "freq" in per
            and not isinstance(per["freq"], int)
        ):
            rep.error(where, "'freq' must be an integer")
        if (
            kind in ("spi", "uart")
            and "baudrate" in per
            and not isinstance(per["baudrate"], int)
        ):
            rep.error(where, "'baudrate' must be an integer")
        _check_devices(per, where, rep)


def validate(facts: Path, stage: str) -> dict[str, Any]:
    rep = Report()
    if not facts.is_dir():
        rep.error(str(facts), "facts directory does not exist")
        return {"ok": False, "errors": rep.errors, "warnings": rep.warnings}
    nets_doc = _load(facts / "nets.json", rep, required=False)
    if nets_doc is not None:
        check_nets(nets_doc, rep)
    mcu: dict[str, Any] | None = None
    if stage in ("mcu", "all", "pinmap"):
        raw = _load(facts / "mcu.json", rep, required=stage in ("mcu", "all"))
        if raw is not None:
            mcu = check_mcu(raw, nets_doc, rep, seed_required=stage == "all")
    if stage == "pinmap" or (
        stage == "all" and ((facts / "pinmap.json").is_file() or nets_doc is not None)
    ):
        raw = _load(facts / "pinmap.json", rep, required=True)
        if raw is not None:
            check_pinmap(raw, mcu, rep)
    if stage in ("peripherals", "all"):
        raw = _load(facts / "peripherals.json", rep, required=True)
        if raw is not None:
            check_peripherals(raw, rep)
    return {"ok": not rep.errors, "errors": rep.errors, "warnings": rep.warnings}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate hardware/facts JSON files.")
    ap.add_argument("--facts", required=True, help="facts directory (hardware/facts)")
    ap.add_argument("--stage", choices=STAGES, default="all", help="default: all")
    ap.add_argument("-o", "--output", help="write the report here (default: stdout)")
    args = ap.parse_args(argv)
    report = validate(Path(args.facts), args.stage)
    dump_json(report, args.output)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
