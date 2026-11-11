"""Descriptive regulation statistics and matched-load interpolation.

Regulation uses the arithmetic mean of the evaluated output voltages. The span
is not a datasheet pass/fail criterion. Replicates and duplicate load points are
never silently averaged, and interpolation never extrapolates.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterable
from math import isclose, isfinite
from statistics import mean
from typing import Any

from powerbench.models import GROUP_FIELDS, GroupField, Measurement, Run


def _voltage_statistics(values: Iterable[float]) -> dict[str, float]:
    voltages = tuple(values)
    average = mean(voltages)
    low, high = min(voltages), max(voltages)
    return {
        "mean": average,
        "min": low,
        "max": high,
        "positive_pct": (high - average) / average * 100,
        "negative_pct": (low - average) / average * 100,
        "span_pct": (high - low) / average * 100,
    }


def summarize_run(run: Run) -> dict[str, Any]:
    """Keep reported zero efficiency; exclude missing and out-of-range peaks."""
    candidates = [
        (m.efficiency, m.load_a, m.point, m)
        for m in run.measurements
        if m.efficiency is not None and 0 <= m.efficiency <= 1
    ]
    peak = min(candidates, key=lambda item: (-item[0], item[1], item[2]), default=None)
    stats = _voltage_statistics(point.vout_v for point in run.measurements)
    return {
        "source": run.source,
        "run_id": run.run_id,
        "sha256": run.sha256,
        "conditions": run.conditions.as_dict(),
        "points": len(run.measurements),
        "peak_efficiency_pct": None if peak is None else peak[0] * 100,
        "peak_load_a": None if peak is None else peak[1],
        "load_min_a": min(point.load_a for point in run.measurements),
        "load_max_a": max(point.load_a for point in run.measurements),
        "vout_mean_v": stats["mean"],
        "vout_min_v": stats["min"],
        "vout_max_v": stats["max"],
        "load_regulation_positive_pct": stats["positive_pct"],
        "load_regulation_negative_pct": stats["negative_pct"],
        "load_regulation_span_pct": stats["span_pct"],
    }


def group_runs(runs: Iterable[Run], varying: GroupField = "vin_v") -> list[list[Run]]:
    """Hold all other nominal conditions constant; keep singletons and repeats."""
    if varying not in GROUP_FIELDS:
        raise ValueError(f"Unsupported varying field: {varying}; expected one of {GROUP_FIELDS}.")
    fixed = tuple(name for name in GROUP_FIELDS if name != varying)
    groups: dict[tuple[str | float, ...], list[Run]] = {}
    for run in runs:
        key = tuple(getattr(run.conditions, name) for name in fixed)
        groups.setdefault(key, []).append(run)

    def order(run: Run) -> tuple[Any, ...]:
        return (
            getattr(run.conditions, varying),
            run.conditions.timestamp or "",
            run.source,
            run.sha256,
            tuple((point.load_a, point.vout_v, point.point) for point in run.measurements),
        )

    return [sorted(groups[key], key=order) for key in sorted(groups)]


def _validate_tolerance(tolerance_a: float) -> None:
    if not isfinite(tolerance_a) or tolerance_a < 0:
        raise ValueError("Load tolerance must be finite and nonnegative.")


def _sorted_measurements(run: Run, tolerance_a: float) -> tuple[Measurement, ...]:
    points = tuple(sorted(run.measurements, key=lambda point: point.load_a))
    for first, second in zip(points, points[1:], strict=False):
        if isclose(first.load_a, second.load_a, rel_tol=0, abs_tol=tolerance_a):
            raise ValueError(
                f"{run.run_id}: duplicate or near-duplicate loads {first.load_a:g} A and "
                f"{second.load_a:g} A (tolerance {tolerance_a:g} A); interpolation is ambiguous."
            )
    return points


def _interpolate(points: tuple[Measurement, ...], load_a: float) -> tuple[float, bool]:
    if not isfinite(load_a):
        raise ValueError("Target load must be finite.")
    if load_a < points[0].load_a or load_a > points[-1].load_a:
        raise ValueError(
            f"Target {load_a:g} A outside measured range "
            f"[{points[0].load_a:g}, {points[-1].load_a:g}] A; extrapolation is prohibited."
        )
    index = bisect_left(points, load_a, key=lambda point: point.load_a)
    if points[index].load_a == load_a:
        return points[index].vout_v, False
    left, right = points[index - 1], points[index]
    weight = (load_a - left.load_a) / (right.load_a - left.load_a)
    return left.vout_v * (1 - weight) + right.vout_v * weight, True


def interpolate_vout(run: Run, load_a: float, *, tolerance_a: float = 1e-9) -> float:
    """Interpolate actual loads, rejecting duplicate points and out-of-range targets."""
    _validate_tolerance(tolerance_a)
    value, _ = _interpolate(_sorted_measurements(run, tolerance_a), load_a)
    return value


def line_regulation(
    runs: Iterable[Run],
    targets_a: tuple[float, ...] | None = None,
    *,
    tolerance_a: float = 1e-9,
) -> list[dict[str, Any]]:
    """Compare Vin sweeps only inside the intersection of their measured loads.

    Default targets are the intersection's lower/middle/upper values, NOT rated
    zero/half/full load. Explicit targets outside it get an out_of_range status.
    The interpolated flag says at least one curve required linear interpolation.
    """
    _validate_tolerance(tolerance_a)
    if targets_a is not None and any(not isfinite(target) for target in targets_a):
        raise ValueError("All target loads must be finite.")
    results: list[dict[str, Any]] = []
    for group in group_runs(runs, varying="vin_v"):
        conditions = {
            name: getattr(group[0].conditions, name) for name in GROUP_FIELDS if name != "vin_v"
        }
        base = {"conditions": conditions, "sources": [run.source for run in group]}
        vin_values = [run.conditions.vin_v for run in group]
        if len(set(vin_values)) != len(vin_values):
            results.append(
                {
                    **base,
                    "status": "ambiguous_replicates",
                    "message": "Repeated runs at the same Vin; select measurements explicitly. No automatic averaging.",
                }
            )
            continue
        if len(vin_values) < 2:
            results.append(
                {
                    **base,
                    "status": "insufficient_vin",
                    "message": "At least two distinct nominal input voltages are required.",
                }
            )
            continue
        try:
            curves = [_sorted_measurements(run, tolerance_a) for run in group]
        except ValueError as exc:
            results.append({**base, "status": "ambiguous_loads", "message": str(exc)})
            continue
        lower = max(curve[0].load_a for curve in curves)
        upper = min(curve[-1].load_a for curve in curves)
        if lower > upper:
            results.append(
                {
                    **base,
                    "status": "no_overlap",
                    "message": "No common measured load range; extrapolation is prohibited.",
                }
            )
            continue
        # Exact target deduplication cannot swallow a valid boundary next to an invalid target.
        targets = sorted(
            set((lower, lower + (upper - lower) / 2, upper) if targets_a is None else targets_a)
        )
        for target in targets:
            if target < lower or target > upper:
                results.append(
                    {
                        **base,
                        "status": "out_of_range",
                        "load_a": target,
                        "load_min_a": lower,
                        "load_max_a": upper,
                        "message": "Target load lies outside the common range; extrapolation is prohibited.",
                    }
                )
                continue
            interpolated = [_interpolate(curve, target) for curve in curves]
            voltages = [value for value, _ in interpolated]
            stats = _voltage_statistics(voltages)
            results.append(
                {
                    **base,
                    "status": "ok",
                    "load_a": target,
                    "vin_values_v": vin_values,
                    "vout_values_v": voltages,
                    "positive_pct": stats["positive_pct"],
                    "negative_pct": stats["negative_pct"],
                    "span_pct": stats["span_pct"],
                    "interpolated": any(was_interpolated for _, was_interpolated in interpolated),
                }
            )
    return results
