"""Immutable domain objects shared by parsers, analysis, and presentation.

Currents are amperes, voltages volts, powers watts; efficiency is a fraction.
Do not infer units from magnitudes. Percent is only a presentation convention.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isfinite
from typing import Any, Literal

Severity = Literal["warning", "error"]
GroupField = Literal["sample_id", "channel", "vin_v", "vout_v", "frequency_khz", "mode"]
GROUP_FIELDS: tuple[GroupField, ...] = (
    "sample_id",
    "channel",
    "vin_v",
    "vout_v",
    "frequency_khz",
    "mode",
)


class PowerBenchError(Exception):
    """An actionable input or analysis error, safe to show on the command line."""


class ParseError(PowerBenchError):
    """An input cannot be parsed without inventing or discarding information."""


@dataclass(frozen=True)
class Conditions:
    sample_id: str
    channel: str
    vin_v: float
    vout_v: float
    frequency_khz: float
    mode: str
    timestamp: str | None = None

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value.strip()
            for value in (self.sample_id, self.channel, self.mode)
        ):
            raise ValueError("Sample, channel, and mode must be non-empty strings.")
        if self.timestamp is not None and not isinstance(self.timestamp, str):
            raise ValueError("Timestamp must be a string or null.")
        if self.channel != "S" and (not self.channel.isdigit() or int(self.channel) < 1):
            raise ValueError("Channel must be a positive integer or S (merged output).")
        for name in ("vin_v", "vout_v", "frequency_khz"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a finite positive number.")

    @property
    def identity(self) -> tuple[str | float, ...]:
        """Nominal conditions only; timestamps identify repeated measurements separately."""
        return tuple(getattr(self, name) for name in GROUP_FIELDS)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    source: str
    severity: Severity = "warning"
    page: int | None = None
    row: int | None = None
    field: str | None = None
    table: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Measurement:
    point: int
    load_a: float
    vout_v: float
    vin_v: float
    iin_a: float
    pout_w: float
    pin_w: float
    loss_w: float
    efficiency: float | None
    page: int = 1
    row: int = 1
    flags: tuple[str, ...] = ()
    table: int = 1

    def __post_init__(self) -> None:
        for value in (self.point, self.page, self.row, self.table):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(
                    "Point, page, table, and row numbers are one-based positive integers."
                )
        for name in ("load_a", "vout_v", "vin_v", "iin_a", "pout_w", "pin_w", "loss_w"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value):
                raise ValueError(f"{name} must be a finite number.")
        if self.load_a < 0 or self.vout_v <= 0 or self.vin_v <= 0:
            raise ValueError("Load must be nonnegative; measured voltages must be positive.")
        if self.efficiency is not None and (
            isinstance(self.efficiency, bool)
            or not isinstance(self.efficiency, int | float)
            or not isfinite(self.efficiency)
        ):
            raise ValueError("Non-finite efficiency must be represented as None, not zero.")

    @property
    def efficiency_pct(self) -> float | None:
        return None if self.efficiency is None else self.efficiency * 100

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "flags": list(self.flags)}


@dataclass(frozen=True)
class Run:
    conditions: Conditions
    measurements: tuple[Measurement, ...]
    source: str
    sha256: str
    issues: tuple[Issue, ...] = ()
    synthetic: bool = False

    def __post_init__(self) -> None:
        if not self.measurements:
            raise ValueError("A run must contain at least one measurement.")
        if not self.source:
            raise ValueError("Source identifier must be non-empty.")

    @property
    def run_id(self) -> str:
        return f"{self.source}:{self.sha256[:12]}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "source": self.source,
            "sha256": self.sha256,
            "synthetic": self.synthetic,
            "conditions": self.conditions.as_dict(),
            "measurements": [m.as_dict() for m in self.measurements],
            "issues": [issue.as_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class Batch:
    runs: tuple[Run, ...] = ()
    issues: tuple[Issue, ...] = ()
    discovered: int = 0
    failed: int = 0
    skipped: int = 0

    @property
    def all_issues(self) -> tuple[Issue, ...]:
        return self.issues + tuple(issue for run in self.runs for issue in run.issues)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.all_issues)

    @property
    def measurement_count(self) -> int:
        return sum(len(run.measurements) for run in self.runs)


@dataclass(frozen=True)
class Settings:
    """Small, typed configuration; defaults reflect the documented ATE contract."""

    efficiency_unit: Literal["fraction", "percent"] = "fraction"
    efficiency_tolerance: float = 0.015
    power_abs_tolerance_w: float = 0.015
    power_rel_tolerance: float = 0.02
    duplicate_load_tolerance_a: float = 1e-9
    mode_labels: dict[str, str] = field(
        default_factory=lambda: {"1": "CCM", "2": "Mode 2", "3": "Burst"}
    )

    def __post_init__(self) -> None:
        if self.efficiency_unit not in ("fraction", "percent"):
            raise ValueError("efficiency_unit must be fraction or percent.")
        for name in (
            "efficiency_tolerance",
            "power_abs_tolerance_w",
            "power_rel_tolerance",
            "duplicate_load_tolerance_a",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not isfinite(value)
                or value < 0
            ):
                raise ValueError(f"{name} must be finite and nonnegative.")
        if not isinstance(self.mode_labels, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and v for k, v in self.mode_labels.items()
        ):
            raise ValueError("mode_labels must map strings to non-empty strings.")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
