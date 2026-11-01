#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Convert a KiCad, Protel/Altium or CSV netlist to nets.json.

nets.json layout:
  {"format": "kicad|protel|csv",
   "components": {"U1": {"value": "...", "footprint": "..."}},
   "nets": {"PA3": [{"ref": "U1", "pin": "34", "pinfunction": "PA3"}]}}

pinfunction is null when the format does not carry it. Net names are kept as in the source.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from common import dump_json, read_csv_dicts

FORMATS = ("auto", "kicad", "protel", "csv")


class NetlistError(Exception):
    pass


_TOKEN_RE = re.compile(r'\(|\)|"((?:[^"\\]|\\.)*)"|[^\s()"]+')


def parse_sexpr(text: str) -> list[Any]:
    """Parse an s-expression into nested lists. Atoms are strings; quotes are removed."""
    root: list[Any] = []
    stack: list[list[Any]] = [root]
    for m in _TOKEN_RE.finditer(text):
        tok = m.group(0)
        if tok == "(":
            node: list[Any] = []
            stack[-1].append(node)
            stack.append(node)
        elif tok == ")":
            if len(stack) == 1:
                raise NetlistError("unbalanced ')' in s-expression")
            stack.pop()
        elif m.group(1) is not None:
            stack[-1].append(re.sub(r"\\(.)", r"\1", m.group(1)))
        else:
            stack[-1].append(tok)
    if len(stack) != 1:
        raise NetlistError("unbalanced '(' in s-expression")
    return root


def _children(node: list[Any], head: str) -> list[list[Any]]:
    return [c for c in node if isinstance(c, list) and c and c[0] == head]


def _field(node: list[Any], head: str) -> str | None:
    for c in _children(node, head):
        if len(c) > 1 and isinstance(c[1], str):
            return c[1]
    return None


def parse_kicad(text: str) -> dict[str, Any]:
    tree = parse_sexpr(text)
    exports = [n for n in tree if isinstance(n, list) and n and n[0] == "export"]
    if not exports:
        raise NetlistError("no (export ...) form found; not a KiCad netlist")
    export = exports[0]
    components: dict[str, dict[str, str | None]] = {}
    for comps in _children(export, "components"):
        for comp in _children(comps, "comp"):
            ref = _field(comp, "ref")
            if ref is None:
                continue
            components[ref] = {
                "value": _field(comp, "value"),
                "footprint": _field(comp, "footprint"),
            }
    nets: dict[str, list[dict[str, str | None]]] = {}
    for nets_node in _children(export, "nets"):
        for net in _children(nets_node, "net"):
            name = _field(net, "name")
            if name is None:
                continue
            nodes = nets.setdefault(name, [])
            for node in _children(net, "node"):
                ref = _field(node, "ref")
                pin = _field(node, "pin")
                if ref is None or pin is None:
                    continue
                nodes.append(
                    {"ref": ref, "pin": pin, "pinfunction": _field(node, "pinfunction")}
                )
    return {"format": "kicad", "components": components, "nets": nets}


def parse_protel(text: str) -> dict[str, Any]:
    components: dict[str, dict[str, str | None]] = {}
    nets: dict[str, list[dict[str, str | None]]] = {}
    block: list[str] | None = None
    kind = ""
    for raw in text.splitlines():
        line = raw.strip()
        if block is None:
            if line in ("[", "("):
                block, kind = [], line
            continue
        if (kind == "[" and line == "]") or (kind == "(" and line == ")"):
            _protel_block(kind, block, components, nets)
            block = None
            continue
        block.append(line)
    if block is not None:
        raise NetlistError("unterminated block at end of Protel netlist")
    if not components and not nets:
        raise NetlistError("no component or net blocks found; not a Protel netlist")
    return {"format": "protel", "components": components, "nets": nets}


def _protel_block(
    kind: str,
    lines: list[str],
    components: dict[str, dict[str, str | None]],
    nets: dict[str, list[dict[str, str | None]]],
) -> None:
    while lines and not lines[0]:
        lines.pop(0)
    if not lines:
        return
    if kind == "[":
        ref = lines[0]
        footprint = lines[1] if len(lines) > 1 else ""
        value = lines[2] if len(lines) > 2 else ""
        components[ref] = {"value": value or None, "footprint": footprint or None}
        return
    name = lines[0]
    nodes = nets.setdefault(name, [])
    for line in lines[1:]:
        if not line:
            continue
        ref, sep, pin = line.rpartition("-")
        if not sep or not ref or not pin:
            raise NetlistError(f"net '{name}': cannot split '{line}' into REF-PIN")
        nodes.append({"ref": ref, "pin": pin, "pinfunction": None})


def parse_csv(path: Path) -> dict[str, Any]:
    rows = read_csv_dicts(path)
    components: dict[str, dict[str, str | None]] = {}
    nets: dict[str, list[dict[str, str | None]]] = {}
    for i, row in enumerate(rows, start=2):
        missing = [k for k in ("ref", "pin", "net") if k not in row]
        if missing:
            raise NetlistError(f"CSV header lacks column(s): {', '.join(missing)}")
        ref, pin, net = row["ref"], row["pin"], row["net"]
        if not ref or not pin:
            raise NetlistError(f"line {i}: empty ref or pin")
        comp = components.setdefault(ref, {"value": None, "footprint": None})
        if row.get("value"):
            comp["value"] = row["value"]
        if row.get("footprint"):
            comp["footprint"] = row["footprint"]
        if not net:
            continue
        nets.setdefault(net, []).append(
            {"ref": ref, "pin": pin, "pinfunction": row.get("pinfunction") or None}
        )
    if not rows:
        raise NetlistError("CSV file has no data rows")
    return {"format": "csv", "components": components, "nets": nets}


def detect_format(path: Path, text: str) -> str:
    head = text.lstrip("\ufeff \t\r\n")
    if head.startswith("(export"):
        return "kicad"
    first = head.splitlines()[0].strip().lower() if head else ""
    if path.suffix.lower() == ".csv" or re.match(r"ref\s*,", first):
        return "csv"
    if first in ("[", "("):
        return "protel"
    raise NetlistError("cannot detect netlist format; pass --format")


def parse_file(path: Path, fmt: str = "auto") -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    if fmt == "auto":
        fmt = detect_format(path, text)
    if fmt == "kicad":
        return parse_kicad(text)
    if fmt == "protel":
        return parse_protel(text)
    return parse_csv(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Convert a KiCad .net, Protel/Altium .net or CSV netlist to nets.json.",
        epilog="CSV header: ref,pin,net[,pinfunction][,value][,footprint].",
    )
    ap.add_argument("file", help="netlist file")
    ap.add_argument("--format", choices=FORMATS, default="auto", help="default: detect")
    ap.add_argument("-o", "--output", help="output nets.json (default: stdout)")
    args = ap.parse_args(argv)
    try:
        result = parse_file(Path(args.file), args.format)
    except (NetlistError, OSError) as e:
        print(f"parse_netlist: {e}", file=sys.stderr)
        return 1
    dump_json(result, args.output)
    print(
        f"parse_netlist: {result['format']}: {len(result['components'])} components, "
        f"{len(result['nets'])} nets",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
