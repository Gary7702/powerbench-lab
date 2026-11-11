"""Offline report integrity, injection isolation, and presentation contracts."""

from __future__ import annotations

import copy
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from powerbench.models import Conditions, Issue, Measurement, Run
from powerbench.report import render_report


class ReportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.scripts: list[tuple[dict[str, str | None], str]] = []
        self._script_attrs: dict[str, str | None] | None = None
        self._script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        self.tags.append((tag, values))
        if tag == "script":
            self._script_attrs = values
            self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._script_attrs is not None:
            self._script_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._script_attrs is not None:
            self.scripts.append((self._script_attrs, "".join(self._script_parts)))
            self._script_attrs = None


@pytest.fixture
def payload() -> dict:
    conditions = Conditions("DEMO-A", "1", 12.0, 5.0, 500.0, "CCM")
    measurements = (
        Measurement(1, 0.0, 5.01, 12.0, 0.01, 0.0, 0.12, 0.12, 0.0, 2, 7),
        Measurement(2, 1.0, 5.0, 12.0, 0.5, 5.0, 6.0, 1.0, 5.0 / 6.0, 2, 8),
        Measurement(3, 2.0, 4.99, 12.0, 1.0, 9.98, 12.0, 2.02, None, 2, 9, ("missing_efficiency",)),
    )
    issue = Issue(
        "missing_efficiency",
        "Efficiency is unavailable for this point.",
        "fixture.csv",
        page=2,
        row=9,
    )
    run = Run(conditions, measurements, "fixture.csv", "a" * 64, (issue,), True)
    summary = {
        "source": run.source,
        "run_id": run.run_id,
        "conditions": conditions.as_dict(),
        "points": 3,
        "peak_efficiency_pct": 5.0 / 6.0 * 100,
        "peak_load_a": 1.0,
        "load_min_a": 0.0,
        "load_max_a": 2.0,
        "vout_mean_v": 5.0,
        "load_regulation_positive_pct": 0.2,
        "load_regulation_negative_pct": -0.2,
        "load_regulation_span_pct": 0.4,
    }
    fixed = conditions.as_dict()
    fixed.pop("vin_v")
    fixed.pop("timestamp")
    return {
        "schema_version": "1.0",
        "package_version": "0.1.0",
        "synthetic": True,
        "counts": {"runs": 1, "measurements": 3, "warnings": 1, "errors": 0},
        "runs": [run.as_dict()],
        "summaries": [summary],
        "line_regulation": [
            {
                "status": "ok",
                "conditions": fixed,
                "load_a": 1.0,
                "vin_values_v": [12.0, 24.0],
                "vout_values_v": [5.0, 4.99],
                "positive_pct": 0.1001,
                "negative_pct": -0.1001,
                "span_pct": 0.2002,
                "sources": ["fixture.csv", "fixture-24.csv"],
                "interpolated": True,
            },
            {
                "status": "ambiguous_replicates",
                "conditions": fixed,
                "message": "Repeated Vin; select one run explicitly.",
                "sources": ["fixture.csv"],
            },
        ],
        "issues": [issue.as_dict()],
    }


def parse_report(output: Path) -> tuple[str, ReportParser]:
    html = output.read_text(encoding="utf-8")
    parser = ReportParser()
    parser.feed(html)
    return html, parser


def embedded_data(parser: ReportParser) -> str:
    return next(text for attrs, text in parser.scripts if attrs.get("id") == "report-data")


def test_round_trip_preserves_every_measurement_and_issue(tmp_path: Path, payload: dict) -> None:
    output = tmp_path / "report.html"
    original = copy.deepcopy(payload)
    assert render_report(payload, output) is None
    html, parser = parse_report(output)
    assert payload == original
    assert json.loads(embedded_data(parser)) == original
    assert len(parser.scripts) == 2
    assert "PowerBench Lab" in html
    assert "offline bench analytics" in html
    assert html.startswith("<!doctype html>")
    assert [path.name for path in tmp_path.iterdir()] == ["report.html"]


@pytest.mark.parametrize(
    "malicious",
    [
        '</script><script>alert("injected")</script>',
        '</ScRiPt><img src=x onerror="alert(1)">',
        "<!-- <script>&source>\u2028\u2029",
        '<svg onload="alert(1)">测试来源</svg>',
    ],
)
def test_source_text_cannot_close_data_script(
    tmp_path: Path, payload: dict, malicious: str
) -> None:
    payload["runs"][0]["source"] = malicious
    payload["runs"][0]["conditions"]["sample_id"] = malicious
    payload["issues"][0]["message"] = malicious
    payload["line_regulation"][1]["message"] = malicious
    output = tmp_path / "safe.html"
    render_report(payload, output)
    html, parser = parse_report(output)
    data_text = embedded_data(parser)
    assert malicious not in html
    assert not any(character in data_text for character in ("<", ">", "&", "\u2028", "\u2029"))
    assert json.loads(data_text) == payload
    assert len(parser.scripts) == 2
    assert not any(
        tag == "img" or "onload" in attrs or "onerror" in attrs for tag, attrs in parser.tags
    )


def test_report_has_no_network_resources_or_unsafe_dom_sinks(tmp_path: Path, payload: dict) -> None:
    output = tmp_path / "offline.html"
    render_report(payload, output)
    html, parser = parse_report(output)
    for _, attrs in parser.tags:
        assert "src" not in attrs
        assert "href" not in attrs
        assert not any(name.lower().startswith("on") for name in attrs)
    script = next(text for attrs, text in parser.scripts if attrs.get("id") != "report-data")
    assert not re.search(
        r"\b(?:fetch|eval|XMLHttpRequest|WebSocket|EventSource|importScripts)\s*\(", script
    )
    assert not any(
        sink in script
        for sink in (
            "innerHTML",
            "outerHTML",
            "insertAdjacentHTML",
            "document.write",
            "localStorage",
            "sessionStorage",
            "sendBeacon",
            "new Function",
        )
    )
    assert not re.search(r"@import\b|url\s*\(", html, re.IGNORECASE)
    assert "textContent" in script
    assert "connect-src 'none'" in html
    assert "no telemetry" in html


