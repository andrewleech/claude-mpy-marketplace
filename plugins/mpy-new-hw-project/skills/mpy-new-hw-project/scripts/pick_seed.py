#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Rank the boards of a MicroPython port as seed boards for a given MCU.

Boards come from a MicroPython checkout (--micropython DIR) or from GitHub (--remote:
the git tree API through `gh api` when gh exists, else urllib, plus raw files). For each
ports/<port>/boards/<BOARD>/ the script reads board.json (mcu, product, vendor) and the MCU
identifiers in mpconfigboard.mk or mpconfigboard.cmake (MCU_SERIES, MCU_VARIANT, CMSIS_MCU,
AF_FILE, PICO_PLATFORM, PICO_BOARD, IDF_TARGET; cmake include() files are followed). Most rp2
boards set only PICO_BOARD; their PICO_PLATFORM then comes from the pico-sdk board header
lib/pico-sdk/src/boards/include/boards/<PICO_BOARD>.h (local checkout only, and only when
the submodule is present). Without the header the board is ranked without a platform and
its reason says so.

Tiers:
  1 exact   the board's MCU is the requested MCU (stm32: same line, e.g. STM32F767;
            mimxrt: same MCU_VARIANT, or same MCU_SERIES when no variant is given;
            samd: same CMSIS_MCU; rp2: same PICO_PLATFORM; esp32: same IDF_TARGET)
  2 series  same MCU series or variant family
  3 port    any other board of the port

Exit 1 when no board has tier 1 or 2, that is, the port does not support the MCU. Then only
the not-supported message is printed (JSON: supported false and no candidates) unless --list
asks for every board.

More than one board in the best tier is a tie. The script cannot break it: the output then
adds the features list of board.json for each tied board and a note to compare the features and
the mpconfigboard.h defines with the design. JSON output has "tie": true.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from common import CMAKE_PORTS, PORTS, dump_json

REPO = "micropython/micropython"
TIER_EXACT, TIER_SERIES, TIER_PORT = 1, 2, 3
TIER_NAMES = {TIER_EXACT: "exact", TIER_SERIES: "series", TIER_PORT: "port"}
CONFIG_VARS = (
    "MCU_SERIES",
    "MCU_VARIANT",
    "CMSIS_MCU",
    "AF_FILE",
    "PICO_PLATFORM",
    "PICO_BOARD",
    "IDF_TARGET",
)


class SeedError(Exception):
    pass


# ---------------------------------------------------------------- sources


class LocalSource:
    def __init__(self, root: Path) -> None:
        self.root = root

    def boards(self, port: str) -> list[str]:
        d = self.root / "ports" / port / "boards"
        if not d.is_dir():
            raise SeedError(
                f"{d} does not exist; not a MicroPython checkout or port without boards"
            )
        names = []
        for p in sorted(d.iterdir()):
            if p.is_dir() and (
                (p / "board.json").is_file()
                or (p / "mpconfigboard.mk").is_file()
                or (p / "mpconfigboard.cmake").is_file()
            ):
                names.append(p.name)
        return names

    def read(self, port: str, rel: str) -> str | None:
        p = self.root / "ports" / port / rel
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def prefetch(self, port: str, rels: list[str]) -> None:
        return None

    def sdk_board_header(self, board: str) -> str | None:
        p = (
            self.root
            / "lib"
            / "pico-sdk"
            / "src"
            / "boards"
            / "include"
            / "boards"
            / f"{board}.h"
        )
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None


