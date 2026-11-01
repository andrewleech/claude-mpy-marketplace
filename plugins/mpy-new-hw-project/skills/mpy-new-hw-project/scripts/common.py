# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Shared constants and helpers for the mpy-new-hw-project scripts."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

PORTS = ("esp32", "mimxrt", "rp2", "samd", "stm32")
CMAKE_PORTS = {"rp2", "esp32"}
# Ports where every pad is addressable by its pad name without a pins.csv entry. A pins.csv
# row whose board name equals its pad name makes make-pins emit a duplicate pin_<PAD> define
# there. On stm32 only pads listed in pins.csv get a pin object, so such rows are needed.
SELF_NAMED_SKIPPED_PORTS = frozenset({"rp2", "samd", "mimxrt", "esp32"})
SOURCES = ("script", "user-confirmed", "inferred")

# Unanchored regex text for a port's own pad names. mimxrt also accepts names read
# from the AF table (see port_name_pattern).
PORT_NAME_REGEX = {
    "stm32": r"P[A-K]\d{1,2}",
    "samd": r"P[A-D]\d{2}",
    "rp2": r"GPIO\d+",
    "esp32": r"GPIO\d+",
    "mimxrt": r"GPIO_[A-Z0-9_]*\d\d",
}


def load_json(path: str | Path) -> Any:
    """Read a JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(obj: Any, path: str | Path | None = None) -> None:
    """Write obj as indented JSON to path, or to stdout when path is None or "-"."""
    text = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    if path is None or str(path) == "-":
        sys.stdout.write(text)
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


_UNNAMED_RES = (
    re.compile(r"^Net-\(.*\)$"),  # KiCad
    re.compile(r"^unconnected-\(.*\)$"),  # KiCad
    re.compile(r"^Net[A-Z]{1,3}\d+_[A-Z]{0,2}\d+$"),  # Protel/Altium: NetU1_5, NetU1_A1
    re.compile(r"^N\$\d+$"),  # Eagle style
)


def strip_sheet(net: str) -> str:
    """Remove the KiCad hierarchical sheet prefix ("/sheet/NAME" gives "NAME")."""
    m = re.search(r"(Net-\(|unconnected-\()", net)
    if m:
        return net[m.start() :]
    if net.startswith("/"):
        return net.rsplit("/", 1)[-1]
    return net


def is_unnamed_net(name: str | None) -> bool:
    """True for empty names and tool-generated names such as Net-(U1-PA3) or NetU1_5."""
    if not name:
        return True
    base = strip_sheet(name)
    return any(r.match(base) for r in _UNNAMED_RES)


def board_pin_name(net: str) -> str:
    """Board pin name for a net: no sheet prefix, upper case, [A-Z0-9_] only, no leading digit.

    The result for an unnamed net is meaningless; check is_unnamed_net first.
    """
    name = re.sub(r"[^A-Z0-9_]", "_", strip_sheet(net).upper())
    if name and name[0].isdigit():
        name = "P_" + name
    return name


_NUM_GPIOS = re.compile(r"^NUM_GPIOS\s*=\s*(\d+)\s*$", re.MULTILINE)


def gpio_limit(port: str, micropython: str | Path | None) -> int | None:
    """Number of GPIO pads the port's pin generator accepts, or None when not known.

    Only esp32 has such a limit: ports/esp32/boards/make-pins.py rejects GPIOn with
    n >= NUM_GPIOS. The value is the same for every IDF_TARGET.
    """
    if port != "esp32" or micropython is None:
        return None
    src = Path(micropython) / "ports/esp32/boards/make-pins.py"
    try:
        m = _NUM_GPIOS.search(src.read_text(encoding="utf-8"))
    except OSError:
        return None
    return int(m.group(1)) if m else None


def gpio_range_error(port: str, name: str, limit: int | None) -> str | None:
    """Error text when name is GPIOn with n at or above limit, else None."""
    m = re.fullmatch(r"GPIO(\d+)", name)
    if limit is None or not m or int(m.group(1)) < limit:
        return None
    return (
        f"'{name}' is not a valid {port} port name: make-pins.py accepts GPIO0 to "
        f"GPIO{limit - 1} (NUM_GPIOS = {limit})"
    )


def port_name_regex(port: str) -> str:
    """Unanchored regex text for the port's pad names."""
    try:
        return PORT_NAME_REGEX[port]
    except KeyError:
        raise ValueError(
            f"unknown port '{port}', expected one of {', '.join(PORTS)}"
        ) from None


def port_name_pattern(port: str, names: Iterable[str] | None = None) -> re.Pattern[str]:
    """Compiled, anchored regex for valid pad names of a port.

    names are extra valid names (mimxrt: names from the AF table that do not follow the
    GPIO_ naming such as WAKEUP). They are added for every port.
    """
    alts = [port_name_regex(port)]
    if names:
        alts.extend(
            re.escape(n) for n in sorted(set(names), key=lambda s: (-len(s), s))
        )
    return re.compile(r"^(?:" + "|".join(alts) + r")$")


def find_port_name(
    text: str | None, port: str, names: Iterable[str] | None = None
) -> str | None:
    """First token of text that is a valid pad name for the port, or None."""
    if not text:
        return None
    pat = port_name_pattern(port, names)
    for tok in re.split(r"[\s/,;()\[\]-]+", text.strip()):
        if tok and pat.match(tok):
            return tok
    return None


def load_port_names(port: str, af_file: str | Path) -> set[str]:
    """Pad names listed in a port AF table (stm32, mimxrt or samd layout)."""
    names: set[str] = set()
    with open(af_file, newline="", encoding="utf-8") as f:
        lines = [ln for ln in f if not ln.lstrip().startswith("#")]
    rows = list(csv.reader(lines))
    if not rows:
        return names
    for row in rows[1:]:
        if port == "stm32":
            cell = row[1].strip() if len(row) > 1 else ""
        else:
            cell = row[0].strip() if row else ""
        if cell:
            names.add(cell)
    return names


def natural_key(text: str) -> list[Any]:
    """Sort key that orders embedded integers numerically ("A2" < "A10")."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", text)]


def read_csv_dicts(path: str | Path) -> list[dict[str, str]]:
    """Read a CSV file with a header row; keys and values are stripped."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            clean = {
                (k or "").strip(): (v or "").strip()
                for k, v in row.items()
                if k is not None
            }
            if any(clean.values()):
                rows.append(clean)
        return rows
