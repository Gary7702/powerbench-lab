"""A small command-line surface over the tested analysis pipeline."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, cast

from powerbench import __version__
from powerbench.batch import discover_inputs, process_batch
from powerbench.config import load_settings
from powerbench.demo import write_demo_inputs
from powerbench.exports import (
    MEASUREMENT_FIELDS,
    SUMMARY_FIELDS,
    build_payload,
    measurement_rows,
    summary_rows,
    write_csv,
    write_json,
    write_manifest,
    write_plots,
    write_workbook,
)
from powerbench.logs import LogResult, parse_log, wide_log_rows
from powerbench.models import GROUP_FIELDS, Batch, GroupField, PowerBenchError, Settings
from powerbench.report import render_report

FORMATS = {"html", "json", "csv", "xlsx", "plots"}


def _formats(value: str) -> tuple[str, ...]:
    formats = tuple(dict.fromkeys(item.strip().lower() for item in value.split(",")))
    if not formats or any(item not in FORMATS for item in formats):
        raise argparse.ArgumentTypeError(
            "Formats must be a comma-separated subset of html,json,csv,xlsx,plots."
        )
    return formats


def _targets(value: str) -> tuple[float, ...]:
    try:
        values = tuple(float(item) for item in value.split(","))
        if not values or any(not math.isfinite(item) or item < 0 for item in values):
            raise ValueError
        return values
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Loads must be finite nonnegative amperes, e.g. 0,1,2."
        ) from exc


def _prepare_output(path: Path) -> None:
    if path.is_symlink() or (path.exists() and (not path.is_dir() or any(path.iterdir()))):
        raise PowerBenchError(
            f"Output is not an empty directory: {path}. Choose a new path; nothing was overwritten."
        )
    path.mkdir(parents=True, exist_ok=True)


def _exit_code(batch: Batch, strict: bool) -> int:
    if not batch.runs or batch.has_errors:
        return 1
    return 1 if strict and batch.all_issues else 0


def _generate(
    batch: Batch,
    output: Path,
    settings: Settings,
    formats: tuple[str, ...],
    *,
    targets: tuple[float, ...] | None = None,
    varying: GroupField = "vin_v",
    log_x: bool = False,
    legacy_wide: bool = False,
) -> dict[str, Any]:
    payload = build_payload(batch, settings, targets)
    # Machine-readable diagnostics are always written, including failed batches.
    write_json(output / "diagnostics.json", payload["issues"])
    if "json" in formats:
        write_json(output / "results.json", payload)
    if "html" in formats:
        render_report(payload, output / "report.html")
    if "csv" in formats:
        write_csv(output / "measurements.csv", MEASUREMENT_FIELDS, measurement_rows(batch.runs))
        write_csv(output / "summary.csv", SUMMARY_FIELDS, summary_rows(payload["summaries"]))
        line_headers = (
            "status",
            "load_a",
            "positive_pct",
            "negative_pct",
            "span_pct",
            "conditions",
            "sources",
            "message",
        )
        rows = [
            [
                json.dumps(entry.get(key), ensure_ascii=False)
                if isinstance(entry.get(key), dict | list)
                else entry.get(key)
                for key in line_headers
            ]
            for entry in payload["line_regulation"]
        ]
        write_csv(output / "line_regulation.csv", line_headers, rows)
    if "xlsx" in formats:
        write_workbook(output / "analysis.xlsx", batch, payload)
    if "plots" in formats:
        write_plots(output / "plots", batch.runs, varying=varying, log_x=log_x, settings=settings)
    if legacy_wide:
        width = max((len(run.measurements) for run in batch.runs), default=0)
        headers = ("source", "metric", "unit", *(f"point_{index}" for index in range(1, width + 1)))
        rows = []
        for run in batch.runs:
            for metric, unit, values in (
                ("load", "A", [m.load_a for m in run.measurements]),
                ("efficiency", "%", [m.efficiency_pct for m in run.measurements]),
            ):
                rows.append([run.source, metric, unit, *values, *([None] * (width - len(values)))])
        write_csv(output / "curves-wide.csv", headers, rows)
    write_manifest(output, batch, settings)
    return payload


def _print_counts(payload: dict[str, Any], output: Path | None = None) -> None:
    counts = payload["counts"]
    print(
        f"PowerBench Lab {__version__}: {counts['runs']} runs, {counts['measurements']} points, "
        f"{counts['warnings']} warnings, {counts['errors']} errors."
    )
    if output is not None:
        print(f"Artifacts: {output.resolve()}")


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, help="TOML settings; unknown keys are rejected.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return failure on any diagnostic, including warnings.",
    )


def _report_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="New or empty output directory; never overwritten.",
    )
    parser.add_argument("--formats", type=_formats, default=_formats("html,json,csv,xlsx,plots"))
    parser.add_argument(
        "--vary",
        choices=GROUP_FIELDS,
        default="vin_v",
        help="The one condition allowed to vary in static plots.",
    )
    parser.add_argument(
        "--log-x",
        action="store_true",
        help="Logarithmic static plots (A); zero-load rows remain in data.",
    )
    parser.add_argument(
        "--loads", type=_targets, help="Matched actual loads for line regulation, in A."
    )
    parser.add_argument(
        "--legacy-wide",
        action="store_true",
        help="Also export clearly labelled alternating load/efficiency rows.",
    )
    _common(parser)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="powerbench", description="Traceable DC-DC converter test analysis, entirely local."
    )
    parser.add_argument("--version", action="version", version=f"powerbench {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser(
        "analyze", help="Analyze instrument PDFs or versioned table JSON."
    )
    analyze.add_argument("inputs", nargs="+", type=Path)
    analyze.add_argument(
        "--recursive",
        action="store_true",
        help="Explicitly include nested folders; default is top-level only.",
    )
    _report_options(analyze)
    demo = commands.add_parser(
        "demo", help="Generate and analyze deterministic synthetic fixtures."
    )
    _report_options(demo)
    validate = commands.add_parser(
        "validate", help="Read and validate without creating output files."
    )
    validate.add_argument("inputs", nargs="+", type=Path)
    validate.add_argument("--recursive", action="store_true")
    validate.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print structured diagnostics to stdout.",
    )
    _common(validate)
    logs = commands.add_parser("logs", help="Extract voltage records from UTF-8/UTF-16 ATE logs.")
    logs.add_argument("inputs", nargs="+", type=Path)
    logs.add_argument("--output", "-o", type=Path, required=True)
    logs.add_argument("--metric", default="读取输出电压", help="Exact metric in delimiter field 3.")
    logs.add_argument("--delimiter", default="......")
    logs.add_argument("--encoding", help="Explicit codec for non-UTF files (never guessed).")
    logs.add_argument(
        "--include-failed", action="store_true", help="Include filenames containing FAIL."
    )
    logs.add_argument("--recursive", action="store_true")
    logs.add_argument("--strict", action="store_true")
    logs.add_argument(
        "--headers",
        type=Path,
        help="JSON array of explicit names for an additional positional wide export.",
    )
    return parser


def _run_logs(args: argparse.Namespace) -> int:
    paths: set[Path] = set()
    for path in args.inputs:
        if not path.exists() or path.is_symlink():
            raise PowerBenchError(f"Missing or symbolic-link log input: {path.name}")
        candidates = (
            (path.rglob("*") if args.recursive else path.iterdir()) if path.is_dir() else (path,)
        )
        for candidate in candidates:
            if (
                candidate.is_file()
                and not candidate.is_symlink()
                and candidate.suffix.lower() in {".log", ".txt"}
            ):
                paths.add(candidate.resolve())
    if not paths:
        raise PowerBenchError("No .log or .txt inputs found.")
    results: list[LogResult] = []
    for path in sorted(paths):
        results.append(
            parse_log(
                path,
                metric=args.metric,
                delimiter=args.delimiter,
                encoding=args.encoding,
                include_failed=args.include_failed,
            )
        )
    wide: list[list[object]] | None = None
    headers: list[str] = []
    if args.headers:
        headers = json.loads(args.headers.read_text(encoding="utf-8"))
        if not isinstance(headers, list) or not all(isinstance(header, str) for header in headers):
            raise PowerBenchError("Headers must be a JSON array of strings.")
        wide = wide_log_rows(tuple(results), tuple(headers))
    _prepare_output(args.output)
    values = [value for result in results for value in result.values]
    issues = [issue for result in results for issue in result.issues]
    write_csv(
        args.output / "voltage-readings.csv",
        ("source", "line", "sequence", "metric", "value", "unit"),
        [list(value.as_dict().values()) for value in values],
    )
    write_json(args.output / "diagnostics.json", [issue.as_dict() for issue in issues])
    if wide is not None:
        write_csv(args.output / "voltage-wide.csv", ["source", *headers], wide)
    write_json(
        args.output / "log-summary.json",
        {
            "files": len(results),
            "values": len(values),
            "skipped": sum(r.skipped for r in results),
            "encodings": {r.source: r.encoding for r in results},
        },
    )
    print(f"Extracted {len(values)} voltage readings from {len(results)} log files.")
    print(f"Artifacts: {args.output.resolve()}")
    return int(
        not values
        or any(issue.severity == "error" for issue in issues)
        or (args.strict and bool(issues))
    )


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    try:
        if args.command == "logs":
            return _run_logs(args)
        settings = load_settings(args.config)
        if args.command == "demo":
            _prepare_output(args.output)
            # Demo fixture efficiencies always use fractions, independently of an input adapter config.
            if settings.efficiency_unit != "fraction":
                raise PowerBenchError(
                    "The built-in demo uses fraction efficiency; remove a percent-mode config."
                )
            paths = write_demo_inputs(args.output / "inputs")
        else:
            paths = discover_inputs(args.inputs, recursive=args.recursive)
            if not paths:
                raise PowerBenchError("No supported input files found.")
        batch = process_batch(paths, settings)
        if args.command == "validate":
            payload = build_payload(batch, settings)
            if args.as_json:
                print(
                    json.dumps(
                        {"counts": payload["counts"], "issues": payload["issues"]},
                        ensure_ascii=False,
                        allow_nan=False,
                    )
                )
            else:
                _print_counts(payload)
            return _exit_code(batch, args.strict)
        if args.command != "demo":
            _prepare_output(args.output)
        payload = _generate(
            batch,
            args.output,
            settings,
            args.formats,
            targets=args.loads,
            varying=cast(GroupField, args.vary),
            log_x=args.log_x,
            legacy_wide=args.legacy_wide,
        )
        _print_counts(payload, args.output)
        return _exit_code(batch, args.strict)
    except (PowerBenchError, OSError, ValueError) as exc:
        print(f"powerbench: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
