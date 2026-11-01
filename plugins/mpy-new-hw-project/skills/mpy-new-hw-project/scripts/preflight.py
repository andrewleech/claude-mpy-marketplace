#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Check the tools a new hardware project needs.

Checks uv, make, git, a container runtime (docker or podman), network access to github.com
and the git identity. With --micropython, also checks that DIR is a MicroPython checkout.

Prints {"ok", "tools", "missing", "notes"} as JSON. Exit 1 when something is missing.
"""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import dump_json

REQUIRED_TOOLS = ("uv", "make", "git")
CONTAINER_TOOLS = ("docker", "podman")


def _git_config(key: str) -> str:
    try:
        r = subprocess.run(
            ["git", "config", "--get", key], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip()


def network_reachable(
    host: str = "github.com", port: int = 443, timeout: float = 5.0
) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def container_usable(tool: str) -> bool:
    try:
        r = subprocess.run([tool, "info"], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def check(micropython: Path | None = None) -> dict[str, Any]:
    tools: dict[str, str | None] = {
        t: shutil.which(t) for t in REQUIRED_TOOLS + CONTAINER_TOOLS
    }
    missing: list[str] = [t for t in REQUIRED_TOOLS if not tools[t]]
    notes: list[str] = []

    runtime = next((t for t in CONTAINER_TOOLS if tools[t]), None)
    tools["container"] = runtime
    if runtime is None:
        missing.append("docker or podman")
        notes.append("no container runtime: the build steps are skipped")
    elif not container_usable(runtime):
        notes.append(
            f"{runtime} is installed but `{runtime} info` failed; check the daemon and group access"
        )

    if not network_reachable():
        missing.append("network access to github.com")
    if tools["git"]:
        if not _git_config("user.name") or not _git_config("user.email"):
            missing.append("git identity (user.name and user.email)")
    tools["gh"] = shutil.which("gh")
    if not tools["gh"]:
        notes.append(
            "gh not found: pick_seed.py --remote falls back to the unauthenticated API"
        )

    if micropython is not None:
        if not (micropython / "ports").is_dir() or not (micropython / "py").is_dir():
            missing.append(f"MicroPython checkout at {micropython}")
        elif not (micropython / "ports" / "stm32" / "boards").is_dir():
            notes.append(
                f"{micropython} has no ports/stm32/boards; the checkout may be incomplete"
            )

    return {"ok": not missing, "tools": tools, "missing": missing, "notes": notes}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Check tools needed for a new hardware project."
    )
    ap.add_argument(
        "--micropython", metavar="DIR", help="MicroPython checkout to check"
    )
    ap.add_argument("-o", "--output", help="write the report here (default: stdout)")
    args = ap.parse_args(argv)
    report = check(Path(args.micropython) if args.micropython else None)
    dump_json(report, args.output)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
