"""Regression tests for metrics, condition isolation, and no-extrapolation rules."""

from dataclasses import replace
from math import inf, nan
from typing import Any

import pytest

from powerbench.analysis import (
    group_runs,
    interpolate_vout,
    line_regulation,
    summarize_run,
)
from powerbench.models import GROUP_FIELDS, Conditions, Measurement, Run


def make_run(
    points: tuple[tuple[float, float], ...] = ((0.0, 5.0), (10.0, 5.0)),
    *,
    efficiencies: tuple[float | None, ...] | None = None,
    source: str = "unit-test.csv",
    **condition_changes: Any,
) -> Run:
    conditions = replace(
        Conditions("sample-a", "1", 12.0, 5.0, 500.0, "unknown-mode"),
        **condition_changes,
    )
    measurements = tuple(
        Measurement(
            point=index + 1,
            load_a=load,
            vout_v=voltage,
            vin_v=conditions.vin_v,
            iin_a=1.0,
            pout_w=load * voltage,
            pin_w=load * voltage + 1.0,
            loss_w=1.0,
            efficiency=0.8 if efficiencies is None else efficiencies[index],
        )
        for index, (load, voltage) in enumerate(points)
    )
    return Run(conditions, measurements, source, "a" * 64)


def test_summary_uses_full_statistics_and_provenance() -> None:
    run = make_run(
        ((9, 7), (0, 4), (2, 5)),
        efficiencies=(0.80, 0.95, 0.90),
        timestamp="2026-01-01T10:00:00",
    )
    result = summarize_run(run)
    assert result["source"] == run.source
    assert result["run_id"] == run.run_id
    assert result["sha256"] == run.sha256
    assert result["conditions"] == run.conditions.as_dict()
    assert result["points"] == 3
    assert result["peak_efficiency_pct"] == 95
    assert result["peak_load_a"] == 0
    assert result["load_min_a"] == 0
    assert result["load_max_a"] == 9
    assert result["vout_mean_v"] == pytest.approx(16 / 3)
    assert result["vout_min_v"] == 4
    assert result["vout_max_v"] == 7
    assert result["load_regulation_positive_pct"] == pytest.approx(31.25)
    assert result["load_regulation_negative_pct"] == pytest.approx(-25)
    assert result["load_regulation_span_pct"] == pytest.approx(56.25)
    assert "span_pct" not in result


@pytest.mark.parametrize(
    ("efficiencies", "peak_pct", "peak_load"),
    [
        ((None, -0.1, 1.1), None, None),
        ((None, 0.0, 1.1), 0.0, 1.0),
        ((0.0, 1.0, -0.1), 100.0, 1.0),
    ],
)
def test_summary_excludes_invalid_efficiency_but_keeps_zero(
    efficiencies: tuple[float | None, ...],
    peak_pct: float | None,
    peak_load: float | None,
) -> None:
    result = summarize_run(make_run(((0, 5), (1, 5), (2, 5)), efficiencies=efficiencies))
    assert result["peak_efficiency_pct"] == peak_pct
    assert result["peak_load_a"] == peak_load


def test_peak_ties_choose_lowest_actual_load() -> None:
    run = make_run(((10, 5), (0, 5), (1, 5)), efficiencies=(0.9, 0.9, 0.8))
    assert summarize_run(run)["peak_load_a"] == 0


def test_single_point_summary_has_zero_span() -> None:
    result = summarize_run(make_run(((3, 5),)))
    assert result["points"] == 1
    assert result["load_min_a"] == result["load_max_a"] == 3
    assert result["load_regulation_positive_pct"] == 0
    assert result["load_regulation_negative_pct"] == 0
    assert result["load_regulation_span_pct"] == 0


def test_summary_keeps_duplicate_loads_as_original_measurements() -> None:
    result = summarize_run(make_run(((1, 4), (1, 6))))
    assert result["points"] == 2
    assert result["vout_mean_v"] == 5
    assert result["load_regulation_span_pct"] == 40


def test_empty_grouping_and_line_regulation() -> None:
    assert group_runs([]) == []
    assert line_regulation([]) == []


