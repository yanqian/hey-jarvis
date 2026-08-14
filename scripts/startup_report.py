#!/usr/bin/env python3
"""Summarize compatible hey-jarvis-startup-v1 JSONL launch records."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable


SCHEMA = "hey-jarvis-startup-v1"
FIELDS = {
    "schema", "launch_id", "build_profile", "sample_kind", "component", "stage",
    "receipt_elapsed_ms", "process_elapsed_ms",
}
COMPONENTS = {"native", "webview", "sidecar"}
PROFILES = {"debug", "release"}
SAMPLE_KINDS = {"cold", "warm", "unspecified"}
MAX_ELAPSED_MS = 300_000


class ReportError(ValueError):
    pass


def percentile_90(values: list[int]) -> int:
    ordered = sorted(values)
    return ordered[max(0, (9 * len(ordered) + 9) // 10 - 1)]


def input_paths(inputs: Iterable[Path]) -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
        if item.is_dir():
            paths.extend(path for path in item.glob("startup*.jsonl*") if path.is_file())
        elif item.is_file():
            paths.append(item)
        else:
            raise ReportError(f"input does not exist: {item}")
    return sorted(set(paths))


def load_records(paths: Iterable[Path]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ReportError(f"{path}:{line_number}: malformed JSON") from exc
            if not isinstance(record, dict) or set(record) != FIELDS:
                raise ReportError(f"{path}:{line_number}: startup fields do not match {SCHEMA}")
            if record["schema"] != SCHEMA:
                raise ReportError(f"{path}:{line_number}: unsupported startup schema")
            if (
                not isinstance(record["launch_id"], str)
                or not record["launch_id"].startswith("launch-")
                or len(record["launch_id"]) > 64
                or record["build_profile"] not in PROFILES
                or record["sample_kind"] not in SAMPLE_KINDS
                or record["component"] not in COMPONENTS
                or not isinstance(record["stage"], str)
                or not 1 <= len(record["stage"]) <= 64
            ):
                raise ReportError(f"{path}:{line_number}: invalid bounded startup value")
            for name in ("receipt_elapsed_ms", "process_elapsed_ms"):
                value = record[name]
                if value is not None and (
                    not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= MAX_ELAPSED_MS
                ):
                    raise ReportError(f"{path}:{line_number}: invalid {name}")
            if record["receipt_elapsed_ms"] is None and record["process_elapsed_ms"] is None:
                raise ReportError(f"{path}:{line_number}: startup record has no duration")
            records.append(record)
    if not records:
        raise ReportError("no startup records found")
    return records


def summarize(
    records: list[dict[str, object]],
    profile: str | None,
    sample_kind: str | None,
    latest: int | None = None,
) -> dict[str, object]:
    selected = [
        record for record in records
        if (profile is None or record["build_profile"] == profile)
        and (sample_kind is None or record["sample_kind"] == sample_kind)
    ]
    if not selected:
        raise ReportError("no startup records match the requested profile/sample kind")
    if latest is not None:
        launch_order = list(dict.fromkeys(str(record["launch_id"]) for record in selected))
        selected_ids = set(launch_order[-latest:])
        selected = [record for record in selected if str(record["launch_id"]) in selected_ids]
    profiles = {str(record["build_profile"]) for record in selected}
    sample_kinds = {str(record["sample_kind"]) for record in selected}
    if len(profiles) != 1 or len(sample_kinds) != 1:
        raise ReportError("mixed build profiles or sample kinds; filter to compatible runs")

    per_launch: dict[str, set[tuple[str, str]]] = defaultdict(set)
    metrics: dict[str, list[int]] = defaultdict(list)
    for record in selected:
        identity = (str(record["component"]), str(record["stage"]))
        launch_id = str(record["launch_id"])
        if identity in per_launch[launch_id]:
            raise ReportError(f"duplicate milestone {identity[0]}.{identity[1]} in {launch_id}")
        per_launch[launch_id].add(identity)
        for clock, field in (("receipt", "receipt_elapsed_ms"), ("process", "process_elapsed_ms")):
            value = record[field]
            if value is not None:
                metrics[f"{identity[0]}.{identity[1]}.{clock}"].append(int(value))

    stages = {
        name: {
            "count": len(values),
            "median_ms": round(statistics.median(values), 1),
            "p90_ms": percentile_90(values),
            "max_ms": max(values),
        }
        for name, values in sorted(metrics.items())
    }
    return {
        "schema": "hey-jarvis-startup-report-v1",
        "build_profile": next(iter(profiles)),
        "sample_kind": next(iter(sample_kinds)),
        "launches": len(per_launch),
        "stages": stages,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--profile", choices=sorted(PROFILES))
    parser.add_argument("--sample-kind", choices=sorted(SAMPLE_KINDS))
    parser.add_argument("--latest", type=int, choices=range(1, 101), metavar="N")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = summarize(
            load_records(input_paths(args.inputs)), args.profile, args.sample_kind, args.latest
        )
    except ReportError as exc:
        print(f"startup report error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    print(f"{report['build_profile']} {report['sample_kind']} launches={report['launches']}")
    for stage, values in report["stages"].items():
        print(f"{stage:42} n={values['count']:>2} median={values['median_ms']:>7}ms p90={values['p90_ms']:>6}ms max={values['max_ms']:>6}ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
