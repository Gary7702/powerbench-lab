"""Batch isolation, deterministic discovery, and explicit configuration contracts."""

import json
from dataclasses import replace

import pytest

from powerbench.batch import discover_inputs, process_batch
from powerbench.config import load_settings
from powerbench.demo import write_demo_inputs
from powerbench.models import Measurement, ParseError, PowerBenchError, Settings


def test_discovery_is_sorted_unique_and_recursion_is_opt_in(tmp_path):
    inputs = write_demo_inputs(tmp_path / "inputs")
    nested = tmp_path / "inputs" / "nested"
    nested.mkdir()
    (nested / "additional.json").write_bytes(inputs[0].read_bytes())
    assert len(discover_inputs([tmp_path / "inputs", inputs[0]])) == 8
    assert len(discover_inputs([tmp_path / "inputs"], recursive=True)) == 9
    assert discover_inputs(reversed(inputs)) == discover_inputs(inputs)
    with pytest.raises(ParseError):
        discover_inputs([tmp_path / "missing"])
    wrong = tmp_path / "wrong.txt"
    wrong.write_text("unused", encoding="utf-8")
    with pytest.raises(ParseError, match="extension"):
        discover_inputs([wrong])


def test_bad_json_does_not_stop_valid_files(tmp_path):
    paths = write_demo_inputs(tmp_path / "inputs")
    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")
    batch = process_batch((paths[0], bad, paths[1]))
    assert len(batch.runs) == 2
    assert batch.failed == 1
    assert batch.discovered == 3
    assert batch.has_errors


def test_duplicate_content_and_conditions_are_deduplicated(tmp_path):
    paths = write_demo_inputs(tmp_path / "inputs")
    copy = tmp_path / "duplicate.json"
    copy.write_bytes(paths[0].read_bytes())
    batch = process_batch((paths[0], copy))
    assert len(batch.runs) == 1
    assert batch.skipped == 1
    assert batch.issues[0].code == "duplicate_input"


def test_same_basename_is_disambiguated_without_absolute_paths(tmp_path):
    a = write_demo_inputs(tmp_path / "a")
    b = write_demo_inputs(tmp_path / "b")
    document = json.loads(b[0].read_text(encoding="utf-8"))
    document["conditions"]["sample_id"] = "OTHER"
    b[0].write_text(json.dumps(document), encoding="utf-8")
    batch = process_batch((a[0], b[0]))
    assert len(batch.runs) == 2
    assert batch.runs[0].source != batch.runs[1].source
    assert all(str(tmp_path) not in run.source for run in batch.runs)


def test_config_defaults_and_override(tmp_path):
    assert load_settings() == Settings()
    path = tmp_path / "settings.toml"
    path.write_text(
        'efficiency_unit = "percent"\npower_abs_tolerance_w = 0.02\n[mode_labels]\n"2" = "Verified vendor name"\n',
        encoding="utf-8",
    )
    settings = load_settings(path)
    assert settings.efficiency_unit == "percent"
    assert settings.mode_labels["2"] == "Verified vendor name"


@pytest.mark.parametrize(
    "text",
    [
        "typo = 1",
        'efficiency_unit = "auto"',
        "power_rel_tolerance = -1",
        'power_rel_tolerance = "text"',
        "mode_labels = 1",
        "broken = [",
    ],
)
def test_invalid_config_rejected(tmp_path, text):
    path = tmp_path / "settings.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(PowerBenchError):
        load_settings(path)


@pytest.mark.parametrize(
    "changes",
    [
        {"sample_id": 1},
        {"sample_id": ""},
        {"channel": 1},
        {"channel": "0"},
        {"vin_v": True},
        {"vin_v": "10"},
        {"vin_v": float("inf")},
        {"vout_v": 0},
        {"timestamp": 99},
    ],
)
def test_conditions_validate_external_json_types(conditions, changes):
    with pytest.raises(ValueError):
        replace(conditions, **changes)


def test_measurement_rejects_invalid_units_and_nonfinite():
    measurement = Measurement(1, 1, 5, 10, 0.625, 5, 6.25, 1.25, 0.8)
    for change in (
        {"point": 1.5},
        {"page": False},
        {"table": 0},
        {"load_a": -1},
        {"vout_v": 0},
        {"iin_a": "1"},
        {"efficiency": float("inf")},
    ):
        with pytest.raises(ValueError):
            replace(measurement, **change)
