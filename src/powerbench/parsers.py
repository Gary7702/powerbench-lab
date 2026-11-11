"""Instrument adapters with explicit schemas, units, and row-level diagnostics.

The native ATE contract is No./Io/Vo/Vi/Ii/Po/Pi/Ploss/Effi. Grid tables
and text-only reports share the same validator; no numeric column is guessed.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from powerbench.models import Conditions, Issue, Measurement, ParseError, Run, Settings

_FILENAME = re.compile(
    r"^_*(?P<sample>[^_]+)_(?P<channel>[1-9]\d*|S)_"
    r"(?P<vin>\d+(?:\.\d+)?)_(?P<vout>\d+(?:\.\d+)?)_"
    r"(?P<frequency>\d+(?:\.\d+)?)_(?P<mode>[^_]+)"
    r"(?:_(?:EFFI_)?(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}[-:]\d{2}[-:]\d{2}))?$",
    re.IGNORECASE,
)

FIELD_ORDER = (
    "point",
    "load_a",
    "vout_v",
    "vin_v",
    "iin_a",
    "pout_w",
    "pin_w",
    "loss_w",
    "efficiency",
)
HEADER_ALIASES: dict[str, set[str]] = {
    "point": {"no", "number", "index", "point"},
    "load_a": {"io", "iout", "load", "loada", "outputcurrent"},
    "vout_v": {"vo", "vout", "voutv", "outputvoltage"},
    "vin_v": {"vi", "vin", "vinv", "inputvoltage"},
    "iin_a": {"ii", "iin", "iina", "inputcurrent"},
    "pout_w": {"po", "pout", "poutw", "outputpower"},
    "pin_w": {"pi", "pin", "pinw", "inputpower"},
    "loss_w": {"ploss", "loss", "lossw", "powerloss"},
    "efficiency": {"effi", "eff", "efficiency", "eta"},
}
_NONFINITE = {
    "inf",
    "+inf",
    "-inf",
    "infinity",
    "+infinity",
    "-infinity",
    "nan",
    "n/a",
    "na",
    "--",
    "",
}


def parse_filename(filename: str) -> Conditions:
    """Read nominal conditions from the basename, not underscore counts in a path."""
    stem = Path(filename.replace("\\", "/")).stem
    match = _FILENAME.fullmatch(stem)
    if match is None:
        raise ParseError(
            "Expected [__]sample_channel_Vin_Vout_frequency-kHz_mode"
            "[_EFFI_YYYY-MM-DD HH-MM-SS].pdf (channel: positive integer or S)."
        )
    values = match.groupdict()
    try:
        return Conditions(
            sample_id=values["sample"],
            channel=values["channel"].upper(),
            vin_v=float(values["vin"]),
            vout_v=float(values["vout"]),
            frequency_khz=float(values["frequency"]),
            mode=values["mode"],
            timestamp=values["timestamp"],
        )
    except ValueError as exc:
        raise ParseError(str(exc)) from exc


def _header_token(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[\[(](?:a|v|w|%)[\])]", "", text)
    return re.sub(r"[^a-z0-9]", "", text)


def _header(row: Sequence[object]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}
    for index, value in enumerate(row):
        token = _header_token(value)
        for field, aliases in HEADER_ALIASES.items():
            if token in aliases:
                explicit = re.search(r"[\[(]\s*([^\])]+)\s*[\])]", str(value))
                units = {
                    "point": "",
                    "load_a": "a",
                    "vout_v": "v",
                    "vin_v": "v",
                    "iin_a": "a",
                    "pout_w": "w",
                    "pin_w": "w",
                    "loss_w": "w",
                    "efficiency": "%",
                }
                if explicit and explicit.group(1).strip().casefold() != units[field]:
                    return None
                if field in mapping:
                    return None
                mapping[field] = index
                break
    return mapping if set(mapping) == set(FIELD_ORDER) else None


def _number(value: object, *, allow_missing: bool = False) -> float | None:
    token = str(value if value is not None else "").strip().replace("\u2212", "-")
    if token.casefold() in _NONFINITE:
        if allow_missing:
            return None
        raise ValueError(f"Non-finite or missing numeric value: {token!r}")
    result = float(token)
    if not math.isfinite(result):
        if allow_missing:
            return None
        raise ValueError("Non-finite numeric value")
    return result


def _measurement(
    row: Sequence[object],
    mapping: dict[str, int],
    settings: Settings,
    source: str,
    page: int,
    row_number: int,
    table_number: int,
) -> tuple[Measurement | None, list[Issue]]:
    issues: list[Issue] = []
    flags: list[str] = []

    def warn(code: str, message: str, field: str | None = None) -> None:
        flags.append(code)
        issues.append(
            Issue(code, message, source, page=page, row=row_number, field=field, table=table_number)
        )

    try:
        if len(row) <= max(mapping.values()):
            raise ValueError("Truncated measurement row")
        values: dict[str, Any] = {
            field: _number(row[index], allow_missing=(field == "efficiency"))
            for field, index in mapping.items()
        }
        if values["point"] != int(values["point"]) or values["point"] < 1:
            raise ValueError("Point number must be a positive integer")
        values["point"] = int(values["point"])
        if values["efficiency"] is None:
            warn(
                "undefined_efficiency",
                "Missing/non-finite efficiency retained as null, not zero.",
                "efficiency",
            )
        elif settings.efficiency_unit == "percent":
            values["efficiency"] /= 100
        efficiency = values["efficiency"]
        if efficiency is not None and not 0 <= efficiency <= 1:
            warn(
                "efficiency_out_of_range",
                "Efficiency lies outside [0, 1]; excluded from peak metrics.",
                "efficiency",
            )
        if values["pin_w"] <= 0:
            warn(
                "nonpositive_input_power",
                "Input power is not positive; efficiency cannot be recomputed.",
                "pin_w",
            )
        elif efficiency is not None:
            calculated = values["pout_w"] / values["pin_w"]
            if abs(calculated - efficiency) > settings.efficiency_tolerance:
                warn(
                    "efficiency_mismatch",
                    "Reported efficiency differs from Pout/Pin beyond tolerance.",
                    "efficiency",
                )
        if values["load_a"] == 0:
            warn(
                "zero_load",
                "Zero-load row retained; excluded only when using a logarithmic x-axis.",
                "load_a",
            )
        for measured, calculated, field in (
            (values["pout_w"], values["load_a"] * values["vout_v"], "pout_w"),
            (values["pin_w"], values["vin_v"] * values["iin_a"], "pin_w"),
            (values["loss_w"], values["pin_w"] - values["pout_w"], "loss_w"),
        ):
            if not math.isclose(
                measured,
                calculated,
                rel_tol=settings.power_rel_tolerance,
                abs_tol=settings.power_abs_tolerance_w,
            ):
                warn(
                    "power_mismatch",
                    f"{field} disagrees with its voltage/current or power balance.",
                    field,
                )
        for field in ("iin_a", "pout_w", "pin_w", "loss_w"):
            if values[field] < 0:
                warn(
                    "negative_power_or_current",
                    f"Negative {field}; verify instrument sign convention.",
                    field,
                )
        return Measurement(
            **values, page=page, row=row_number, flags=tuple(flags), table=table_number
        ), issues
    except (ValueError, TypeError, OverflowError) as exc:
        issues.append(
            Issue(
                "malformed_row",
                f"Measurement row rejected: {exc}",
                source,
                severity="error",
                page=page,
                row=row_number,
                table=table_number,
            )
        )
        return None, issues


def parse_tables(
    tables: Iterable[tuple[int, Sequence[Sequence[object]]]],
    conditions: Conditions,
    *,
    source: str,
    sha256: str = "",
    settings: Settings | None = None,
    synthetic: bool = False,
) -> Run:
    """Parse (one-based page, table rows) pairs; repeat headers may span pages.

    Headers are required on the first relevant table. A later headerless table
    may continue that exact schema. Bad measurement rows are reported as errors,
    not silently dropped; callers can make any diagnostic fatal with --strict.
    """
    settings = settings or Settings()
    measurements: list[Measurement] = []
    issues: list[Issue] = []
    previous_mapping: dict[str, int] | None = None
    table_counts: dict[int, int] = {}
    for page, rows in tables:
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise ParseError("Table page must be a positive one-based integer.")
        table_counts[page] = table_counts.get(page, 0) + 1
        table_number = table_counts[page]
        mapping = previous_mapping
        for row_number, row in enumerate(rows, 1):
            new_mapping = _header(row)
            if new_mapping is not None:
                mapping = previous_mapping = new_mapping
                efficiency_header = str(row[mapping["efficiency"]])
                if "%" in efficiency_header and settings.efficiency_unit != "percent":
                    raise ParseError(
                        "Efficiency header declares percent; set efficiency_unit='percent'."
                    )
                continue
            if not row or all(cell is None or not str(cell).strip() for cell in row):
                continue
            recognized = sum(
                any(_header_token(cell) in aliases for aliases in HEADER_ALIASES.values())
                for cell in row
            )
            if recognized >= 3:
                raise ParseError(
                    "Incomplete, duplicate, or unsupported-unit ATE header; refusing guessed columns."
                )
            if mapping is None:
                continue
            point_index = mapping["point"]
            point_token = str(row[point_index]).strip() if point_index < len(row) else ""
            numbered = re.fullmatch(r"[+-]?\d+(?:\.\d+)?", point_token) is not None
            numeric_cells = sum(
                re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", str(cell).strip())
                is not None
                for cell in row
            )
            # Titles/metadata are not data. Numbered short rows and rows with an
            # invalid point but numeric fields are still candidates: diagnose them.
            if not numbered and numeric_cells < 2:
                continue
            measurement, row_issues = _measurement(
                row, mapping, settings, source, page, row_number, table_number
            )
            issues.extend(row_issues)
            if measurement is not None:
                measurements.append(measurement)
    if not measurements:
        raise ParseError("No valid measurements under a recognized nine-column ATE header.")
    loads = [m.load_a for m in measurements]
    if loads != sorted(loads):
        issues.append(
            Issue(
                "unsorted_loads",
                "Source row order retained; interpolation/plots sort by actual load.",
                source,
            )
        )
    sorted_loads = sorted(loads)
    if any(
        b - a <= settings.duplicate_load_tolerance_a
        for a, b in zip(sorted_loads, sorted_loads[1:], strict=False)
    ):
        issues.append(
            Issue(
                "duplicate_loads",
                "Repeated load points retained; line interpolation is ambiguous.",
                source,
            )
        )
    if not sha256:
        serialized = json.dumps(
            [m.as_dict() for m in measurements], sort_keys=True, allow_nan=False
        )
        sha256 = hashlib.sha256(serialized.encode()).hexdigest()
    return Run(conditions, tuple(measurements), source, sha256, tuple(issues), synthetic)


def parse_text(
    text: str,
    conditions: Conditions,
    *,
    source: str,
    sha256: str = "",
    settings: Settings | None = None,
    synthetic: bool = False,
) -> Run:
    """Whitespace-delimited fallback for born-digital tables; no OCR is attempted."""
    tables = [
        (page, [line.split() for line in content.splitlines()])
        for page, content in enumerate(text.split("\f"), 1)
    ]
    return parse_tables(
        tables, conditions, source=source, sha256=sha256, settings=settings, synthetic=synthetic
    )


def parse_pdf(path: Path, settings: Settings | None = None, *, source: str | None = None) -> Run:
    """Read every page with a grid-first, text-fallback adapter; files are closed.

    Scanned/OCR-only files are explicitly unsupported. Passwords, retries, or
    execution of embedded content are never inferred from the input.
    """
    import pdfplumber

    source = source or path.name
    conditions = parse_filename(path.name)
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        tables: list[tuple[int, Sequence[Sequence[object]]]] = []
        with pdfplumber.open(path) as pdf:
            if not pdf.pages:
                raise ParseError("Empty PDF.")
            for page_number, page in enumerate(pdf.pages, 1):
                page_tables = page.extract_tables() or []
                usable = [
                    table
                    for table in page_tables
                    if any(_header(row) is not None for row in table)
                    or (tables and any(len(row) == len(FIELD_ORDER) for row in table))
                ]
                if usable:
                    tables.extend((page_number, table) for table in usable)
                else:
                    text = page.extract_text() or ""
                    if not text.strip():
                        raise ParseError(
                            f"Page {page_number} has no extractable text; scanned PDFs need external OCR."
                        )
                    tables.append((page_number, [line.split() for line in text.splitlines()]))
        return parse_tables(tables, conditions, source=source, sha256=digest, settings=settings)
    except ParseError:
        raise
    except Exception as exc:
        # Third-party readers have many format-specific exception types.
        # Keep paths/data out of a public report, but preserve the original cause.
        raise ParseError(
            f"PDF reader failed ({type(exc).__name__}); check the file is readable and unencrypted."
        ) from exc


def parse_table_json(
    path: Path, settings: Settings | None = None, *, source: str | None = None
) -> Run:
    """Read the portable, versioned table interchange format used by demo/tests."""
    try:
        raw = path.read_bytes()
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("schema_version") != "1.0":
            raise ValueError("Expected a JSON object with table schema_version='1.0'")
        if not isinstance(data.get("conditions"), dict):
            raise ValueError("conditions must be an object")
        if not isinstance(data.get("tables"), list) or not data["tables"]:
            raise ValueError("tables must be a non-empty array")
        conditions = Conditions(**data["conditions"])
        tables = []
        for table in data["tables"]:
            if not isinstance(table, dict) or not isinstance(table.get("rows"), list):
                raise ValueError("Each table must contain a rows array")
            for row in table["rows"]:
                if not isinstance(row, list) or any(
                    isinstance(cell, list | dict | bool) for cell in row
                ):
                    raise ValueError("Table rows must be arrays of numeric/text/null cells")
            tables.append((table["page"], table["rows"]))
        return parse_tables(
            tables,
            conditions,
            source=source or path.name,
            sha256=hashlib.sha256(raw).hexdigest(),
            settings=settings,
            synthetic=data.get("synthetic") is True,
        )
    except ParseError:
        raise
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ParseError(f"Invalid table JSON: {exc}") from exc
