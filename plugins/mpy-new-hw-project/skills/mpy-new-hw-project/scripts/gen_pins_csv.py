#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Write a board pins.csv (BOARD_PIN_NAME,port_name) from pinmap.json.

Board pin names come from net names: sheet prefix removed, upper case, characters outside
[A-Z0-9_] replaced with "_", "P_" prefix when the first character is a digit. Unnamed nets
(KiCad Net-(...), unconnected-(...), Protel NetU1_5) get no line. Pins of pinmap.json are
port pins only, so power and ground are not listed.

--include-pad PAD[=NAME] adds a pad of the pinmap that has an unnamed net, under the board
pin name NAME (default: the port name). On stm32 only pads listed in pins.csv get pin_<Pxn>
objects, so a pad that mpconfigboard.h names needs a line even when its net is unnamed.

Rows whose board pin name equals the pad name are left out on rp2, samd, mimxrt and esp32,
where every pad is addressable by its pad name and such a row makes make-pins emit a duplicate
pin_<PAD> define. --keep-self-named keeps them. An --include-pad on a pad whose net is already named is
ignored with a warning (stderr, and the "warnings" key of the summary).

--micropython DIR makes the esp32 pad names get range checked against NUM_GPIOS of
ports/esp32/boards/make-pins.py.

Exit 1 on a name collision or a port name that is not valid for the port.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from common import (
    PORTS,
    SELF_NAMED_SKIPPED_PORTS,
    board_pin_name,
    gpio_limit,
    gpio_range_error,
    dump_json,
    is_unnamed_net,
    load_json,
    load_port_names,
    port_name_pattern,
)


def build_rows(
    pinmap: dict[str, Any],
    port: str,
    exclude: set[str] | None = None,
    af_names: set[str] | None = None,
    keep_self_named: bool | None = None,
    include_pads: dict[str, str] | None = None,
    num_gpios: int | None = None,
) -> tuple[list[tuple[str, str]], list[str], list[str], list[str]]:
    """Return (rows, skipped, errors, warnings). rows are (board_pin_name, port_name) pairs.

    keep_self_named None means the port default: skip self-named rows on
    SELF_NAMED_SKIPPED_PORTS, keep them elsewhere.
    """
    if keep_self_named is None:
        keep_self_named = port not in SELF_NAMED_SKIPPED_PORTS
    exclude = {e.upper() for e in (exclude or set())}
    pattern = port_name_pattern(port, af_names)
    rows: list[tuple[str, str]] = []
    skipped: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []
    owner: dict[str, str] = {}
    include_pads = include_pads or {}
    for pad in include_pads:
        if not any(p["port_name"] == pad for p in pinmap.get("pins", [])):
            errors.append(f"--include-pad {pad}: pad is not in the pinmap")
    for pin in pinmap.get("pins", []):
        net = pin["net"]
        port_name = pin["port_name"]
        if not pattern.match(port_name):
            errors.append(
                f"package pin {pin['package_pin']}: '{port_name}' is not a valid {port} port name"
            )
            continue
        if (range_error := gpio_range_error(port, port_name, num_gpios)) is not None:
            errors.append(f"package pin {pin['package_pin']}: {range_error}")
            continue
        if port_name in include_pads and is_unnamed_net(net):
            name = include_pads[port_name]
            if not keep_self_named and name == port_name:
                skipped.append(f"{pin['package_pin']}:{net}")
                continue
            if name in owner:
                errors.append(
                    f"board pin name {name} is used by nets '{owner[name]}' and '{net}'"
                )
                continue
            owner[name] = net
            rows.append((name, port_name))
            continue
        if port_name in include_pads:
            warnings.append(
                f"--include-pad {port_name}: pad already has the named net '{net}', option ignored"
            )
        if is_unnamed_net(net):
            skipped.append(f"{pin['package_pin']}:{net}")
            continue
        name = board_pin_name(net)
        if name in exclude or net.upper() in exclude:
            skipped.append(f"{pin['package_pin']}:{net}")
            continue
        if not keep_self_named and name == port_name:
            skipped.append(f"{pin['package_pin']}:{net}")
            continue
        if name in owner:
            errors.append(
                f"board pin name {name} is used by nets '{owner[name]}' and '{net}'"
            )
            continue
        owner[name] = net
        rows.append((name, port_name))
    return rows, skipped, errors, warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Generate a board pins.csv from pinmap.json."
    )
    ap.add_argument(
        "--pinmap", required=True, help="pinmap.json from resolve_pinmap.py"
    )
    ap.add_argument("--port", required=True, choices=PORTS)
    ap.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        metavar="NAME",
        help="net or board pin names to leave out",
    )
    ap.add_argument(
        "--micropython",
        metavar="DIR",
        help="MicroPython checkout; esp32 port names are range checked against make-pins.py",
    )
    ap.add_argument(
        "--af-file", help="port AF table CSV; adds its pad names as valid names"
    )
    ap.add_argument(
        "--keep-self-named",
        action="store_true",
        help="keep lines whose board pin name equals the port name "
        "(left out by default on rp2, samd, mimxrt and esp32)",
    )
    ap.add_argument(
        "--include-pad",
        action="append",
        default=[],
        metavar="PAD[=NAME]",
        help="add a pad with an unnamed net under board pin name NAME (default: PAD); repeatable",
    )
    ap.add_argument("-o", "--output", help="output pins.csv (default: stdout)")
    args = ap.parse_args(argv)

    try:
        pinmap = load_json(args.pinmap)
        af_names = load_port_names(args.port, args.af_file) if args.af_file else None
    except (OSError, ValueError) as e:
        print(f"gen_pins_csv: {e}", file=sys.stderr)
        return 1
    if pinmap.get("status") != "ok":
        print("gen_pins_csv: pinmap.json status is not ok", file=sys.stderr)
        return 1
    if pinmap.get("port") not in (None, args.port):
        print(
            f"gen_pins_csv: pinmap.json port is {pinmap['port']}, not {args.port}",
            file=sys.stderr,
        )
        return 1

    include_pads: dict[str, str] = {}
    for spec in args.include_pad:
        pad, _, name = spec.partition("=")
        pad = pad.strip()
        include_pads[pad] = name.strip() or pad
    rows, skipped, errors, warnings = build_rows(
        pinmap,
        args.port,
        set(args.exclude),
        af_names,
        True if args.keep_self_named else None,
        include_pads,
        gpio_limit(args.port, args.micropython),
    )
    for w in warnings:
        print(f"gen_pins_csv: warning: {w}", file=sys.stderr)
    if errors:
        for e in errors:
            print(f"gen_pins_csv: {e}", file=sys.stderr)
        return 1

    text = "".join(f"{name},{port_name}\n" for name, port_name in rows)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text, encoding="utf-8")
        dump_json(
            {
                "written": args.output,
                "count": len(rows),
                "skipped": skipped,
                "warnings": warnings,
            }
        )
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