def test_synthetic_banner_is_visible_without_javascript(tmp_path: Path, payload: dict) -> None:
    output = tmp_path / "synthetic.html"
    render_report(payload, output)
    html, _ = parse_report(output)
    before_scripts = html.split('<script id="report-data"', 1)[0]
    assert "SYNTHETIC DEMONSTRATION DATA" in before_scripts
    assert "not actual device measurements" in before_scripts
    assert "not actual" in before_scripts


def test_run_synthetic_flag_also_triggers_banner(tmp_path: Path, payload: dict) -> None:
    payload["synthetic"] = False
    output = tmp_path / "mixed-origin.html"
    render_report(payload, output)
    assert "SYNTHETIC DEMONSTRATION DATA" in output.read_text(encoding="utf-8")


def test_non_synthetic_report_does_not_claim_certification(tmp_path: Path, payload: dict) -> None:
    payload["synthetic"] = False
    payload["runs"][0]["synthetic"] = False
    output = tmp_path / "input-data.html"
    render_report(payload, output)
    html, _ = parse_report(output)
    assert "SYNTHETIC DEMONSTRATION DATA" not in html
    assert "TRACEABLE INPUT DATA" in html
    assert "does not certify device performance" in html


def test_controls_and_accessibility_contract(tmp_path: Path, payload: dict) -> None:
    output = tmp_path / "controls.html"
    render_report(payload, output)
    html, parser = parse_report(output)
    ids = [attrs["id"] for _, attrs in parser.tags if "id" in attrs]
    assert len(ids) == len(set(ids))
    assert set(
        (
            "filter-sample",
            "filter-channel",
            "filter-vin",
            "filter-mode",
            "comparison-set",
            "mixed",
            "search",
            "reset",
            "log-x",
            "legend",
            "point-details",
            "summary-body",
            "line-body",
            "severity",
            "issue-list",
        )
    ).issubset(ids)
    metric_buttons = [
        attrs.get("data-metric")
        for tag, attrs in parser.tags
        if tag == "button" and "data-metric" in attrs
    ]
    assert metric_buttons == ["efficiency", "vout_v", "loss_w"]
    assert "Mixed conditions - visual inspection only" in html
    assert "zero/nonpositive-load point(s) excluded" in html
    assert "source data and summaries are unchanged" in html
    assert 'tabindex:0,role:"button"' in html
    assert 'event.key==="Enter"' in html
    assert "@media(max-width:640px)" in html
    assert 'name="color-scheme" content="light"' in html


def test_formula_notes_match_analysis_contract(tmp_path: Path, payload: dict) -> None:
    output = tmp_path / "formulas.html"
    render_report(payload, output)
    html, _ = parse_report(output)
    assert "Load regulation uses measured mean Vout" in html
    assert "(min − mean) / mean" in html
    assert "Percentages use the mean Vout across the evaluated sweep" in html
    assert "Linearly interpolated sweep" in html
    assert "Exact measured sweep" in html
    assert "they are not necessarily rated zero/half/full load" in html
    assert "entry.message" in html
    assert "No pooled statistics or cross-condition ranking" in html


def test_empty_dataset_still_produces_valid_self_contained_report(tmp_path: Path) -> None:
    payload = {
        "schema_version": "1.0",
        "package_version": "0.1.0",
        "synthetic": False,
        "counts": {"runs": 0, "measurements": 0, "warnings": 0, "errors": 0},
        "runs": [],
        "summaries": [],
        "line_regulation": [],
        "issues": [],
    }
    output = tmp_path / "empty.html"
    render_report(payload, output)
    html, parser = parse_report(output)
    assert json.loads(embedded_data(parser)) == payload
    assert "No visible curves" in html
    assert "No run summaries match this view" in html


def test_unicode_sources_and_utf8_are_preserved(tmp_path: Path, payload: dict) -> None:
    payload["runs"][0]["source"] = "中文样品/效率测试.csv"
    output = tmp_path / "utf8.html"
    render_report(payload, output)
    content = output.read_bytes()
    assert "中文样品/效率测试.csv".encode() in content
    _, parser = parse_report(output)
    assert json.loads(embedded_data(parser))["runs"][0]["source"] == "中文样品/效率测试.csv"


def test_parent_directory_is_not_created_implicitly(tmp_path: Path, payload: dict) -> None:
    output = tmp_path / "missing" / "report.html"
    with pytest.raises(FileNotFoundError):
        render_report(payload, output)
    assert not output.parent.exists()


def test_nonfinite_payload_fails_before_overwriting_output(tmp_path: Path, payload: dict) -> None:
    output = tmp_path / "report.html"
    output.write_text("existing report", encoding="utf-8")
    payload["runs"][0]["measurements"][0]["efficiency"] = float("nan")
    with pytest.raises(ValueError):
        render_report(payload, output)
    assert output.read_text(encoding="utf-8") == "existing report"


def test_render_is_deterministic(tmp_path: Path, payload: dict) -> None:
    first, second = tmp_path / "first.html", tmp_path / "second.html"
    render_report(payload, first)
    render_report(payload, second)
    assert first.read_bytes() == second.read_bytes()
