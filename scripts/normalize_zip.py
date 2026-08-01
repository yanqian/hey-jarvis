#!/usr/bin/env python3
"""Rewrite a ZIP with stable entry ordering and metadata."""

from __future__ import annotations

import argparse
import os
import tempfile
import zipfile
from pathlib import Path


FIXED_ZIP_TIME = (2025, 1, 1, 0, 0, 0)


def normalize(path: Path) -> None:
    with zipfile.ZipFile(path, "r") as source:
        entries = [(item, source.read(item)) for item in source.infolist()]
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(descriptor)
    temporary_path = Path(temporary)
    try:
        with zipfile.ZipFile(temporary_path, "w") as target:
            for original, payload in sorted(entries, key=lambda value: value[0].filename):
                item = zipfile.ZipInfo(original.filename, FIXED_ZIP_TIME)
                item.compress_type = original.compress_type
                item.comment = original.comment
                item.extra = b""
                item.create_system = original.create_system
                item.external_attr = original.external_attr
                item.internal_attr = original.internal_attr
                target.writestr(item, payload)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    normalize(args.path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
