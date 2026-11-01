#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Map MCU package pins to port pad names and check the map against the netlist.

The package pin to port name table comes from a CSV (header package_pin,port_name) or from
the netlist pinfunction field. A net that is connected to an MCU pin and is named after a
pad (PA3, /PA3, PA3_ADC) is an anchor: the table must map that pin to that pad. Any
disagreement fails the gate. Too few anchors also fails, unless --confirmed says the user
checked the table.

Writes pinmap.json. On success it prints a one-line summary (status, pin count, anchor count)
to stderr. Exit 0 when status is ok, 1 when it is fail.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from common import (
    PORTS,
    dump_json,
    find_port_name,
    gpio_limit,
    gpio_range_error,
    load_json,
    load_port_names,
    natural_key,
    port_name_pattern,
    port_name_regex,
    read_csv_dicts,
    strip_sheet,
)


def table_from_csv(path: Path, errors: list[str]) -> list[tuple[str, str]]:
    rows = read_csv_dicts(path)
    out: list[tuple[str, str]] = []
    for i, row in enumerate(rows, start=2):
        if "package_pin" not in row or "port_name" not in row:
            errors.append(f"{path}: header must be package_pin,port_name")
            return []
        pin, name = row["package_pin"], row["port_name"]
        if not pin or not name:
            errors.append(f"{path}:{i}: empty package_pin or port_name")
            continue
        out.append((pin, name))
    return out


def table_from_pinfunction(
    nets: dict[str, Any], mcu_ref: str, port: str, names: set[str]
) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    for nodes in nets.values():
        for node in nodes:
            if node["ref"] != mcu_ref:
                continue
            name = find_port_name(node.get("pinfunction"), port, names)
            if name:
                seen.setdefault(node["pin"], name)
    return list(seen.items())


def net_port_name(net: str, port: str, known: set[str]) -> str | None:
    """Pad name that a net name stands for, or None when the net is not self-naming."""
    name = strip_sheet(net).upper()
    if name in known:
        return name
    if port == "mimxrt":
        best = None
        for k in known:
            if name.startswith(k) and name[len(k) : len(k) + 1] in ("_", "-"):
                if best is None or len(k) > len(best):
                    best = k
        return best
    m = re.fullmatch(rf"({port_name_regex(port)})(?:[_-].*)?", name)
    return m.group(1) if m else None