def test_grouping_preserves_single_last_and_replicate_runs() -> None:
    low = make_run(vin_v=6, source="low.csv")
    high = make_run(vin_v=24, source="high.csv")
    replicate = make_run(vin_v=6, source="replicate.csv")
    last = make_run(channel="2", source="last.csv")
    assert group_runs([last]) == [[last]]
    groups = group_runs([high, replicate, last, low])
    assert groups == [[low, replicate, high], [last]]
    assert sum(map(len, groups)) == 4


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sample_id", "sample-b"),
        ("channel", "S"),
        ("vout_v", 3.3),
        ("frequency_khz", 800.0),
        ("mode", "another-unknown-mode"),
    ],
)
def test_grouping_isolates_every_fixed_nominal_condition(field: str, value: Any) -> None:
    first = make_run(vin_v=6)
    second = make_run(vin_v=12, **{field: value})
    groups = group_runs([first, second])
    assert len(groups) == 2
    assert all(len(group) == 1 for group in groups)


@pytest.mark.parametrize("varying", GROUP_FIELDS)
def test_grouping_supports_each_declared_varying_field(varying: str) -> None:
    alternatives = {
        "sample_id": "sample-b",
        "channel": "2",
        "vin_v": 24.0,
        "vout_v": 3.3,
        "frequency_khz": 800.0,
        "mode": "other-mode",
    }
    first = make_run()
    second = make_run(**{varying: alternatives[varying]})
    groups = group_runs([first, second], varying=varying)
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_grouping_ignores_timestamp_and_sorts_reproducibly() -> None:
    first = make_run(timestamp="2026-01-01T00:00:00", source="first.csv")
    second = make_run(timestamp="2026-01-02T00:00:00", source="second.csv")
    higher = make_run(vin_v=24, source="higher.csv")
    assert group_runs([second, higher, first]) == group_runs([higher, first, second])
    assert group_runs([second, higher, first]) == [[first, second, higher]]


def test_unknown_grouping_field_is_rejected_even_without_runs() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        group_runs([], varying="timestamp")


def test_interpolation_sorts_actual_nonuniform_loads_without_mutating_run() -> None:
    run = make_run(((10, 7), (0, 5), (1, 5.1)))
    original = run.measurements
    assert interpolate_vout(run, 5) == pytest.approx(5.1 + (5 - 1) / (10 - 1) * 1.9)
    assert run.measurements is original
    assert [point.load_a for point in run.measurements] == [10, 0, 1]


@pytest.mark.parametrize(("load", "expected"), [(0, 5), (1, 5.1), (10, 7)])
def test_interpolation_returns_exact_sample_values(load: float, expected: float) -> None:
    assert interpolate_vout(make_run(((10, 7), (0, 5), (1, 5.1))), load) == expected


@pytest.mark.parametrize("load", [-1, -1e-12, 10 + 1e-12, 11])
def test_interpolation_never_extrapolates_even_near_boundary(load: float) -> None:
    with pytest.raises(ValueError, match="extrapolation is prohibited"):
        interpolate_vout(make_run(), load)


