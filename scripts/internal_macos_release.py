#!/usr/bin/env python3
"""Inspect and describe an unsigned Hey Jarvis internal macOS artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import stat
import subprocess
from pathlib import Path
from typing import Any


SCHEMA = "hey-jarvis-internal-release-v1"
PRODUCT = "Hey Jarvis"
BUNDLE_ID = "com.heyjarvis.desktop"
MINIMUM_MACOS = "14.0"
ARCHITECTURE = "arm64"
MAX_DMG_BYTES = 150 * 1024 * 1024
REQUIRED_WARNING = "INTERNAL-UNSIGNED.txt"
SECRET_PATTERNS = (
    # Require a digit or uppercase character so adjacent compiled string
    # literals such as `sk-` plus lower-case diagnostics do not look like a
    # key. Current project/legacy keys satisfy this conservative detector.
    re.compile(rb"sk-(?=[A-Za-z0-9_-]{20,})(?=[A-Za-z0-9_-]*[A-Z0-9])[A-Za-z0-9_-]{20,}"),
    re.compile(rb"OPENAI_API_KEY\s*="),
    re.compile(rb"FINNHUB_API_KEY\s*="),
)
DEVELOPER_PATH_PATTERNS = (
    re.compile(rb"/Users/[^/\x00]+/(?:Project|Projects|workspace|src)/"),
    re.compile(rb"/home/[^/\x00]+/(?:Project|Projects|workspace|src)/"),
)


class ReleaseError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_version(root: Path) -> str:
    tauri = json.loads((root / "app/src-tauri/tauri.conf.json").read_text())
    package = json.loads((root / "app/package.json").read_text())
    cargo = (root / "app/src-tauri/Cargo.toml").read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', cargo, re.MULTILINE)
    versions = {tauri["version"], package["version"], match.group(1) if match else ""}
    if len(versions) != 1 or "" in versions:
        raise ReleaseError(f"version sources disagree: {sorted(versions)}")
    return tauri["version"]


def _run_file(path: Path) -> str:
    result = subprocess.run(
        ["/usr/bin/file", "-b", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _signature_status(app: Path) -> str:
    result = subprocess.run(
        ["/usr/bin/codesign", "-dv", "--verbose=4", str(app)],
        capture_output=True,
        text=True,
    )
    details = result.stdout + result.stderr
    if "Developer ID Application:" in details or "TeamIdentifier=" in details and "not set" not in details:
        raise ReleaseError("Developer ID/team signature is outside INTERNAL-UNSIGNED scope")
    if "Signature=adhoc" in details:
        return "adhoc-no-distribution-trust"
    if result.returncode != 0 and "not signed at all" in details:
        return "none"
    raise ReleaseError("unable to prove the bundle lacks a distribution signature")


def _scan_for_private_material(path: Path, root: Path) -> None:
    root_bytes = str(root.resolve()).encode()
    for candidate in path.rglob("*"):
        if not candidate.is_file() or candidate.is_symlink():
            continue
        with candidate.open("rb") as handle:
            data = handle.read()
        if root_bytes in data or any(pattern.search(data) for pattern in DEVELOPER_PATH_PATTERNS):
            raise ReleaseError(f"developer filesystem path found in {candidate.relative_to(path)}")
        if any(pattern.search(data) for pattern in SECRET_PATTERNS):
            raise ReleaseError(f"credential-shaped content found in {candidate.relative_to(path)}")


def inspect_app(app: Path, root: Path) -> dict[str, Any]:
    plist_path = app / "Contents/Info.plist"
    if not plist_path.is_file():
        raise ReleaseError("app bundle is missing Contents/Info.plist")
    with plist_path.open("rb") as handle:
        info = plistlib.load(handle)
    version = canonical_version(root)
    expected = {
        "CFBundleDisplayName": PRODUCT,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "LSMinimumSystemVersion": MINIMUM_MACOS,
    }
    for key, value in expected.items():
        if info.get(key) != value:
            raise ReleaseError(f"{key} must be {value!r}, got {info.get(key)!r}")
    microphone = info.get("NSMicrophoneUsageDescription", "")
    if "microphone" not in microphone.lower() or "wake phrase" not in microphone.lower():
        raise ReleaseError("microphone usage description is missing or incomplete")
    icon_name = info.get("CFBundleIconFile", "")
    if not icon_name or not (app / "Contents/Resources" / icon_name).is_file():
        raise ReleaseError("configured app icon is missing from the bundle")

    executable = app / "Contents/MacOS" / info.get("CFBundleExecutable", "")
    required = (
        executable,
        app / "Contents/Resources/sidecar/hey-jarvis-sidecar",
        app / "Contents/Resources/packaging-manifests/build-manifest.json",
    )
    for candidate in required:
        if not candidate.exists():
            raise ReleaseError(f"required bundle resource is missing: {candidate.relative_to(app)}")

    nested: list[dict[str, Any]] = []
    for candidate in sorted(app.rglob("*")):
        if not candidate.is_file() or candidate.is_symlink():
            continue
        mode = candidate.stat().st_mode
        if not (mode & stat.S_IXUSR) and candidate.suffix not in {".dylib", ".so"}:
            continue
        kind = _run_file(candidate)
        if "Mach-O" in kind:
            if "arm64" not in kind or "x86_64" in kind:
                raise ReleaseError(f"non-arm64 nested code: {candidate.relative_to(app)} ({kind})")
            code_type = "mach-o-arm64"
            signature = _signature_status(candidate)
        else:
            code_type = "data-or-script"
            signature = "not-applicable"
        nested.append(
            {
                "path": candidate.relative_to(app).as_posix(),
                "bytes": candidate.stat().st_size,
                "type": code_type,
                "code_signature": signature,
            }
        )
    if not any(item["path"] == executable.relative_to(app).as_posix() for item in nested):
        raise ReleaseError("main executable is absent from nested-code inventory")
    _scan_for_private_material(app, root)
    return {
        "product": PRODUCT,
        "bundle_identifier": BUNDLE_ID,
        "version": version,
        "minimum_macos": MINIMUM_MACOS,
        "architecture": ARCHITECTURE,
        "microphone_usage_description": microphone,
        "icon": icon_name,
        "code_signature": _signature_status(app),
        "nested_code": nested,
    }


def write_release_files(root: Path, app: Path, dmg: Path, output: Path, checksum: Path) -> dict[str, Any]:
    if "INTERNAL-UNSIGNED" not in dmg.name:
        raise ReleaseError("DMG filename must contain INTERNAL-UNSIGNED")
    if not (app.parent / REQUIRED_WARNING).is_file():
        raise ReleaseError(f"mounted DMG is missing {REQUIRED_WARNING}")
    app_data = inspect_app(app, root)
    dmg_bytes = dmg.stat().st_size
    if dmg_bytes > MAX_DMG_BYTES:
        raise ReleaseError(f"DMG exceeds {MAX_DMG_BYTES} byte internal budget")
    digest = sha256(dmg)
    manifest = {
        "schema": SCHEMA,
        "channel": "internal-unsigned",
        "distribution": {
            "developer_id_signed": False,
            "notarized": False,
            "stapled": False,
            "gatekeeper_ready": False,
            "public_distribution": False,
            "trusted_source_required": True,
        },
        "app": app_data,
        "artifact": {
            "filename": dmg.name,
            "bytes": dmg_bytes,
            "max_bytes": MAX_DMG_BYTES,
            "sha256": digest,
        },
    }
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    checksum.write_text(f"{digest}  {dmg.name}\n")
    return manifest


def verify_release_files(root: Path, app: Path, dmg: Path, manifest_path: Path, checksum_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") != SCHEMA or manifest.get("channel") != "internal-unsigned":
        raise ReleaseError("manifest is not an internal unsigned release")
    distribution = manifest.get("distribution", {})
    if any(distribution.get(key) for key in ("developer_id_signed", "notarized", "stapled", "gatekeeper_ready", "public_distribution")):
        raise ReleaseError("manifest makes a forbidden distribution trust claim")
    actual_app = inspect_app(app, root)
    if actual_app != manifest.get("app"):
        raise ReleaseError("mounted app no longer matches the manifest")
    digest = sha256(dmg)
    if manifest.get("artifact", {}).get("sha256") != digest:
        raise ReleaseError("DMG checksum does not match manifest")
    if manifest.get("artifact", {}).get("bytes") != dmg.stat().st_size:
        raise ReleaseError("DMG size does not match manifest")
    if checksum_path.read_text().strip() != f"{digest}  {dmg.name}":
        raise ReleaseError("SHA-256 sidecar file does not match artifact")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("write", "verify"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--dmg", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checksum", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.mode == "write":
            write_release_files(args.root, args.app, args.dmg, args.manifest, args.checksum)
        else:
            verify_release_files(args.root, args.app, args.dmg, args.manifest, args.checksum)
    except (OSError, ValueError, ReleaseError, subprocess.SubprocessError) as error:
        parser.exit(2, f"error: {error}\n")
    print(f"{args.mode} verified: {args.dmg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
