#!/usr/bin/env python3
"""Dependency-free static contract for the isolated F086 spike."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".js", ".json", ".toml", ".rs", ".sh", ".html", ".css", ".md"}
FORBIDDEN_IMPORT = re.compile(r"(^|\n)\s*(?:from|import)\s+src(?:\.|\s|$)")


def main() -> int:
    failures: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        if any(part in {"node_modules", "target", ".venv", ".build"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT)
        if relative == Path("scripts/check_isolation.py"):
            continue
        if FORBIDDEN_IMPORT.search(text):
            failures.append(f"{relative}: imports product src")
        if "../../src" in text or "../src/realtime" in text:
            failures.append(f"{relative}: references product source path")

    config = json.loads((ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    external = config.get("bundle", {}).get("externalBin", [])
    if external != ["binaries/tauri-realtime-probe"]:
        failures.append("tauri.conf.json: unexpected externalBin boundary")
    if config.get("identifier") != "com.heyjarvis.taurirealtime.spike":
        failures.append("tauri.conf.json: spike bundle identifier changed")

    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    if package.get("private") is not True:
        failures.append("package.json: spike package must remain private")

    if failures:
        print("\n".join(failures))
        return 1
    print("F086 isolation contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
