"""Report serialization, safe spreadsheet export and publication-quality plots."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from powerbench import __version__
from powerbench.analysis import group_runs, line_regulation, summarize_run
from powerbench.models import Batch, GroupField, Run, Settings

MEASUREMENT_FIELDS = (
    "run_id",
    "source",
    "sample_id",
    "channel",
    "vin_nominal_v",
    "vout_nominal_v",
    "frequency_khz",
    "mode",
    "point",
    "load_a",
    "vout_v",
    "vin_v",
    "iin_a",
    "pout_w",
    "pin_w",
    "loss_w",
    "efficiency_fraction",
    "efficiency_pct",
    "page",
    "table",
    "row",
    "flags",
)
SUMMARY_FIELDS = (
    "source",
    "sample_id",
    "channel",
    "vin_v",
    "vout_v",
    "frequency_khz",
    "mode",
    "points",
    "peak_efficiency_pct",
    "peak_load_a",
    "load_min_a",
    "load_max_a",
    "vout_mean_v",
    "vout_min_v",
    "vout_max_v",
    "load_regulation_positive_pct",
    "load_regulation_negative_pct",
    "load_regulation_span_pct",
)


def csv_safe(value: object) -> object:
    """Escape spreadsheet formula prefixes in text only; preserve numeric negatives."""
    if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def write_csv(path: Path, headers: Sequence[str], rows: Iterable[Sequence[object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([csv_safe(value) for value in headers])
        for row in rows:
            writer.writerow([csv_safe(value) for value in row])


def measurement_rows(runs: Sequence[Run]) -> list[list[object]]:
    rows: list[list[object]] = []
    for run in runs:
        c = run.conditions
        for m in run.measurements:
            rows.append(
                [
                    run.run_id,
                    run.source,
                    c.sample_id,
                    c.channel,
                    c.vin_v,
                    c.vout_v,
                    c.frequency_khz,
                    c.mode,
                    m.point,
                    m.load_a,
                    m.vout_v,
                    m.vin_v,
                    m.iin_a,
                    m.pout_w,
                    m.pin_w,
                    m.loss_w,
                    m.efficiency,
                    m.efficiency_pct,
                    m.page,
                    m.table,
                    m.row,
                    ";".join(m.flags),
                ]
            )
    return rows


def summary_rows(summaries: Sequence[dict[str, Any]]) -> list[list[object]]:
    return [[{**s["conditions"], **s}.get(field) for field in SUMMARY_FIELDS] for s in summaries]


def build_payload(
    batch: Batch, settings: Settings | None = None, targets_a: tuple[float, ...] | None = None
) -> dict[str, Any]:
    settings = settings or Settings()
    issues = batch.all_issues
    return {
        "schema_version": "1.0",
        "package_version": __version__,
        "synthetic": bool(batch.runs) and all(run.synthetic for run in batch.runs),
        "contains_synthetic": any(run.synthetic for run in batch.runs),
        "counts": {
            "files": batch.discovered,
            "runs": len(batch.runs),
            "measurements": batch.measurement_count,
            "failed_files": batch.failed,
            "skipped_files": batch.skipped,
            "warnings": sum(i.severity == "warning" for i in issues),
            "errors": sum(i.severity == "error" for i in issues),
        },
        "units": {
            "current": "A",
            "voltage": "V",
            "power": "W",
            "frequency": "kHz",
            "efficiency": "fraction",
        },
        "method": {
            "load_regulation": "100*(max(Vout)-mean(Vout))/mean(Vout) and 100*(min(Vout)-mean(Vout))/mean(Vout)",
            "span": "100*(max(Vout)-min(Vout))/mean(Vout)",
            "line_regulation": "Linear interpolation at common actual load, fixed sample/channel/Vout/frequency/mode; no extrapolation.",
            "limitations": "Descriptive measurements, not datasheet pass/fail or uncertainty-qualified metrology. Mode labels are configurable.",
        },
        "settings": settings.as_dict(),
        "runs": [run.as_dict() for run in batch.runs],
        "summaries": [summarize_run(run) for run in batch.runs],
        "line_regulation": line_regulation(
            batch.runs, targets_a=targets_a, tolerance_a=settings.duplicate_load_tolerance_a
        ),
        "issues": [issue.as_dict() for issue in issues],
    }


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )


def write_workbook(path: Path, batch: Batch, payload: dict[str, Any]) -> None:
    """Structured workbook with numeric values, filtering, and a native XY chart.

    Never turn untrusted input text into formulas or hyperlinks. All formulas
    are replaced by already-tested analysis results with documented definitions.
    """
    import xlsxwriter

    with xlsxwriter.Workbook(
        path, {"strings_to_formulas": False, "strings_to_urls": False}
    ) as workbook:
        workbook.set_properties({"title": "PowerBench Lab analysis", "author": "PowerBench Lab"})
        header = workbook.add_format(
            {"bold": True, "bg_color": "#E7F4F2", "font_color": "#183E48", "border": 0}
        )
        numeric = workbook.add_format({"num_format": "0.0000"})
        text = workbook.add_format({"text_wrap": True, "valign": "top"})

        def sheet(name: str, columns: Sequence[str], rows: list[list[object]]) -> Any:
            ws = workbook.add_worksheet(name)
            ws.freeze_panes(1, 0)
            ws.set_row(0, 32)
            ws.set_column(0, len(columns) - 1, 18, numeric)
            for col, label in enumerate(columns):
                ws.write_string(0, col, label, header)
            for row_index, values in enumerate(rows, 1):
                for col, value in enumerate(values):
                    if value is None:
                        ws.write_blank(row_index, col, None)
                    elif isinstance(value, int | float) and not isinstance(value, bool):
                        ws.write_number(row_index, col, value)
                    else:
                        ws.write_string(row_index, col, str(value))
            ws.autofilter(0, 0, len(rows), len(columns) - 1)
            return ws

        sheet("Measurements", MEASUREMENT_FIELDS, measurement_rows(batch.runs))
        sheet("Summary", SUMMARY_FIELDS, summary_rows(payload["summaries"]))
        line_columns = (
            "status",
            "load_a",
            "positive_pct",
            "negative_pct",
            "span_pct",
            "conditions",
            "sources",
            "message",
        )
        line_rows = [
            [
                json.dumps(entry.get(field), ensure_ascii=False)
                if isinstance(entry.get(field), dict | list)
                else entry.get(field)
                for field in line_columns
            ]
            for entry in payload["line_regulation"]
        ]
        sheet("Line Regulation", line_columns, line_rows)
        issue_columns = ("severity", "code", "source", "page", "row", "field", "message")
        sheet(
            "Diagnostics",
            issue_columns,
            [[issue.get(field) for field in issue_columns] for issue in payload["issues"]],
        )
        readme = workbook.add_worksheet("Read Me")
        readme.set_column(0, 0, 26)
        readme.set_column(1, 1, 100, text)
        notes = [
            ("PowerBench Lab", f"Version {__version__}; schema 1.0"),
            (
                "Data provenance",
                "SYNTHETIC DEMONSTRATION ONLY"
                if payload["synthetic"]
                else "User-supplied input; review confidentiality before sharing.",
            ),
            (
                "Units",
                "Current A; voltage V; power W; switching frequency kHz. Efficiency fraction and percent are separate columns.",
            ),
            (
                "Missing efficiency",
                "Empty cell means unavailable/non-finite; never imputed as zero.",
            ),
            ("Load regulation", payload["method"]["load_regulation"]),
            ("Line regulation", payload["method"]["line_regulation"]),
            ("Scope", payload["method"]["limitations"]),
            (
                "Formula safety",
                "All input strings are literal text. Numeric results are calculated by the Python analysis module.",
            ),
        ]
        for row_index, (key, value) in enumerate(notes):
            readme.write_string(row_index, 0, key, header)
            readme.write_string(row_index, 1, value, text)
            readme.set_row(row_index, 40)
        if batch.runs:
            group = group_runs(batch.runs, "vin_v")[0]
            chart = workbook.add_chart({"type": "scatter", "subtype": "straight_with_markers"})
            first_rows: dict[str, int] = {}
            start = 1
            for run in batch.runs:
                first_rows[run.run_id] = start
                start += len(run.measurements)
            for run in group:
                first = first_rows[run.run_id]
                last = first + len(run.measurements) - 1
                chart.add_series(
                    {
                        "name": f"Vin {run.conditions.vin_v:g} V",
                        "categories": ["Measurements", first, 9, last, 9],
                        "values": ["Measurements", first, 17, last, 17],
                        "marker": {"type": "circle", "size": 4},
                    }
                )
            chart.set_title({"name": "Efficiency | comparable input-voltage sweep"})
            chart.set_x_axis({"name": "Load current (A)"})
            chart.set_y_axis({"name": "Efficiency (%)", "min": 0, "max": 100})
            chart.set_size({"width": 900, "height": 460})
            chart.set_legend({"position": "bottom"})
            readme.insert_chart("A11", chart)


def write_plots(
    directory: Path,
    runs: Sequence[Run],
    *,
    varying: GroupField = "vin_v",
    log_x: bool = False,
    settings: Settings | None = None,
) -> list[Path]:
    from matplotlib import rc_context
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    settings = settings or Settings()
    directory.mkdir(parents=True, exist_ok=True)
    output: list[Path] = []
    colors = ("#087F8C", "#D76A37", "#6656B8", "#2465AD", "#BB4C77", "#537C4A")
    with rc_context({"svg.fonttype": "none", "svg.hashsalt": "powerbench-lab", "font.size": 10}):
        for index, group in enumerate(group_runs(runs, varying), 1):
            fig = Figure(figsize=(10.4, 5.8), dpi=150, facecolor="#FFFFFF", layout="constrained")
            FigureCanvasAgg(fig)
            ax = fig.add_subplot(111)
            ax.set_facecolor("#F8FBFC")
            for run_index, run in enumerate(group):
                points = sorted(
                    (m for m in run.measurements if not log_x or m.load_a > 0),
                    key=lambda m: m.load_a,
                )
                x = [m.load_a for m in points]
                y = [
                    m.efficiency_pct
                    if m.efficiency is not None and 0 <= m.efficiency <= 1
                    else float("nan")
                    for m in points
                ]
                value = getattr(run.conditions, varying)
                units = {"vin_v": " V", "vout_v": " V", "frequency_khz": " kHz"}
                names = {
                    "vin_v": "Vin",
                    "vout_v": "Vout",
                    "frequency_khz": "Frequency",
                    "channel": "Channel",
                    "sample_id": "Sample",
                }
                label = f"{names.get(varying, varying)} {value}{units.get(varying, '')}"
                if varying == "mode":
                    label = settings.mode_labels.get(str(value), f"Mode {value}")
                ax.plot(
                    x,
                    y,
                    marker="o",
                    markersize=3.6,
                    linewidth=1.8,
                    color=colors[run_index % len(colors)],
                    label=label,
                )
            c = group[0].conditions
            condition_labels = {
                "sample_id": f"Sample {c.sample_id}",
                "channel": f"CH {c.channel}",
                "vin_v": f"Vin {c.vin_v:g} V",
                "vout_v": f"Vout {c.vout_v:g} V",
                "frequency_khz": f"{c.frequency_khz:g} kHz",
                "mode": settings.mode_labels.get(c.mode, f"Mode {c.mode}"),
            }
            fixed = [label for name, label in condition_labels.items() if name != varying]
            ax.set_title(
                "Efficiency vs. load\n" + "  |  ".join(fixed),
                loc="left",
                fontsize=11,
                pad=18,
                color="#203B4A",
            )
            ax.set_xlabel("Load current (A)" + (" | log scale; zero excluded" if log_x else ""))
            ax.set_ylabel("Efficiency (%)")
            ax.set_ylim(0, 101)
            if log_x and any(m.load_a > 0 for run in group for m in run.measurements):
                ax.set_xscale("log")
            ax.grid(True, which="both", color="#DFE7EB", linewidth=0.6)
            for spine in ax.spines.values():
                spine.set_color("#D7E2E7")
            ax.legend(loc="lower right", frameon=True, facecolor="white")
            label = (
                "SYNTHETIC DEMO - not a device specification"
                if all(r.synthetic for r in group)
                else "Source-preserving analysis - review diagnostics"
            )
            fig.suptitle(
                "POWERBENCH LAB  /  " + label, fontsize=9, color="#527482", x=0.02, ha="left"
            )
            for extension in ("svg", "png"):
                path = directory / f"efficiency-{varying}-{index:02d}.{extension}"
                metadata: dict[str, str | None] = (
                    {"Date": None} if extension == "svg" else {"Software": "PowerBench Lab"}
                )
                fig.savefig(path, metadata=metadata)
                output.append(path)
            fig.clear()
    return output


def write_manifest(directory: Path, batch: Batch, settings: Settings) -> Path:
    artifacts = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            artifacts.append(
                {
                    "path": path.relative_to(directory).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "bytes": path.stat().st_size,
                }
            )
    path = directory / "manifest.json"
    write_json(
        path,
        {
            "schema_version": "1.0",
            "package_version": __version__,
            "settings": settings.as_dict(),
            "inputs": [
                {"source": r.source, "sha256": r.sha256, "synthetic": r.synthetic}
                for r in batch.runs
            ],
            "artifacts": artifacts,
        },
    )
    return path
