"""End-to-end CLI and artifact safety checks using only synthetic fixtures."""

import csv
import hashlib
import json
from zipfile import ZipFile

import pytest

from powerbench.batch import process_batch
from powerbench.cli import main
from powerbench.demo import write_demo_inputs
from powerbench.exports import csv_safe, write_json, write_plots
from powerbench.models import Settings


def test_demo_json_csv_html_and_manifest(tmp_path, capsys):
    output = tmp_path / "demo"
    assert main(["demo", "-o", str(output), "--formats", "html,json,csv", "--legacy-wide"]) == 0
    payload = json.loads((output / "results.json").read_text(encoding="utf-8"))
    assert payload["counts"] == {
        "files": 8,
        "runs": 8,
        "measurements": 96,
        "failed_files": 0,
        "skipped_files": 0,
        "warnings": 9,
        "errors": 0,
    }
    assert payload["synthetic"]
    assert len(payload["line_regulation"]) == 12
    assert len(payload["runs"]) == 8
    assert "SYNTHETIC DEMONSTRATION DATA" in (output / "report.html").read_text(encoding="utf-8")
    with (output / "measurements.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 96
    assert rows[1]["efficiency_fraction"]
    assert rows[1]["table"] == "1"
    with (output / "curves-wide.csv").open(encoding="utf-8-sig") as stream:
        assert len(list(csv.reader(stream))) == 17
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["artifacts"]:
        path = output / entry["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    assert "8 runs, 96 points" in capsys.readouterr().out


def test_no_output_overwrites(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    original = output / "keep.txt"
    original.write_text("keep this content", encoding="utf-8")
    assert main(["demo", "-o", str(output), "--formats", "html"]) == 2
    assert original.read_text(encoding="utf-8") == "keep this content"
    assert sorted(p.name for p in output.iterdir()) == ["keep.txt"]


def test_analyze_partial_failure_returns_nonzero_and_diagnostics(tmp_path):
    paths = write_demo_inputs(tmp_path / "inputs")
    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")
    output = tmp_path / "output"
    assert main(["analyze", str(paths[0]), str(bad), "-o", str(output), "--formats", "json"]) == 1
    payload = json.loads((output / "results.json").read_text(encoding="utf-8"))
    assert payload["counts"]["runs"] == 1
    assert payload["counts"]["failed_files"] == 1
    assert any(i["severity"] == "error" for i in payload["issues"])


def test_validate_is_read_only_and_strict_mode_is_explicit(tmp_path, capsys):
    paths = write_demo_inputs(tmp_path / "inputs")
    before = sorted(str(p) for p in tmp_path.rglob("*"))
    assert main(["validate", str(paths[0]), "--json"]) == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["counts"]["runs"] == 1
    assert main(["validate", str(paths[0]), "--strict"]) == 1
    assert before == sorted(str(p) for p in tmp_path.rglob("*"))


def test_missing_and_empty_inputs_are_actionable(tmp_path, capsys):
    assert main(["validate", str(tmp_path / "missing")]) == 2
    assert "does not exist" in capsys.readouterr().err
    assert main(["validate", str(tmp_path)]) == 2
    assert "No supported input" in capsys.readouterr().err


@pytest.mark.parametrize(
    "args",
    [
        ["demo", "-o", "unused", "--formats", "pdf"],
        ["demo", "-o", "unused", "--loads", "nan"],
        ["demo", "-o", "unused", "--loads", "-1"],
        ["demo", "-o", "unused", "--loads", "text"],
    ],
)
def test_invalid_cli_options_exit_two(args):
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2


def test_version_and_help_do_not_run_pipeline(capsys):
    for args in (["--version"], ["--help"]):
        with pytest.raises(SystemExit) as exc:
            main(args)
        assert exc.value.code == 0
    assert "powerbench" in capsys.readouterr().out


def test_log_cli_wide_output_and_diagnostics(tmp_path):
    path = tmp_path / "example.log"
    path.write_text(
        "now......ch......读取输出电压......3.3\nnow......ch......读取输出电压......3.2\n",
        encoding="utf-8",
    )
    headers = tmp_path / "headers.json"
    headers.write_text('["first_v", "second_v"]', encoding="utf-8")
    output = tmp_path / "logs"
    assert main(["logs", str(path), "--headers", str(headers), "-o", str(output)]) == 0
    assert (output / "voltage-wide.csv").is_file()
    assert json.loads((output / "diagnostics.json").read_text(encoding="utf-8")) == []
    with (output / "voltage-readings.csv").open(encoding="utf-8-sig") as stream:
        assert len(list(csv.DictReader(stream))) == 2


def test_log_cli_missing_inputs_and_bad_headers(tmp_path):
    assert main(["logs", str(tmp_path / "missing"), "-o", str(tmp_path / "out")]) == 2
    assert main(["logs", str(tmp_path), "-o", str(tmp_path / "out")]) == 2
    path = tmp_path / "example.log"
    path.write_text("now......ch......读取输出电压......3.3", encoding="utf-8")
    headers = tmp_path / "headers.json"
    headers.write_text("{}", encoding="utf-8")
    assert main(["logs", str(path), "--headers", str(headers), "-o", str(tmp_path / "out")]) == 2


@pytest.mark.parametrize("text", ["=1+2", " +command", "-formula", "@SUM(A1)", "\t=1"])
def test_csv_formula_text_is_escaped(text):
    assert csv_safe(text) == "'" + text


def test_csv_negative_numbers_are_still_numeric():
    assert csv_safe(-0.1) == -0.1
    assert csv_safe("normal source") == "normal source"


def test_json_never_serializes_nan(tmp_path):
    with pytest.raises(ValueError):
        write_json(tmp_path / "result.json", {"value": float("nan")})


def test_xlsx_export_is_structured_and_never_evaluates_input_text(tmp_path):
    inputs = write_demo_inputs(tmp_path / "inputs")
    data = json.loads(inputs[0].read_text(encoding="utf-8"))
    data["conditions"]["sample_id"] = "=SUM(1,2)"
    inputs[0].write_text(json.dumps(data), encoding="utf-8")
    output = tmp_path / "xlsx"
    assert main(["analyze", str(inputs[0]), "-o", str(output), "--formats", "xlsx"]) == 0
    with ZipFile(output / "analysis.xlsx") as archive:
        workbook = archive.read("xl/workbook.xml").decode()
        for name in ("Measurements", "Summary", "Line Regulation", "Diagnostics", "Read Me"):
            assert name in workbook
        assert "xl/charts/chart1.xml" in archive.namelist()
        shared = archive.read("xl/sharedStrings.xml").decode()
        assert "=SUM(1,2)" in shared
        assert not any(
            "<f>" in archive.read(name).decode()
            for name in archive.namelist()
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )


def test_static_plots_include_last_and_singleton_curves(tmp_path):
    inputs = write_demo_inputs(tmp_path / "inputs")
    batch = process_batch(inputs[:1])
    paths = write_plots(
        tmp_path / "plots", batch.runs, log_x=True, varying="mode", settings=Settings()
    )
    assert len(paths) == 2
    svg = next(path for path in paths if path.suffix == ".svg").read_text(encoding="utf-8")
    assert "Efficiency" in svg
    assert "SYNTHETIC" in svg
    assert all(path.stat().st_size > 100 for path in paths)