def resolve(
    nets_doc: dict[str, Any],
    mcu_ref: str,
    port: str,
    table: list[tuple[str, str]],
    af_names: set[str] | None = None,
    min_anchors: int = 3,
    confirmed: bool = False,
    table_errors: list[str] | None = None,
    num_gpios: int | None = None,
) -> dict[str, Any]:
    errors: list[str] = list(table_errors or [])
    pattern = port_name_pattern(port, af_names)

    by_pin: dict[str, str] = {}
    by_name: dict[str, str] = {}
    for pin, name in table:
        if pin in by_pin:
            errors.append(
                f"package pin {pin} appears twice in the table ({by_pin[pin]} and {name})"
            )
            continue
        if not pattern.match(name):
            errors.append(
                f"package pin {pin}: '{name}' is not a valid {port} port name"
            )
        elif (range_error := gpio_range_error(port, name, num_gpios)) is not None:
            errors.append(f"package pin {pin}: {range_error}")
        elif af_names and port != "mimxrt" and name not in af_names:
            errors.append(f"package pin {pin}: '{name}' is not in the AF file")
        if name in by_name:
            errors.append(
                f"port name {name} is mapped to two package pins ({by_name[name]} and {pin})"
            )
        else:
            by_name[name] = pin
        by_pin[pin] = name

    pin_nets: dict[str, str] = {}
    if mcu_ref not in nets_doc.get("components", {}) and not any(
        n["ref"] == mcu_ref for nodes in nets_doc["nets"].values() for n in nodes
    ):
        errors.append(f"MCU reference '{mcu_ref}' is not in the netlist")
    for net, nodes in nets_doc["nets"].items():
        for node in nodes:
            if node["ref"] != mcu_ref:
                continue
            pin = node["pin"]
            if pin in pin_nets and pin_nets[pin] != net:
                errors.append(
                    f"package pin {pin} is on two nets ('{pin_nets[pin]}' and '{net}')"
                )
            pin_nets.setdefault(pin, net)

    known = set(by_name) | (af_names or set())
    anchors: list[dict[str, str]] = []
    pins: list[dict[str, Any]] = []
    for pin in sorted(pin_nets, key=natural_key):
        net = pin_nets[pin]
        claimed = net_port_name(net, port, known)
        mapped = by_pin.get(pin)
        is_anchor = False
        if claimed is not None:
            if mapped is None:
                errors.append(
                    f"package pin {pin}: net '{net}' names port pad {claimed} "
                    f"but the pin table has no entry for pin {pin}"
                )
            elif mapped != claimed:
                errors.append(
                    f"package pin {pin}: net '{net}' names port pad {claimed} "
                    f"but the pin table maps pin {pin} to {mapped}"
                )
            else:
                is_anchor = True
                anchors.append({"package_pin": pin, "port_name": mapped, "net": net})
        if mapped is not None:
            pins.append(
                {
                    "package_pin": pin,
                    "port_name": mapped,
                    "net": net,
                    "anchor": is_anchor,
                }
            )

    if len(anchors) < min_anchors and not confirmed:
        message = f"only {len(anchors)} anchor(s), need {min_anchors}"
        if not errors:
            message += "; show the table to the user and rerun with --confirmed once they confirm it"
        errors.append(message)

    result: dict[str, Any] = {
        "port": port,
        "mcu_ref": mcu_ref,
        "status": "fail" if errors else "ok",
        "pins": pins,
        "anchors": anchors,
        "errors": errors,
    }
    if confirmed:
        result["confirmed"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Resolve MCU package pins to port pad names and verify against net names.",
    )
    ap.add_argument("--nets", required=True, help="nets.json from parse_netlist.py")
    ap.add_argument(
        "--mcu-ref", required=True, help="MCU reference designator, e.g. U1"
    )
    ap.add_argument("--port", required=True, choices=PORTS)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pin-table", help="CSV with header package_pin,port_name")
    src.add_argument(
        "--from-pinfunction",
        action="store_true",
        help="take the table from the netlist pinfunction field",
    )
    ap.add_argument(
        "--af-file", help="port AF table CSV; port names must be listed in it"
    )
    ap.add_argument(
        "--micropython",
        metavar="DIR",
        help="MicroPython checkout; esp32 port names are range checked against make-pins.py",
    )
    ap.add_argument("--min-anchors", type=int, default=3, help="default: 3")
    ap.add_argument(
        "--confirmed",
        action="store_true",
        help="the user confirmed the table; fewer than --min-anchors anchors is then accepted",
    )
    ap.add_argument("-o", "--output", help="output pinmap.json (default: stdout)")
    args = ap.parse_args(argv)

    try:
        nets_doc = load_json(args.nets)
        af_names = load_port_names(args.port, args.af_file) if args.af_file else None
        table_errors: list[str] = []
        if args.pin_table:
            table = table_from_csv(Path(args.pin_table), table_errors)
        else:
            table = table_from_pinfunction(
                nets_doc["nets"], args.mcu_ref, args.port, af_names or set()
            )
            if not table:
                table_errors.append(
                    f"no pinfunction on {args.mcu_ref} matches a {args.port} port name"
                )
    except (OSError, KeyError, ValueError) as e:
        print(f"resolve_pinmap: {e}", file=sys.stderr)
        return 1

    result = resolve(
        nets_doc,
        args.mcu_ref,
        args.port,
        table,
        af_names=af_names,
        min_anchors=args.min_anchors,
        confirmed=args.confirmed,
        table_errors=table_errors,
        num_gpios=gpio_limit(args.port, args.micropython),
    )
    dump_json(result, args.output)
    for err in result["errors"]:
        print(f"resolve_pinmap: {err}", file=sys.stderr)
    if result["status"] == "ok":
        print(
            f"resolve_pinmap: ok, {len(result['pins'])} pins, {len(result['anchors'])} anchors",
            file=sys.stderr,
        )
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