@pytest.mark.parametrize("load", [nan, inf, -inf])
def test_interpolation_rejects_nonfinite_target(load: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        interpolate_vout(make_run(), load)


@pytest.mark.parametrize("second_load", [0.0, 1e-10, 1e-9])
def test_interpolation_rejects_duplicate_and_near_duplicate_loads(second_load: float) -> None:
    run = make_run(((0, 5), (second_load, 5.1), (10, 5.2)))
    with pytest.raises(ValueError, match="duplicate"):
        interpolate_vout(run, 5)
    with pytest.raises(ValueError, match="duplicate"):
        interpolate_vout(run, 0)


def test_load_duplicate_tolerance_is_absolute_not_relative() -> None:
    run = make_run(((1e9, 5), (1e9 + 1, 7)))
    assert interpolate_vout(run, 1e9 + 0.5) == pytest.approx(6)


def test_distinct_small_loads_above_tolerance_are_valid() -> None:
    run = make_run(((0, 5), (2e-9, 7)))
    assert interpolate_vout(run, 1e-9) == pytest.approx(6)


@pytest.mark.parametrize("tolerance", [-1, inf, nan])
def test_invalid_interpolation_tolerance_is_rejected(tolerance: float) -> None:
    with pytest.raises(ValueError, match="tolerance"):
        interpolate_vout(make_run(), 5, tolerance_a=tolerance)
    with pytest.raises(ValueError, match="tolerance"):
        line_regulation([], tolerance_a=tolerance)


def test_custom_duplicate_tolerance_is_used_by_analysis() -> None:
    run = make_run(((0, 5), (0.001, 5.1), (10, 5.2)), vin_v=6)
    with pytest.raises(ValueError, match="duplicate"):
        interpolate_vout(run, 5, tolerance_a=0.01)
    result = line_regulation([run, make_run(vin_v=12)], tolerance_a=0.01)
    assert result[0]["status"] == "ambiguous_loads"


def test_single_point_curve_accepts_only_its_exact_load() -> None:
    run = make_run(((3, 5.5),))
    assert interpolate_vout(run, 3) == 5.5
    with pytest.raises(ValueError, match="extrapolation is prohibited"):
        interpolate_vout(run, 3 + 1e-12)


def test_line_regulation_uses_mean_denominator_and_actual_midpoint() -> None:
    low = make_run(((10, 6), (0, 4), (1, 4.2)), vin_v=6, source="low.csv")
    high = make_run(((0, 5), (10, 7)), vin_v=12, source="high.csv")
    results = line_regulation([high, low])
    assert [point["load_a"] for point in results] == [0, 5, 10]
    assert [point["interpolated"] for point in results] == [False, True, False]
    midpoint = results[1]
    assert midpoint["status"] == "ok"
    assert midpoint["vin_values_v"] == [6, 12]
    assert midpoint["vout_values_v"] == pytest.approx([5, 6])
    assert midpoint["positive_pct"] == pytest.approx(0.5 / 5.5 * 100)
    assert midpoint["negative_pct"] == pytest.approx(-0.5 / 5.5 * 100)
    assert midpoint["span_pct"] == pytest.approx(1 / 5.5 * 100)
    assert midpoint["sources"] == ["low.csv", "high.csv"]
    assert midpoint["conditions"]["mode"] == "unknown-mode"
    assert "vin_v" not in midpoint["conditions"]
    assert "timestamp" not in midpoint["conditions"]


def test_line_regulation_uses_all_vin_curves_not_only_extremes() -> None:
    curves = [
        make_run(((0, 4), (10, 4)), vin_v=6, source="a.csv"),
        make_run(((0, 7), (10, 7)), vin_v=12, source="b.csv"),
        make_run(((0, 5), (10, 5)), vin_v=24, source="c.csv"),
    ]
    point = line_regulation(curves, targets_a=(5,))[0]
    assert point["vout_values_v"] == [4, 7, 5]
    assert point["positive_pct"] == pytest.approx(31.25)
    assert point["negative_pct"] == pytest.approx(-25)
    assert point["span_pct"] == pytest.approx(56.25)


def test_line_regulation_default_targets_follow_common_range() -> None:
    low = make_run(((0, 5), (10, 6)), vin_v=6)
    high = make_run(((2, 5), (8, 6)), vin_v=12)
    third = make_run(((3, 5), (12, 6)), vin_v=24)
    points = line_regulation([third, high, low])
    assert [point["load_a"] for point in points] == [3, 5.5, 8]
    assert all(point["status"] == "ok" for point in points)


def test_touching_ranges_produce_one_deduplicated_target() -> None:
    low = make_run(((0, 5), (5, 6)), vin_v=6)
    high = make_run(((5, 6), (10, 7)), vin_v=12)
    points = line_regulation([low, high])
    assert len(points) == 1
    assert points[0]["load_a"] == 5
    assert points[0]["span_pct"] == 0
    assert points[0]["interpolated"] is False


def test_single_point_curve_can_share_one_target_with_another_curve() -> None:
    points = line_regulation(
        [
            make_run(((3, 5),), vin_v=6),
            make_run(((0, 4), (6, 6)), vin_v=12),
        ]
    )
    assert len(points) == 1
    assert points[0]["load_a"] == 3
    assert points[0]["vout_values_v"] == [5, 5]
    assert points[0]["interpolated"] is True


def test_nonoverlapping_ranges_report_status_without_values() -> None:
    points = line_regulation(
        [
            make_run(((0, 5), (2, 6)), vin_v=6),
            make_run(((3, 5), (10, 6)), vin_v=12),
        ]
    )
    assert len(points) == 1
    assert points[0]["status"] == "no_overlap"
    assert points[0]["message"]
    assert "vout_values_v" not in points[0]


def test_explicit_targets_are_sorted_deduplicated_and_report_out_of_range() -> None:
    curves = [
        make_run(((0, 5), (10, 6)), vin_v=6),
        make_run(((2, 5), (8, 6)), vin_v=12),
    ]
    points = line_regulation(curves, targets_a=(9, 5, 2, 5, 1, 8))
    assert [point["load_a"] for point in points] == [1, 2, 5, 8, 9]
    assert [point["status"] for point in points] == [
        "out_of_range",
        "ok",
        "ok",
        "ok",
        "out_of_range",
    ]
    assert points[0]["load_min_a"] == 2
    assert points[0]["load_max_a"] == 8
    assert "vout_values_v" not in points[0]
    assert line_regulation(curves, targets_a=()) == []


def test_near_outside_target_does_not_swallow_exact_valid_boundary() -> None:
    curves = [make_run(vin_v=6), make_run(vin_v=12)]
    points = line_regulation(curves, targets_a=(-1e-12, 0, 10, 10 + 1e-12))
    assert [point["status"] for point in points] == ["out_of_range", "ok", "ok", "out_of_range"]


@pytest.mark.parametrize("target", [nan, inf, -inf])
def test_line_regulation_rejects_nonfinite_explicit_targets(target: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        line_regulation([make_run(vin_v=6), make_run(vin_v=12)], targets_a=(target,))


def test_replicates_are_ambiguous_even_when_measurements_are_identical() -> None:
    first = make_run(vin_v=6, source="a.csv", timestamp="2026-01-01")
    repeated = make_run(vin_v=6, source="b.csv", timestamp="2026-01-02")
    other = make_run(vin_v=12, source="c.csv")
    points = line_regulation([other, repeated, first])
    assert len(points) == 1
    assert points[0]["status"] == "ambiguous_replicates"
    assert points[0]["sources"] == ["a.csv", "b.csv", "c.csv"]
    assert points[0]["message"]
    assert "span_pct" not in points[0]


def test_only_replicates_are_not_silently_reduced_to_one_run() -> None:
    run = make_run()
    assert line_regulation([run, run])[0]["status"] == "ambiguous_replicates"


def test_single_run_reports_insufficient_distinct_vin() -> None:
    points = line_regulation([make_run()])
    assert len(points) == 1
    assert points[0]["status"] == "insufficient_vin"
    assert "span_pct" not in points[0]


@pytest.mark.parametrize("delta", [0, 1e-10, 1e-9])
def test_line_regulation_reports_ambiguous_loads(delta: float) -> None:
    points = line_regulation(
        [
            make_run(((0, 4), (delta, 5), (10, 6)), vin_v=6),
            make_run(vin_v=12),
        ]
    )
    assert len(points) == 1
    assert points[0]["status"] == "ambiguous_loads"
    assert points[0]["message"]
    assert "span_pct" not in points[0]


@pytest.mark.parametrize(("field", "different"), [("channel", "2"), ("mode", "unmapped-mode")])
def test_line_regulation_never_mixes_channels_or_modes(field: str, different: str) -> None:
    first = make_run(vin_v=6, source="a.csv")
    second = make_run(vin_v=12, source="b.csv", **{field: different})
    results = line_regulation([first, second])
    assert len(results) == 2
    assert all(point["status"] == "insufficient_vin" for point in results)


def test_failed_group_does_not_hide_later_valid_group() -> None:
    runs = [
        make_run(channel="1", vin_v=6, source="single.csv"),
        make_run(channel="2", vin_v=6, source="a.csv"),
        make_run(channel="2", vin_v=12, source="b.csv"),
    ]
    points = line_regulation(runs)
    assert points[0]["status"] == "insufficient_vin"
    assert len(points) == 4
    assert all(point["status"] == "ok" for point in points[1:])


def test_generator_inputs_and_result_order_are_reproducible() -> None:
    first = make_run(vin_v=6, source="a.csv")
    second = make_run(vin_v=12, source="b.csv")
    assert line_regulation(iter([second, first])) == line_regulation([first, second])
