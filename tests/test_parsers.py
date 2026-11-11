"""Adapter, schema, unit, and data-integrity regression tests."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from powerbench.demo import demo_documents
from powerbench.models import ParseError, Settings
from powerbench.parsers import parse_filename, parse_pdf, parse_table_json, parse_tables, parse_text


@pytest.mark.parametrize(
    "filename",
    [
        "__DEMO_1_10_5_500_1_EFFI_2026-01-01 12-00-00.pdf",
        "DEMO_1_10_5_500_1_2026-01-01 12-00-00.pdf",
        "DEMO_1_10_5_500_1.pdf",
        "C:\\folder_with_underscores\\__DEMO_1_10_5_500_1.pdf",
    ],
)
def test_filename_is_basename_not_path_underscore_counts(filename):
    conditions = parse_filename(filename)
    assert conditions.identity == ("DEMO", "1", 10.0, 5.0, 500.0, "1")


def test_filename_preserves_merged_channel_and_unknown_mode():
    c = parse_filename("__ABC_s_10.5_2.75_850.5_unknown.pdf")
    assert c.channel == "S"
    assert c.mode == "unknown"
    assert c.frequency_khz == 850.5


@pytest.mark.parametrize(
    "name",
    [
        "nonsense.pdf",
        "S_0_10_5_100_1.pdf",
        "S_1_0_5_100_1.pdf",
        "S_1_10_0_100_1.pdf",
        "S_1_10_5_0_1.pdf",
    ],
)
def test_bad_filenames_have_actionable_errors(name):
    with pytest.raises(ParseError):
        parse_filename(name)


def test_header_lookup_and_reported_zero_are_preserved(conditions, table):
    rows = [["Synthetic report"], ["Synthetic sample"], *table]
    run = parse_tables([(1, rows)], conditions, source="safe-source")
    assert len(run.measurements) == 3
    assert run.measurements[0].efficiency == 0
    assert run.measurements[0].row == 4
    assert run.measurements[1].efficiency_pct == 80
    assert run.measurements[1].table == 1
    assert len(run.sha256) == 64
    assert {i.code for i in run.issues} == {"zero_load", "nonpositive_input_power"}


def test_column_reordering_with_zero_and_null_first_column(conditions, table):
    indices = [8, 0, 2, 1, 3, 4, 5, 6, 7]
    reordered = [[row[i] for i in indices] for row in table]
    reordered[2][0] = None
    run = parse_tables([(1, reordered)], conditions, source="reordered")
    assert len(run.measurements) == 3
    assert run.measurements[0].efficiency == 0
    assert run.measurements[1].efficiency is None
    assert run.measurements[1].load_a == 1


@pytest.mark.parametrize("value", ["inf", "-Infinity", "NaN", "N/A", "--", "", None])
def test_invalid_efficiency_is_null_not_zero(conditions, table, value):
    table[2][8] = value
    run = parse_tables([(1, table)], conditions, source="invalid-efficiency")
    assert run.measurements[1].efficiency is None
    issue = next(i for i in run.issues if i.code == "undefined_efficiency")
    assert (issue.page, issue.table, issue.row, issue.field) == (1, 1, 3, "efficiency")


@pytest.mark.parametrize("bad", ["nan", "inf", "text", "", None])
def test_bad_required_numeric_value_rejects_row_with_error(conditions, table, bad):
    table[2][1] = bad
    run = parse_tables([(1, table)], conditions, source="bad-current")
    assert len(run.measurements) == 2
    assert any(i.code == "malformed_row" and i.severity == "error" for i in run.issues)


def test_truncated_numbered_row_is_not_silently_discarded(conditions, table):
    run = parse_tables([(1, [*table, [4]])], conditions, source="truncated")
    assert any(i.code == "malformed_row" and i.row == 5 for i in run.issues)


def test_noninteger_point_is_rejected(conditions, table):
    table[2][0] = 2.5
    run = parse_tables([(1, table)], conditions, source="bad-point")
    assert len(run.measurements) == 2
    assert any(i.severity == "error" for i in run.issues)


def test_header_on_multiple_pages_and_headerless_continuation(conditions, table):
    run = parse_tables(
        [(1, table[:2]), (2, [table[0], table[2]]), (3, [table[3]])], conditions, source="pages"
    )
    assert [m.page for m in run.measurements] == [1, 2, 3]
    assert [m.row for m in run.measurements] == [2, 2, 1]


def test_multiple_tables_have_unambiguous_provenance(conditions, table):
    run = parse_tables([(1, table[:2]), (1, [table[0], table[2]])], conditions, source="tables")
    assert [m.table for m in run.measurements] == [1, 2]


def test_unknown_or_duplicate_header_is_not_guessed(conditions, table):
    table[0][1] = "Load (mA)"
    with pytest.raises(ParseError, match="header"):
        parse_tables([(1, table)], conditions, source="wrong-unit")
    table[0][1] = "Vi"
    with pytest.raises(ParseError):
        parse_tables([(1, table)], conditions, source="duplicate-column")


@pytest.mark.parametrize("header", ["Io (V)", "Io [W]", "Io (mA)"])
def test_current_header_cannot_claim_the_wrong_physical_unit(conditions, table, header):
    table[0][1] = header
    with pytest.raises(ParseError):
        parse_tables([(1, table)], conditions, source="wrong-physical-unit")


def test_text_provenance_counts_blank_lines(conditions):
    run = parse_text(
        "\nNo. Io Vo Vi Ii Po Pi Ploss Effi\n\n1 1 5 10 0.625 5 6.25 1.25 0.8",
        conditions,
        source="blank-lines",
    )
    assert run.measurements[0].row == 4


def test_percent_unit_is_explicit_and_header_conflicts_fail(conditions, table):
    table[0][8] = "Efficiency (%)"
    for row in table[1:]:
        row[8] *= 100
    with pytest.raises(ParseError, match="percent"):
        parse_tables([(1, table)], conditions, source="percent")
    run = parse_tables(
        [(1, table)], conditions, source="percent", settings=Settings(efficiency_unit="percent")
    )
    assert run.measurements[1].efficiency == 0.8


def test_power_crosschecks_do_not_replace_reported_values(conditions, table):
    table[2][8] = 0.9
    table[2][7] = -100
    run = parse_tables([(1, table)], conditions, source="cross-check")
    assert run.measurements[1].efficiency == 0.9
    assert run.measurements[1].loss_w == -100
    codes = {i.code for i in run.issues}
    assert {"efficiency_mismatch", "power_mismatch", "negative_power_or_current"} <= codes


def test_out_of_range_efficiency_is_flagged_not_clamped(conditions, table):
    table[2][8] = 1.3
    run = parse_tables([(1, table)], conditions, source="range")
    assert run.measurements[1].efficiency == 1.3
    assert "efficiency_out_of_range" in run.measurements[1].flags


def test_unsorted_and_duplicate_loads_are_retained(conditions, table):
    run = parse_tables(
        [(1, [table[0], table[3], table[1], table[2], table[2]])], conditions, source="ordering"
    )
    assert [m.load_a for m in run.measurements] == [2, 0, 1, 1]
    assert {"unsorted_loads", "duplicate_loads"} <= {i.code for i in run.issues}


@pytest.mark.parametrize("page", [0, -1, True, "1"])
def test_page_provenance_requires_positive_integer(conditions, table, page):
    with pytest.raises(ParseError):
        parse_tables([(page, table)], conditions, source="page")


def test_text_fallback_and_form_feed_pages(conditions):
    run = parse_text(
        "No. Io Vo Vi Ii Po Pi Ploss Effi\n1 0 5 10 0 0 0 0 0\fNo. Io Vo Vi Ii Po Pi Ploss Effi\n2 1 5 10 0.625 5 6.25 1.25 0.8",
        conditions,
        source="text",
    )
    assert [m.page for m in run.measurements] == [1, 2]


def test_empty_inputs_fail_with_context(conditions):
    with pytest.raises(ParseError, match="No valid measurements"):
        parse_text("Some unrelated text", conditions, source="empty")


@pytest.mark.parametrize(
    "bad",
    [[], None, "text", {}, {"schema_version": "2"}, {"schema_version": "1.0", "conditions": []}],
)
def test_malformed_json_root_is_a_parse_error_not_attribute_error(tmp_path, bad):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ParseError):
        parse_table_json(path)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda d: d.update(tables=[]),
        lambda d: d.update(tables=[None]),
        lambda d: d["conditions"].update(channel=1),
        lambda d: d["conditions"].update(vin_v="10"),
        lambda d: d["tables"][0].update(rows=["not a row"]),
        lambda d: d["tables"][0].update(rows=[[["nested"]]]),
        lambda d: d["tables"][0].pop("page"),
    ],
)
def test_malformed_json_nested_schema_is_rejected(tmp_path, mutator):
    _, data = demo_documents()[0]
    mutator(data)
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ParseError):
        parse_table_json(path)


def test_portable_table_json_round_trip(tmp_path):
    name, data = demo_documents()[0]
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    run = parse_table_json(path)
    assert run.synthetic
    assert len(run.measurements) == 12
    assert run.source == name


def _mock_pdf(monkeypatch, pages):
    import pdfplumber

    document = MagicMock()
    document.__enter__.return_value = SimpleNamespace(pages=pages)
    monkeypatch.setattr(pdfplumber, "open", lambda path: document)
    return document


def test_pdf_adapter_reads_every_page_and_closes_file(tmp_path, monkeypatch, table):
    path = tmp_path / "__DEMO_1_10_5_500_1.pdf"
    path.write_bytes(b"adapter-test-double-not-a-real-pdf")
    pages = [
        SimpleNamespace(extract_tables=lambda: [table[:2]]),
        SimpleNamespace(extract_tables=lambda: [table[0:1] + table[2:]]),
    ]
    document = _mock_pdf(monkeypatch, pages)
    run = parse_pdf(path)
    assert [m.page for m in run.measurements] == [1, 2, 2]
    document.__exit__.assert_called_once()


def test_pdf_adapter_falls_back_to_text(tmp_path, monkeypatch):
    path = tmp_path / "DEMO_1_10_5_500_1.pdf"
    path.write_bytes(b"not-real-pdf")
    page = SimpleNamespace(
        extract_tables=lambda: [],
        extract_text=lambda: "No. Io Vo Vi Ii Po Pi Ploss Effi\n1 1 5 10 0.625 5 6.25 1.25 0.8",
    )
    _mock_pdf(monkeypatch, [page])
    assert parse_pdf(path).measurements[0].efficiency == 0.8


def test_pdf_scanned_empty_and_reader_errors_are_explicit(tmp_path, monkeypatch):
    import pdfplumber

    path = tmp_path / "DEMO_1_10_5_500_1.pdf"
    path.write_bytes(b"not-real-pdf")
    _mock_pdf(monkeypatch, [SimpleNamespace(extract_tables=lambda: [], extract_text=lambda: "")])
    with pytest.raises(ParseError, match="OCR"):
        parse_pdf(path)
    _mock_pdf(monkeypatch, [])
    with pytest.raises(ParseError, match="Empty"):
        parse_pdf(path)

    def broken(path):
        raise RuntimeError("adapter failure")

    monkeypatch.setattr(pdfplumber, "open", broken)
    with pytest.raises(ParseError, match="PDF reader failed"):
        parse_pdf(path)