class RemoteSource:
    def __init__(self, ref: str = "master") -> None:
        self.ref = ref
        self._tree: set[str] | None = None
        self._cache: dict[str, str | None] = {}

    def _load_tree(self) -> set[str]:
        if self._tree is not None:
            return self._tree
        api = f"repos/{REPO}/git/trees/{self.ref}?recursive=1"
        data: dict[str, Any] | None = None
        if shutil.which("gh"):
            r = subprocess.run(
                ["gh", "api", api], capture_output=True, text=True, timeout=120
            )
            if r.returncode == 0:
                data = json.loads(r.stdout)
        if data is None:
            req = urllib.request.Request(
                f"https://api.github.com/{api}",
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "pick_seed",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.load(resp)
            except OSError as e:
                raise SeedError(
                    f"cannot fetch the GitHub tree for {REPO}@{self.ref}: {e}"
                ) from e
        if data.get("truncated"):
            raise SeedError("GitHub tree response is truncated")
        self._tree = {e["path"] for e in data["tree"] if e.get("type") == "blob"}
        return self._tree

    def boards(self, port: str) -> list[str]:
        prefix = f"ports/{port}/boards/"
        names: set[str] = set()
        for path in self._load_tree():
            if not path.startswith(prefix):
                continue
            parts = path[len(prefix) :].split("/")
            if len(parts) == 2 and parts[1] in (
                "board.json",
                "mpconfigboard.mk",
                "mpconfigboard.cmake",
            ):
                names.add(parts[0])
        if not names:
            raise SeedError(f"no boards found for port '{port}' in {REPO}@{self.ref}")
        return sorted(names)

    def _fetch(self, path: str) -> str | None:
        if path not in self._load_tree():
            return None
        url = f"https://raw.githubusercontent.com/{REPO}/{self.ref}/{path}"
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except OSError:
            return None

    def prefetch(self, port: str, rels: list[str]) -> None:
        paths = [
            f"ports/{port}/{r}" for r in rels if f"ports/{port}/{r}" not in self._cache
        ]
        with ThreadPoolExecutor(max_workers=8) as pool:
            for path, text in zip(paths, pool.map(self._fetch, paths)):
                self._cache[path] = text

    def read(self, port: str, rel: str) -> str | None:
        path = f"ports/{port}/{rel}"
        if path not in self._cache:
            self._cache[path] = self._fetch(path)
        return self._cache[path]


# ---------------------------------------------------------------- parsing

_MK_RE = re.compile(r"^([A-Z][A-Z0-9_]*)\s*[?:+]?=\s*(.*?)\s*(?:#.*)?$")
_CMAKE_SET_RE = re.compile(
    r'\bset\(\s*([A-Z][A-Z0-9_]*)\s+"?([^")\s]+)"?', re.IGNORECASE
)
_CMAKE_INCLUDE_RE = re.compile(r'\binclude\(\s*"?([^")\s]+)"?\s*\)', re.IGNORECASE)


def parse_mk(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("\t"):
            continue
        m = _MK_RE.match(line.strip())
        if m and m.group(1) in CONFIG_VARS:
            out[m.group(1)] = m.group(2)
    return out


def parse_cmake(text: str, port: str, source: Any, depth: int = 0) -> dict[str, str]:
    out: dict[str, str] = {}
    if depth < 4:
        for m in _CMAKE_INCLUDE_RE.finditer(text):
            rel = m.group(1)
            if "${" in rel:
                continue
            inc = source.read(port, rel)
            if inc:
                out.update(parse_cmake(inc, port, source, depth + 1))
    for m in _CMAKE_SET_RE.finditer(text):
        if m.group(1).upper() in CONFIG_VARS:
            out[m.group(1).upper()] = m.group(2)
    return out


@dataclass
class Board:
    name: str
    port: str
    vendor: str = ""
    product: str = ""
    board_mcu: str = ""
    mcu_series: str = ""
    mcu_variant: str = ""
    cmsis_mcu: str = ""
    af_file: str = ""
    pico_platform: str = ""
    pico_board: str = ""
    platform_note: str = ""
    idf_target: str = ""
    features: list[str] = field(default_factory=list)
    show_features: bool = False
    tier: int = 0
    reason: str = ""
    rank: int = 0
    _sort: tuple[Any, ...] = field(default=(), repr=False)

    def public(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("_sort")
        if not d.pop("show_features"):
            d.pop("features")
        d["tier"] = TIER_NAMES.get(self.tier, "") if self.tier else ""
        return {
            k: v for k, v in d.items() if v not in ("", 0, []) or k in ("name", "rank")
        }


def load_boards(source: Any, port: str) -> list[Board]:
    names = source.boards(port)
    cfg_name = "mpconfigboard.cmake" if port in CMAKE_PORTS else "mpconfigboard.mk"
    source.prefetch(
        port, [f"boards/{n}/{f}" for n in names for f in ("board.json", cfg_name)]
    )
    boards = []
    for name in names:
        b = Board(name=name, port=port)
        raw = source.read(port, f"boards/{name}/board.json")
        if raw:
            try:
                info = json.loads(raw)
            except ValueError:
                info = {}
            b.vendor = str(info.get("vendor", ""))
            b.product = str(info.get("product", ""))
            b.board_mcu = str(info.get("mcu", ""))
            features = info.get("features", [])
            if isinstance(features, list):
                b.features = [str(f) for f in features]
        cfg = source.read(port, f"boards/{name}/{cfg_name}")
        if cfg:
            v = parse_cmake(cfg, port, source) if port in CMAKE_PORTS else parse_mk(cfg)
            b.mcu_series = v.get("MCU_SERIES", "")
            b.mcu_variant = v.get("MCU_VARIANT", "")
            b.cmsis_mcu = v.get("CMSIS_MCU", "")
            b.af_file = v.get("AF_FILE", "")
            b.pico_platform = v.get("PICO_PLATFORM", "")
            b.pico_board = v.get("PICO_BOARD", "")
            b.idf_target = v.get("IDF_TARGET", "")
        if port == "rp2" and not b.pico_platform:
            _platform_from_sdk(source, b)
        boards.append(b)
    return boards


_SDK_PLATFORM_RE = re.compile(
    r"pico_board_cmake_set\(\s*PICO_PLATFORM\s*,\s*([\w-]+)\s*\)"
)


def _platform_from_sdk(source: Any, b: Board) -> None:
    """Fill b.pico_platform from the pico-sdk header of b.pico_board, else set platform_note."""
    if not b.pico_board:
        b.platform_note = "no PICO_PLATFORM or PICO_BOARD in mpconfigboard.cmake"
        return
    lookup = getattr(source, "sdk_board_header", None)
    text = lookup(b.pico_board) if lookup else None
    if text is None:
        b.platform_note = f"pico-sdk header for PICO_BOARD {b.pico_board} not available; ranked without PICO_PLATFORM"
        return
    m = _SDK_PLATFORM_RE.search(text)
    if m:
        b.pico_platform = m.group(1)
    else:
        b.platform_note = (
            f"no PICO_PLATFORM in the pico-sdk header of PICO_BOARD {b.pico_board}"
        )


# ---------------------------------------------------------------- matching


def normalize_target(port: str, text: str) -> str:
    """Upper-case MCU name without separators; vendor prefixes unified per port."""
    t = re.sub(r"[\s\-_.]", "", text).upper()
    if port == "stm32":
        if not t.startswith("STM32"):
            t = "STM32" + t
    elif port == "mimxrt":
        m = re.search(r"(?:MIMXRT|IMXRT|RT)(\d{4}\w*)", t)
        if m:
            t = "MIMXRT" + m.group(1)
    elif port == "samd":
        if t.startswith("ATSAM"):
            t = t[2:]
    return t


def _prefix_len(a: str, b: str) -> int:
    """Length of the common prefix, case-insensitive; a lower case "x" in b is a wildcard."""
    n = 0
    for ca, cb in zip(a, b):
        if ca.upper() != cb.upper() and cb != "x":
            break
        n += 1
    return n


def _core(port: str, target: str) -> str:
    prefix = {"stm32": "STM32", "mimxrt": "MIMXRT", "samd": "SAM"}.get(port, "")
    return target[len(prefix) :] if prefix and target.startswith(prefix) else target


def _is_reference(name: str) -> bool:
    return "GENERIC" in name or name.startswith(("NUCLEO_", "RPI_"))


def classify(
    port: str, target: str, series_set: set[str], b: Board
) -> tuple[int, str, str]:
    """Return (tier, reason, identifier used for prefix comparison)."""
    if port == "stm32":
        line = target[:9]
        tsub = target[5:].lower()
        tseries = max((s for s in series_set if tsub.startswith(s)), default="")
        cmsis = b.cmsis_mcu
        if cmsis and cmsis[:9].upper() == line:
            return (
                TIER_EXACT,
                f"exact MCU match: CMSIS_MCU {cmsis} is the {line} line"
                + (f", AF_FILE {b.af_file}" if b.af_file else ""),
                cmsis,
            )
        if tseries and b.mcu_series.lower() == tseries:
            return (
                TIER_SERIES,
                f"same series: MCU_SERIES {b.mcu_series} (CMSIS_MCU {cmsis})",
                cmsis,
            )
        return (
            TIER_PORT,
            f"other series: MCU_SERIES {b.mcu_series or b.board_mcu}",
            cmsis,
        )
    if port == "mimxrt":
        tseries = target[:10]
        if b.mcu_variant and len(target) > 10 and b.mcu_variant.upper() == target:
            return (
                TIER_EXACT,
                f"exact MCU match: MCU_VARIANT {b.mcu_variant}",
                b.mcu_variant,
            )
        if b.mcu_series.upper() == tseries:
            if len(target) <= 10:
                return (
                    TIER_EXACT,
                    f"exact MCU match: MCU_SERIES {b.mcu_series} (variant {b.mcu_variant})",
                    b.mcu_variant,
                )
            return (
                TIER_SERIES,
                f"same series: MCU_SERIES {b.mcu_series}, board variant {b.mcu_variant}",
                b.mcu_variant,
            )
        return TIER_PORT, f"other series: MCU_SERIES {b.mcu_series}", b.mcu_variant
    if port == "samd":
        m = re.match(r"(SAM[DL]\d\d)", target)
        tseries = m.group(1) if m else ""
        cmsis = b.cmsis_mcu.upper()
        if len(target) > 6 and cmsis and target.startswith(cmsis):
            return TIER_EXACT, f"exact MCU match: CMSIS_MCU {b.cmsis_mcu}", b.cmsis_mcu
        if tseries and b.mcu_series.upper() == tseries:
            return (
                TIER_SERIES,
                f"same series: MCU_SERIES {b.mcu_series}, board CMSIS_MCU {b.cmsis_mcu}",
                b.cmsis_mcu,
            )
        return TIER_PORT, f"other series: MCU_SERIES {b.mcu_series}", b.cmsis_mcu
    if port == "rp2":
        m = re.match(r"RP(2\d{3})", target)
        family = ("rp2350" if m.group(1) == "2354" else f"rp{m.group(1)}") if m else ""
        platform = (b.pico_platform or b.board_mcu).lower()
        if not platform:
            return TIER_PORT, f"unknown MCU: {b.platform_note}", ""
        base = platform.split("-")[0]
        if family and base == family:
            if "riscv" in platform:
                return (
                    TIER_SERIES,
                    f"same MCU, RISC-V core: PICO_PLATFORM {platform}",
                    platform,
                )
            return TIER_EXACT, f"exact MCU match: PICO_PLATFORM {platform}", platform
        return TIER_PORT, f"other MCU: PICO_PLATFORM {platform}", platform
    if port == "esp32":
        m = re.match(r"ESP32([CHPS]\d+)?", target)
        chip = ("esp32" + (m.group(1) or "").lower()) if m else ""
        idf = (b.idf_target or b.board_mcu).lower()
        if chip and idf == chip:
            return TIER_EXACT, f"exact MCU match: IDF_TARGET {idf}", idf
        return TIER_PORT, f"other chip: IDF_TARGET {idf}", idf
    raise SeedError(f"unknown port '{port}'")


def rank(port: str, mcu: str, boards: list[Board]) -> tuple[list[Board], bool]:
    target = normalize_target(port, mcu)
    series_set = {b.mcu_series.lower() for b in boards if b.mcu_series}
    # Boards of these ports are often named after the part; a name containing the full
    # part (or its first four characters, the line) ranks first within a tier.
    named_by_part = port in ("stm32", "mimxrt", "samd")
    core = _core(port, target) if named_by_part else ""
    for b in boards:
        tier, reason, ident = classify(port, target, series_set, b)
        b.tier, b.reason = tier, reason
        hay = f"{b.name} {b.product}".upper().replace(" ", "_")
        if core and core in hay:
            hit = 2
        elif core and core[:4] in hay:
            hit = 1
        else:
            hit = 0
        b._sort = (
            tier,
            -hit,
            -_prefix_len(target, ident),
            0 if _is_reference(b.name) else 1,
            b.name,
        )
    ordered = sorted(boards, key=lambda b: b._sort)
    for i, b in enumerate(ordered, start=1):
        b.rank = i
    supported = any(b.tier in (TIER_EXACT, TIER_SERIES) for b in ordered)
    return ordered, supported


def mark_tie(boards: list[Board]) -> list[Board]:
    """Boards sharing the best tier when it is tier 1 or 2 and more than one board has it.

    Their features are shown in the output. Returns [] when there is no tie.
    """
    tiers = [b.tier for b in boards if b.tier in (TIER_EXACT, TIER_SERIES)]
    if not tiers:
        return []
    best = min(tiers)
    tied = [b for b in boards if b.tier == best]
    if len(tied) < 2:
        return []
    for b in tied:
        b.show_features = True
    return tied


TIE_NOTE = (
    "{count} boards share tier {tier}. Break the tie by comparing their features and the "
    "mpconfigboard.h defines with the design."
)


# ---------------------------------------------------------------- cli


def format_text(
    port: str,
    mcu: str | None,
    boards: list[Board],
    supported: bool | None,
    tied: list[Board] | None = None,
) -> str:
    lines = []
    if mcu:
        state = "supported" if supported else "NOT supported"
        lines.append(f"port {port}, MCU {mcu}: {state}")
    else:
        lines.append(f"port {port}: {len(boards)} boards")
    for b in boards:
        ident = " ".join(
            f"{k}={v}"
            for k, v in (
                ("series", b.mcu_series),
                ("variant", b.mcu_variant),
                ("cmsis", b.cmsis_mcu),
                ("platform", b.pico_platform),
                ("idf", b.idf_target),
                ("mcu", b.board_mcu),
            )
            if v
        )
        head = f"{b.rank:>3}. {b.name}" if b.rank else f"  - {b.name}"
        lines.append(f"{head}  [{b.vendor} {b.product}]".rstrip() + f"  {ident}")
        if b.reason:
            lines.append(f"       {TIER_NAMES[b.tier]}: {b.reason}")
        if b.show_features:
            lines.append(f"       features: {', '.join(b.features) or 'none listed'}")
    if tied:
        lines.append(TIE_NOTE.format(count=len(tied), tier=TIER_NAMES[tied[0].tier]))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Rank the boards of a MicroPython port as seed boards for an MCU.",
        epilog="Exit 1 when the port has no board for the MCU or its series.",
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--micropython", metavar="DIR", help="MicroPython checkout")
    src.add_argument("--remote", action="store_true", help="read boards from GitHub")
    ap.add_argument(
        "--ref", default="master", help="git ref for --remote (default: master)"
    )
    ap.add_argument("--port", required=True, choices=PORTS)
    ap.add_argument(
        "--mcu", help="MCU part, e.g. STM32F767ZI, RP2350, ESP32-S3, SAMD51J19A"
    )
    ap.add_argument("--list", action="store_true", help="list every board of the port")
    ap.add_argument(
        "--limit", type=int, default=10, help="candidates shown (0 = all; default 10)"
    )
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("-o", "--output", help="write JSON output here")
    args = ap.parse_args(argv)
    if not args.mcu and not args.list:
        ap.error("give --mcu, --list, or both")

    try:
        source = (
            RemoteSource(args.ref)
            if args.remote
            else LocalSource(Path(args.micropython))
        )
        boards = load_boards(source, args.port)
    except SeedError as e:
        print(f"pick_seed: {e}", file=sys.stderr)
        return 1

    supported: bool | None = None
    if args.mcu:
        boards, supported = rank(args.port, args.mcu, boards)
    tied = mark_tie(boards) if args.mcu else []
    if args.mcu and not supported and not args.list:
        shown = []
    else:
        shown = boards if args.list or args.limit == 0 else boards[: args.limit]

    if args.json or args.output:
        doc: dict[str, Any] = {
            "port": args.port,
            "mcu": args.mcu,
            "supported": supported,
            "candidates": [b.public() for b in shown],
        }
        if tied:
            doc["tie"] = True
            doc["tie_note"] = TIE_NOTE.format(
                count=len(tied), tier=TIER_NAMES[tied[0].tier]
            )
        dump_json(doc, args.output)
    elif not (args.mcu and not supported and not args.list):
        sys.stdout.write(format_text(args.port, args.mcu, shown, supported, tied))
    if args.mcu and not supported:
        print(
            f"pick_seed: port {args.port} has no board for {args.mcu} or its series",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
