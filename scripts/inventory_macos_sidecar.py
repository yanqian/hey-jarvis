#!/usr/bin/env python3
"""Write deterministic F090 manifests for a PyInstaller onedir runtime."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
from pathlib import Path


MACHO_SUFFIXES = {".dylib", ".so"}
MODEL_NAMES = {
    "melspectrogram.tflite",
    "embedding_model.tflite",
    "hey_jarvis_v0.1.tflite",
}
SIDECAR_BUDGET_BYTES = 180 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]
INPUT_PATHS = (
    ROOT / "packaging" / "macos-sidecar" / "build-requirements.lock",
    ROOT / "packaging" / "macos-sidecar" / "requirements.lock",
    ROOT / "packaging" / "macos-sidecar" / "models.lock",
    ROOT / "packaging" / "macos-sidecar" / "openwakeword-runtime-init.py",
    ROOT / "packaging" / "macos-sidecar" / "hey_jarvis_sidecar.spec",
    ROOT / "scripts" / "build_macos_sidecar.sh",
    ROOT / "scripts" / "normalize_zip.py",
    ROOT / "app" / "sidecar" / "product_sidecar.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command(*args: str) -> str:
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def artifact_entry(runtime: Path, path: Path) -> dict[str, object]:
    relative = path.relative_to(runtime).as_posix()
    mode = stat.S_IMODE(path.stat().st_mode)
    description = command("file", "-b", str(path))
    executable = bool(mode & 0o111)
    macho = "Mach-O" in description
    entry: dict[str, object] = {
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "mode": f"{mode:04o}",
        "executable": executable,
        "file_type": description,
        "signing_class": "nested_code" if macho or executable else "resource",
    }
    if macho:
        entry["architectures"] = command("lipo", "-archs", str(path)).split()
        linked = command("otool", "-L", str(path)).splitlines()[1:]
        entry["linked_libraries"] = [line.strip().split(" ", 1)[0] for line in linked]
    return entry


def license_files(distribution: importlib.metadata.Distribution) -> list[Path]:
    root = Path(distribution.locate_file(""))
    result: list[Path] = []
    for item in distribution.files or ():
        name = Path(item).name.upper()
        if name.startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE")):
            path = root / item
            if path.is_file():
                result.append(path)
    return sorted(set(result))


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_manifests(runtime: Path, output: Path) -> None:
    if not runtime.is_dir() or not (runtime / "hey-jarvis-sidecar").is_file():
        raise SystemExit(f"invalid onedir runtime: {runtime}")
    output.mkdir(parents=True, exist_ok=True)
    licenses_dir = output / "licenses"
    if licenses_dir.exists():
        shutil.rmtree(licenses_dir)
    licenses_dir.mkdir()

    files = sorted(path for path in runtime.rglob("*") if path.is_file())
    artifacts = [artifact_entry(runtime, path) for path in files]
    nested = [entry for entry in artifacts if entry["signing_class"] == "nested_code"]
    invalid_arch = [
        entry["path"]
        for entry in nested
        if "architectures" in entry and entry["architectures"] != ["arm64"]
    ]
    if invalid_arch:
        raise SystemExit("non-arm64 nested code: " + ", ".join(invalid_arch))

    dependencies: list[dict[str, object]] = []
    for distribution in sorted(
        importlib.metadata.distributions(),
        key=lambda value: (value.metadata.get("Name") or "").lower(),
    ):
        name = distribution.metadata.get("Name") or "unknown"
        copied: list[dict[str, str]] = []
        destination = licenses_dir / name.lower().replace("_", "-")
        for index, source in enumerate(license_files(distribution), start=1):
            destination.mkdir(exist_ok=True)
            target = destination / f"{index:02d}-{source.name}"
            shutil.copyfile(source, target)
            copied.append({"path": target.relative_to(output).as_posix(), "sha256": sha256(target)})
        dependencies.append(
            {
                "name": name,
                "version": distribution.version,
                "license_expression": distribution.metadata.get("License-Expression"),
                "license": distribution.metadata.get("License"),
                "license_files": copied,
            }
        )

    models = [entry for entry in artifacts if Path(str(entry["path"])).name in MODEL_NAMES]
    if {Path(str(entry["path"])).name for entry in models} != MODEL_NAMES:
        raise SystemExit("runtime does not contain exactly the required wake model set")
    forbidden = [
        entry["path"]
        for entry in artifacts
        if str(entry["path"]).endswith(".onnx")
        or "/scipy/" in f"/{entry['path']}/"
        or "/sklearn/" in f"/{entry['path']}/"
    ]
    if forbidden:
        raise SystemExit("forbidden optional runtime content: " + ", ".join(forbidden[:10]))

    total = sum(int(entry["bytes"]) for entry in artifacts)
    write_json(output / "artifact-manifest.json", {"files": artifacts})
    write_json(output / "nested-code-manifest.json", {"nested_code": nested})
    write_json(output / "dependency-license-manifest.json", {"distributions": dependencies})
    write_json(output / "model-manifest.json", {"models": models})
    write_json(
        output / "build-manifest.json",
        {
            "format": 1,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "source_date_epoch": os.environ.get("SOURCE_DATE_EPOCH"),
            "runtime_bytes": total,
            "runtime_budget_bytes": SIDECAR_BUDGET_BYTES,
            "within_runtime_budget": total <= SIDECAR_BUDGET_BYTES,
            "inputs": {
                path.relative_to(ROOT).as_posix(): sha256(path)
                for path in INPUT_PATHS
            },
            "artifact_manifest_sha256": sha256(output / "artifact-manifest.json"),
            "nested_code_manifest_sha256": sha256(output / "nested-code-manifest.json"),
            "dependency_license_manifest_sha256": sha256(output / "dependency-license-manifest.json"),
            "model_manifest_sha256": sha256(output / "model-manifest.json"),
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--build-env", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    del args.build_env  # Invocation through that environment is the dependency boundary.
    build_manifests(args.runtime.resolve(), args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
