"""Defensive extraction of delimiter-separated ATE voltage logs.

The original layout identifies the metric in field 3 and the value in field 4.
The adapter preserves file/line/sequence provenance. It deliberately does not
invent test conditions from positional values; an explicit header list is needed
for a fixed-layout wide export.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from powerbench.models import Issue, ParseError


@dataclass(frozen=True)
class LogValue:
    source: str
    line: int
    sequence: int
    metric: str
    value: float
    unit: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LogResult:
    source: str
    encoding: str
    values: tuple[LogValue, ...]
    issues: tuple[Issue, ...]
    skipped: bool = False


def _decode(raw: bytes, encoding: str | None) -> tuple[str, str]:
    if encoding:
        return raw.decode(encoding), encoding
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"
    return raw.decode("utf-8-sig"), "utf-8-sig"


def parse_log(
    path: Path,
    *,
    metric: str = "读取输出电压",
    delimiter: str = "......",
    encoding: str | None = None,
    include_failed: bool = False,
) -> LogResult:
    if not delimiter or not metric:
        raise ParseError("Log delimiter and metric must be non-empty.")
    source = path.name
    if "FAIL" in path.stem.upper() and not include_failed:
        return LogResult(
            source,
            "",
            (),
            (Issue("failed_log_skipped", "FAIL-marked log excluded by policy.", source),),
            True,
        )
    try:
        text, used_encoding = _decode(path.read_bytes(), encoding)
    except (OSError, UnicodeError, LookupError) as exc:
        raise ParseError(
            f"Cannot decode log {source}; specify --encoding for non-UTF input."
        ) from exc
    values: list[LogValue] = []
    issues: list[Issue] = []
    number_pattern = re.compile(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(V|mV)?$")
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split(delimiter)
        if len(parts) < 4:
            issues.append(
                Issue(
                    "short_log_line",
                    "Fewer than four fields; line ignored.",
                    source,
                    row=line_number,
                )
            )
            continue
        if parts[2].strip() != metric:
            continue
        token = parts[3].strip().replace("\u2212", "-")
        match = number_pattern.fullmatch(token)
        if match is None:
            issues.append(
                Issue(
                    "invalid_log_value",
                    "Target metric has an invalid/missing numeric voltage.",
                    source,
                    severity="error",
                    row=line_number,
                )
            )
            continue
        value = float(match.group(1))
        if not math.isfinite(value):
            issues.append(
                Issue(
                    "invalid_log_value",
                    "Target metric is non-finite.",
                    source,
                    severity="error",
                    row=line_number,
                )
            )
            continue
        if match.group(2) == "mV":
            value /= 1000
        values.append(LogValue(source, line_number, len(values) + 1, metric, value, "V"))
    if not values:
        issues.append(
            Issue(
                "no_log_values",
                "No usable values for the requested metric.",
                source,
                severity="error",
            )
        )
    return LogResult(source, used_encoding, tuple(values), tuple(issues))


def wide_log_rows(results: tuple[LogResult, ...], headers: tuple[str, ...]) -> list[list[object]]:
    """Only map positions to explicit headers if every retained log has that length."""
    if (
        not headers
        or any(not isinstance(header, str) or not header.strip() for header in headers)
        or len(set(headers)) != len(headers)
    ):
        raise ParseError("Wide export needs unique, non-empty column names.")
    rows: list[list[object]] = []
    for result in results:
        if result.skipped:
            continue
        if any(issue.severity == "error" for issue in result.issues):
            raise ParseError(
                f"Cannot create positional wide output from a log with rejected values: {result.source}"
            )
        if len(result.values) != len(headers):
            raise ParseError(
                f"{result.source}: found {len(result.values)} values for {len(headers)} headers; refusing misalignment."
            )
        rows.append([result.source, *(value.value for value in result.values)])
    return rows
