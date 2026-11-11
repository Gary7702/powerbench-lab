"""Render offline, self-contained reports without treating input text as HTML."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def render_report(payload: dict[str, Any], output: Path) -> None:
    """Write a UTF-8 report; the caller provides an existing parent directory."""
    data = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    for character, escaped in (
        ("&", "\\u0026"),
        ("<", "\\u003c"),
        (">", "\\u003e"),
        ("\u2028", "\\u2028"),
        ("\u2029", "\\u2029"),
    ):
        data = data.replace(character, escaped)
    banner = (
        '<aside class="notice synthetic" role="note"><strong>SYNTHETIC DEMONSTRATION DATA</strong>'
        "<span>Generated fixtures for software validation and portfolio demonstration. "
        "These are not actual device measurements or equipment performance claims.</span></aside>"
        if payload.get("synthetic") or any(run.get("synthetic") for run in payload.get("runs", []))
        else '<aside class="notice" role="note"><strong>TRACEABLE INPUT DATA</strong>'
        "<span>Values reflect the supplied files. Review quality issues and test conditions "
        "before interpreting results; this report does not certify device performance.</span></aside>"
    )
    html = _TEMPLATE.replace("__DATA_NOTICE__", banner).replace("__PAYLOAD_JSON__", data)
    output.write_text(html, encoding="utf-8")


_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; font-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
<title>PowerBench Lab | Offline Bench Analytics</title>
<style>
:root{--bg:#f3f6f8;--paper:#fff;--ink:#172d40;--muted:#647588;--line:#dfe7ed;--teal:#007f83;--cyan:#0e9fac;--soft:#e9f6f5;--warn:#8a5b0e;--red:#b54747;--radius:16px}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,"Segoe UI",Arial,sans-serif;font-size:14px;line-height:1.55}button,input,select{font:inherit}button,select,input[type=checkbox]{cursor:pointer}button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid #69cbd4;outline-offset:3px}button{color:var(--ink)}.shell{max-width:1420px;margin:auto;padding:0 42px}.topbar{border-bottom:1px solid var(--line);background:#fff}.topbar .shell{min-height:78px;display:flex;align-items:center;justify-content:space-between;gap:18px}.brand{display:flex;gap:13px;align-items:center}.brand-mark{width:35px;height:35px;flex-shrink:0}.brand-name{font-size:18px;font-weight:750;letter-spacing:-.5px}.brand-sub{font-size:10px;letter-spacing:1.9px;text-transform:uppercase;color:var(--muted)}.offline{display:flex;align-items:center;gap:7px;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--teal)}.dot{width:6px;height:6px;background:var(--teal);border-radius:50%}.masthead{padding:40px 0 26px;display:flex;justify-content:space-between;align-items:end;gap:24px}.eyebrow{font-size:11px;letter-spacing:1.8px;font-weight:750;text-transform:uppercase;color:var(--teal);margin:0 0 8px}h1{font-size:clamp(28px,4vw,40px);line-height:1.2;letter-spacing:-1.3px;margin:0 0 10px;font-weight:700}.subtitle{color:var(--muted);margin:0;max-width:700px}.report-meta{font-family:Consolas,monospace;font-size:11px;color:var(--muted);text-align:right;white-space:nowrap}.notice{display:flex;gap:16px;align-items:baseline;padding:15px 18px;border:1px solid #c7e5e2;border-left:3px solid var(--teal);background:#eef8f6;border-radius:8px;font-size:12px;margin-bottom:24px}.notice strong{font-size:10px;letter-spacing:.8px;flex-shrink:0}.notice span{color:#44626a}.synthetic{background:#fff9ea;border-color:#ebd5a5;border-left-color:#bc8a20}.synthetic strong{color:#80580d}.synthetic span{color:#795f2c}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}.metric{border:1px solid var(--line);background:var(--paper);border-radius:var(--radius);padding:21px 24px}.metric-label{font-size:11px;text-transform:uppercase;letter-spacing:1.1px;color:var(--muted)}.metric-value{font-size:34px;font-weight:650;letter-spacing:-1px;line-height:1.4;font-variant-numeric:tabular-nums}.metric-foot{font-size:11px;color:var(--muted)}.metric:nth-child(2) .metric-value{color:var(--teal)}.metric:nth-child(3) .metric-value{color:var(--warn)}.metric:nth-child(4) .metric-value{color:var(--red)}.panel{border:1px solid var(--line);background:var(--paper);border-radius:var(--radius);margin-bottom:24px;overflow:hidden;box-shadow:0 2px 5px #19344b03}.panel-header{padding:23px 26px 18px;display:flex;align-items:start;justify-content:space-between;gap:18px}.section-id{font-family:Consolas,monospace;font-size:11px;color:var(--teal);margin-right:9px}h2{font-size:18px;font-weight:650;letter-spacing:-.35px;margin:0}h3{margin:0;font-size:14px;font-weight:650}.hint{font-size:12px;color:var(--muted);margin:5px 0 0}.badge{padding:4px 9px;background:var(--soft);color:var(--teal);font-size:10px;border-radius:5px;white-space:nowrap;text-transform:uppercase;letter-spacing:.7px}.filters{padding:0 26px 19px;display:grid;grid-template-columns:repeat(4,minmax(110px,1fr)) minmax(185px,1.5fr) auto;gap:12px;align-items:end}label.field{display:flex;flex-direction:column;gap:6px;font-size:11px;font-weight:600;color:var(--muted)}select,input[type=search]{width:100%;min-width:0;background:#fff;border:1px solid #d3dee6;border-radius:7px;padding:9px 10px;color:var(--ink);height:39px;font-size:12px}button.secondary{border:1px solid var(--line);border-radius:7px;background:#fff;padding:9px 14px;height:39px;white-space:nowrap;font-size:12px}button.secondary:hover{background:var(--bg)}.scope-controls{padding:17px 26px;background:#fafcfd;border-top:1px solid var(--line);display:flex;align-items:end;gap:22px}.scope-controls .field{max-width:720px;flex:1}.check{display:flex;align-items:center;gap:8px;font-size:12px;min-height:39px}.check input{accent-color:var(--teal)}.scope-note{padding:12px 26px;color:#35656b;background:#f0f9f8;font-size:12px;border-top:1px solid #dceeed}.scope-note.mixed{color:#8a5b0e;background:#fff7e8;border-color:#eedfbc}.plot-toolbar{padding:21px 26px 8px;display:flex;justify-content:space-between;gap:16px;align-items:center}.segmented{display:inline-flex;gap:3px;padding:4px;background:var(--bg);border-radius:8px}.segmented button{font-size:12px;background:none;border:0;padding:7px 16px;border-radius:6px}.segmented button[aria-pressed=true]{background:#fff;color:var(--teal);box-shadow:0 1px 4px #17394a16;font-weight:650}.chart-wrap{padding:0 14px;overflow-x:auto}.chart{display:block;width:100%;min-width:620px;height:auto}.chart text{font-family:Inter,"Segoe UI",Arial,sans-serif}.chart .point{cursor:pointer;outline:none}.chart .point:hover,.chart .point:focus{stroke:var(--ink);stroke-width:3}.chart-note{margin:0 26px;color:var(--muted);font-size:11px;min-height:21px}.legend{display:flex;flex-wrap:wrap;gap:8px 18px;padding:15px 26px 20px}.legend label{display:flex;gap:7px;align-items:center;max-width:100%;font-size:11px;cursor:pointer}.legend input{accent-color:var(--teal)}.legend-label{overflow-wrap:anywhere}.swatch{height:3px;width:20px;border-radius:2px;flex-shrink:0}.point-panel{padding:18px 26px;background:#f8fbfc;border-top:1px solid var(--line)}.point-head{display:flex;align-items:center;justify-content:space-between;gap:15px}.point-head button{padding:4px 8px;font-size:11px;border:1px solid var(--line);border-radius:5px;background:#fff}.point-prompt{font-size:12px;color:var(--muted);margin:9px 0 0}.point-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:13px 20px;margin:14px 0 0}.point-grid dt{color:var(--muted);font-size:10px;margin-bottom:3px;text-transform:uppercase;letter-spacing:.6px}.point-grid dd{margin:0;font-size:12px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.point-grid .wide{grid-column:span 3}.table-wrap{overflow-x:auto;padding-bottom:5px}table{border-collapse:collapse;width:100%;font-size:12px;white-space:nowrap}th{padding:11px 17px;background:#f8fafc;color:var(--muted);font-weight:600;text-align:left;font-size:10px;letter-spacing:.5px;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}td{padding:14px 17px;border-bottom:1px solid #edf1f5;font-variant-numeric:tabular-nums;vertical-align:top}th:first-child,td:first-child{padding-left:26px}tbody tr:last-child td{border-bottom:0}tbody tr:hover{background:#fbfdfd}.cell-sub{font-size:10px;color:var(--muted);margin-top:3px;white-space:normal;max-width:270px;overflow-wrap:anywhere}.numeric{text-align:right}.emphasis{color:var(--teal);font-weight:650}.table-note{margin:0;padding:13px 26px 18px;font-size:11px;color:var(--muted);border-top:1px solid var(--line)}.empty{color:var(--muted);padding:25px!important;text-align:center;white-space:normal}.issue-list{padding:0 26px 20px;display:grid;gap:9px;max-height:450px;overflow-y:auto}.issue{padding:14px 15px;border:1px solid var(--line);border-radius:9px;display:flex;gap:12px}.severity{color:var(--warn);background:#fff5df;padding:3px 7px;font-size:9px;font-weight:700;letter-spacing:.5px;height:max-content;border-radius:4px;flex-shrink:0}.severity.error{color:var(--red);background:#fff0f0}.issue-body{min-width:0}.issue-code{font-size:11px;font-weight:700}.issue-message{font-size:12px;margin:3px 0 5px;overflow-wrap:anywhere}.issue-source{font-size:10px;color:var(--muted);overflow-wrap:anywhere}.quality-tools{display:flex;align-items:center;gap:9px}.quality-tools select{max-width:160px;height:34px;padding:5px 9px}.footer{display:flex;justify-content:space-between;gap:20px;padding:2px 0 30px;font-size:10px;color:var(--muted);letter-spacing:.4px}.footer strong{color:var(--ink);font-weight:600}.noscript{padding:20px;border:1px solid #ebd5a5;background:#fff9ea}#status{font-size:11px;color:var(--muted)}[hidden]{display:none!important}
@media(max-width:1050px){.shell{padding:0 24px}.filters{grid-template-columns:repeat(4,1fr)}.filters .search-field{grid-column:span 3}.point-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.point-grid .wide{grid-column:span 3}.notice{align-items:start;flex-direction:column;gap:4px}.report-meta{display:none}}
@media(max-width:640px){.shell{padding:0 16px}.topbar .shell{min-height:68px}.brand-name{font-size:16px}.brand-sub{font-size:8px;letter-spacing:1.4px}.offline{font-size:9px}.masthead{padding:28px 0 21px}.metrics{grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:18px}.metric{padding:15px}.metric-value{font-size:29px}.metric-label{font-size:9px}.metric-foot{font-size:10px}.panel{margin-bottom:18px;border-radius:12px}.panel-header{padding:19px 16px 15px;flex-wrap:wrap}.filters{padding:0 16px 16px;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.filters .search-field{grid-column:span 2}.filters button{grid-column:span 2}.scope-controls{padding:15px 16px;flex-direction:column;align-items:stretch;gap:7px}.scope-note{padding:12px 16px}.plot-toolbar{padding:16px 16px 7px;align-items:start;flex-wrap:wrap}.segmented button{padding:7px 12px}.legend{padding:12px 16px 17px;gap:9px}.legend label{width:100%}.point-panel{padding:16px}.point-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.point-grid .wide{grid-column:span 2}.chart-note{margin:0 16px}.table-note{padding:13px 16px}.issue-list{padding:0 16px 16px}.footer{flex-direction:column;gap:5px}.quality-tools{width:100%;justify-content:space-between}.notice{margin-bottom:18px}.point-head{align-items:start}h2{font-size:17px}}
@media print{body{background:#fff}.shell{max-width:none;padding:0 10px}.panel{break-inside:avoid;box-shadow:none}.filters,.scope-controls,.segmented,.check,.quality-tools select,button{display:none!important}.chart{min-width:0}.table-wrap{overflow:visible}.issue-list{max-height:none}.topbar{border-bottom:1px solid #ccc}.masthead{padding-top:20px}.notice{break-inside:avoid}}
</style>
</head>
<body>
<header class="topbar"><div class="shell"><div class="brand"><svg class="brand-mark" viewBox="0 0 36 36" aria-hidden="true"><rect x="1" y="1" width="34" height="34" rx="9" fill="#e7f5f4"/><path d="M7 24h5l4-13 5 17 3-11h5" fill="none" stroke="#007f83" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg><div><div class="brand-name">PowerBench Lab</div><div class="brand-sub">offline bench analytics</div></div></div><span class="offline"><span class="dot"></span>Self-contained report</span></div></header>
<main class="shell">
<section class="masthead"><div><p class="eyebrow">Measurement intelligence / engineering workspace</p><h1>Every curve. In context.</h1><p class="subtitle">Inspect efficiency, output voltage and power loss with explicit test conditions and point-level source traceability.</p></div><div class="report-meta" id="report-meta"></div></section>
__DATA_NOTICE__
<noscript><p class="noscript">Enable JavaScript to view this offline interactive report. All report data is embedded in this file; no network connection is needed.</p></noscript>
<section class="metrics" aria-label="Dataset overview">
<div class="metric"><div class="metric-label">Measurement runs</div><div class="metric-value" id="count-runs">—</div><div class="metric-foot">Source-isolated test sequences</div></div>
<div class="metric"><div class="metric-label">Data points</div><div class="metric-value" id="count-measurements">—</div><div class="metric-foot">Measurements retained in dataset</div></div>
<div class="metric"><div class="metric-label">Warnings</div><div class="metric-value" id="count-warnings">—</div><div class="metric-foot">Review before interpretation</div></div>
<div class="metric"><div class="metric-label">Errors</div><div class="metric-value" id="count-errors">—</div><div class="metric-foot">See quality log for affected sources</div></div>
</section>
<section class="panel" aria-labelledby="explorer-title">
<div class="panel-header"><div><h2 id="explorer-title"><span class="section-id">01</span>Curve explorer</h2><p class="hint">Compare like-for-like conditions. Inspect any point to recover its provenance.</p></div><span class="badge">Interactive SVG</span></div>
<div class="filters">
<label class="field">Sample<select id="filter-sample" aria-label="Filter by sample"></select></label>
<label class="field">Channel<select id="filter-channel" aria-label="Filter by channel"></select></label>
<label class="field">Input voltage<select id="filter-vin" aria-label="Filter by input voltage"></select></label>
<label class="field">Operating mode<select id="filter-mode" aria-label="Filter by operating mode"></select></label>
<label class="field search-field">Search dataset<input id="search" type="search" placeholder="Source, sample, condition or issue…" autocomplete="off"></label>
<button class="secondary" id="reset" type="button">Reset view</button>
</div>
<div class="scope-controls"><label class="field">Comparable condition set<select id="comparison-set" aria-label="Comparable condition set"></select></label><label class="check"><input type="checkbox" id="mixed">Show all matching curves</label></div>
<div class="scope-note" id="scope-note" role="status"></div>
<div class="plot-toolbar"><div class="segmented" role="group" aria-label="Chart quantity"><button type="button" data-metric="efficiency" aria-pressed="true">Efficiency</button><button type="button" data-metric="vout_v" aria-pressed="false">Vout</button><button type="button" data-metric="loss_w" aria-pressed="false">Loss</button></div><label class="check"><input type="checkbox" id="log-x">Logarithmic load axis</label></div>
<div class="chart-wrap"><svg class="chart" id="chart" viewBox="0 0 1040 430" role="img" aria-labelledby="chart-title chart-description"></svg></div>
<p id="chart-note" class="chart-note" aria-live="polite"></p><div class="legend" id="legend" aria-label="Toggle individual curves"></div>
<div class="point-panel"><div class="point-head"><h3>Point inspection</h3><button type="button" id="clear-point" hidden>Clear selection</button></div><p class="point-prompt" id="point-prompt">Hover, focus or select a marker to inspect it. Click or press Enter to pin a point.</p><dl class="point-grid" id="point-details" hidden aria-live="polite"></dl></div>
</section>
<section class="panel" aria-labelledby="summary-title"><div class="panel-header"><div><h2 id="summary-title"><span class="section-id">02</span>Run-level summary</h2><p class="hint">Filtered condition set; each run is summarized independently, including curves switched off above.</p></div><span class="badge" id="summary-count"></span></div><div class="table-wrap"><table><thead><tr><th>Run / source</th><th>Conditions</th><th class="numeric">Points</th><th class="numeric">Peak efficiency</th><th class="numeric">Peak load</th><th class="numeric">Load range</th><th class="numeric">Mean Vout</th><th class="numeric">Load reg. +</th><th class="numeric">Load reg. −</th><th class="numeric">Load span</th></tr></thead><tbody id="summary-body"></tbody></table></div><p class="table-note">Efficiency displays the reported fraction × 100; Pout / Pin is a diagnostic cross-check only. Load regulation uses measured mean Vout: + = (max − mean) / mean; − = (min − mean) / mean; span = (max − min) / mean; all expressed as %. Signed deviations are preserved. No pooled statistics or cross-condition ranking.</p></section>
<section class="panel" aria-labelledby="line-title"><div class="panel-header"><div><h2 id="line-title"><span class="section-id">03</span>Line regulation</h2><p class="hint">Matched-load analysis across input voltages. Linear interpolation is disclosed; extrapolation and cross-condition merging are prohibited.</p></div><span class="badge" id="line-count"></span></div><div class="table-wrap"><table><thead><tr><th>Condition set</th><th class="numeric">Matched load</th><th>Vin sweep</th><th>Measured Vout</th><th class="numeric">Positive</th><th class="numeric">Negative</th><th class="numeric">Span</th><th>Status / sources</th></tr></thead><tbody id="line-body"></tbody></table></div><p class="table-note">Entries follow the selected condition set and filters. Vin filtering selects existing sweep entries containing that voltage; it does not recompute their sweep. Percentages use the mean Vout across the evaluated sweep. Targets lie inside the common measured load range; they are not necessarily rated zero/half/full load. Unavailable or ambiguous matches remain explicit.</p></section>
<section class="panel" aria-labelledby="quality-title"><div class="panel-header"><div><h2 id="quality-title"><span class="section-id">04</span>Data quality log</h2><p class="hint">Dataset-wide validation events, independent of curve filters. Search applies to this log.</p></div><div class="quality-tools"><span id="issue-count" class="badge"></span><select id="severity" aria-label="Filter quality issues"><option value="">All severities</option><option value="warning">Warnings</option><option value="error">Errors</option></select></div></div><div class="issue-list" id="issue-list"></div></section>
<footer class="footer"><div><strong>PowerBench Lab</strong> / evidence before conclusions</div><div id="status" role="status"></div><div>Local file · no external resources · no telemetry</div></footer>
</main>
<script id="report-data" type="application/json">__PAYLOAD_JSON__</script>
<script>
"use strict";
(() => {
  const data = JSON.parse(document.getElementById("report-data").textContent);
  const runs = data.runs || [], summaries = data.summaries || [], lineEntries = data.line_regulation || [], issues = data.issues || [];
  const el = id => document.getElementById(id);
  const node = (tag, text, className) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = String(text); if (className) n.className = className; return n; };
  const svgNode = (tag, attrs, text) => { const n = document.createElementNS("http://www.w3.org/2000/svg", tag); Object.entries(attrs || {}).forEach(([k,v]) => n.setAttribute(k, String(v))); if (text !== undefined) n.textContent = String(text); return n; };
  const fmt = (value, decimals = 3, unit = "") => typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("en-US", {maximumFractionDigits:decimals}) + unit : "—";
  const signed = value => typeof value === "number" && Number.isFinite(value) ? (value > 0 ? "+" : "") + fmt(value, 4, "%") : "—";
  const sameFields = ["sample_id", "channel", "vout_v", "frequency_khz", "mode"];
  const groupKey = c => JSON.stringify(sameFields.map(field => (c || {})[field]));
  const modeLabel = value => ((data.settings || {}).mode_labels || {})[String(value)] || ("Mode " + String(value));
  const conditionText = (c, withVin = true) => ["Sample " + (c.sample_id ?? "—"), "CH " + (c.channel ?? "—"), ...(withVin ? [fmt(c.vin_v, 3, " V in")] : []), fmt(c.vout_v, 3, " V out"), fmt(c.frequency_khz, 3, " kHz"), modeLabel(c.mode ?? "—")].join(" · ");
  const queryMatches = value => !el("search").value.trim() || JSON.stringify(value).toLowerCase().includes(el("search").value.trim().toLowerCase());
  const colors = ["#007f83", "#346dd2", "#a35ea8", "#c27d21", "#e06452", "#617c45", "#8067c3", "#46788d"];
  const color = run => colors[runs.indexOf(run) % colors.length];
  const state = {metric:"efficiency", group:"", hidden:new Set(), pinned:null};
  const filterDefs = [["filter-sample","sample_id","All samples"],["filter-channel","channel","All channels"],["filter-vin","vin_v","All input voltages"],["filter-mode","mode","All modes"]];
  const filteredRuns = () => runs.filter(run => filterDefs.every(([id,key]) => !el(id).value || String(run.conditions[key]) === el(id).value) && queryMatches([run.source,run.run_id,run.conditions]));
  const selectedRuns = () => filteredRuns().filter(run => el("mixed").checked || groupKey(run.conditions) === state.group);
  function fillFilters() {
    filterDefs.forEach(([id,key,label]) => {
      const select = el(id); select.replaceChildren(); const all = node("option",label); all.value = ""; select.append(all);
      const values = [...new Set(runs.map(run => run.conditions[key]))].sort((a,b) => typeof a === "number" && typeof b === "number" ? a-b : String(a).localeCompare(String(b),"en",{numeric:true}));
      values.forEach(value => { const option = node("option", key === "vin_v" ? fmt(value,3," V") : key === "mode" ? modeLabel(value) : String(value)); option.value = String(value); select.append(option); });
    });
  }
  function refreshGroups() {
    const groups = new Map(); filteredRuns().forEach(run => groups.set(groupKey(run.conditions), run.conditions));
    if (!groups.has(state.group)) state.group = groups.keys().next().value || "";
    const select = el("comparison-set"); select.replaceChildren();
    groups.forEach((conditions,key) => { const option = node("option",conditionText(conditions,false)); option.value = key; select.append(option); });
    if (!groups.size) { const option = node("option","No matching condition sets"); option.value = ""; select.append(option); }
    select.value = state.group; select.disabled = el("mixed").checked || !groups.size;
  }
  function resetPoint() { state.pinned = null; el("point-details").replaceChildren(); el("point-details").hidden = true; el("point-prompt").hidden = false; el("clear-point").hidden = true; }
  function showPoint(run, point, pinned = false) {
    const details = el("point-details"); details.replaceChildren(); details.hidden = false; el("point-prompt").hidden = true; el("clear-point").hidden = !state.pinned;
    const fields = [["Source",run.source,"wide"],["Conditions",conditionText(run.conditions),"wide"],["Page / table / row",String(point.page) + " / " + String(point.table || 1) + " / " + String(point.row)],["Point",String(point.point) + (pinned ? " · pinned" : "")],["Load",fmt(point.load_a,6," A")],["Efficiency",fmt(point.efficiency === null ? null : point.efficiency * 100,4,"%")],["Measured Vout",fmt(point.vout_v,6," V")],["Power loss",fmt(point.loss_w,6," W")],["Measured Vin",fmt(point.vin_v,6," V")],["Input current",fmt(point.iin_a,6," A")],["Input power",fmt(point.pin_w,6," W")],["Output power",fmt(point.pout_w,6," W")],["Flags",(point.flags || []).join(", ") || "None"],["Timestamp",run.conditions.timestamp || "Not provided"],["Run ID",run.run_id,"wide"],["Source SHA-256",run.sha256,"wide"]];
    fields.forEach(([label,value,cls]) => { const group = node("div",undefined,cls); group.append(node("dt",label),node("dd",value)); details.append(group); });
  }
  function restorePoint() { if (state.pinned) showPoint(state.pinned.run,state.pinned.point,true); else resetPoint(); }
  function drawChart(scoped) {
    const svg = el("chart"); svg.replaceChildren(); const log = el("log-x").checked;
    const metrics = {efficiency:{label:"Efficiency (%)",get:p => p.efficiency === null || p.efficiency === undefined || p.efficiency < 0 || p.efficiency > 1 ? null : p.efficiency * 100},vout_v:{label:"Output voltage (V)",get:p => p.vout_v},loss_w:{label:"Power loss (W)",get:p => p.loss_w}};
    const metric = metrics[state.metric]; const active = scoped.filter(run => !state.hidden.has(run.run_id));
    svg.append(svgNode("title",{id:"chart-title"},metric.label + " versus load current"),svgNode("desc",{id:"chart-description"},"Toggle curves using the legend. Focus, hover or select markers to inspect source, page, row and measurement values. " + (log ? "Logarithmic load current axis; zero-load points are excluded." : "Linear load current axis.")));
    const pointsByRun = active.map(run => ({run,points:run.measurements.filter(p => typeof p.load_a === "number" && Number.isFinite(p.load_a) && typeof metric.get(p) === "number" && Number.isFinite(metric.get(p)) && (!log || p.load_a > 0)).slice().sort((a,b) => a.load_a - b.load_a)}));
    const all = pointsByRun.flatMap(entry => entry.points); const zeroCount = active.reduce((sum,run) => sum + run.measurements.filter(p => p.load_a <= 0).length,0);
    const omitted = active.reduce((sum,run) => sum + run.measurements.filter(p => metric.get(p) === null || !Number.isFinite(metric.get(p))).length,0);
    const noteParts = [log ? "Log X: " + zeroCount + " zero/nonpositive-load point(s) excluded from the chart; source data and summaries are unchanged." : "Linear X · load current (A). Curves connect measured points; they are not fitted models."];
    if (omitted) noteParts.push(omitted + " point(s) have no valid " + metric.label.toLowerCase() + " value and are not plotted.");
    el("chart-note").textContent = noteParts.join(" ");
    const left=83,right=1007,top=31,bottom=354;
    svg.append(svgNode("text",{x:left,y:17,fill:"#52687b","font-size":12},metric.label),svgNode("text",{x:(left+right)/2,y:409,fill:"#52687b","font-size":12,"text-anchor":"middle"},log ? "Load current (A) · logarithmic scale" : "Load current (A)"));
    if (!all.length) { svg.append(svgNode("rect",{x:left,y:top,width:right-left,height:bottom-top,fill:"#fafcfd",rx:8}),svgNode("text",{x:(left+right)/2,y:193,"text-anchor":"middle",fill:"#647588","font-size":16},active.length ? "No plottable points for this quantity / axis." : "No visible curves. Adjust filters or enable a curve.")); renderLegend(scoped); return; }
    let xMin=Infinity,xMax=-Infinity,yMin=Infinity,yMax=-Infinity;
    all.forEach(p => { const x=log ? Math.log10(p.load_a) : p.load_a, y=metric.get(p); xMin=Math.min(xMin,x); xMax=Math.max(xMax,x); yMin=Math.min(yMin,y); yMax=Math.max(yMax,y); });
    if (xMin===xMax) { if(log) { xMin-=.25; xMax+=.25; } else { const padding=Math.max(Math.abs(xMin)*.1,.1); xMin=Math.max(0,xMin-padding); xMax+=padding; } }
    if(!log) xMin=Math.min(0,xMin);
    const yPadding=Math.max((yMax-yMin)*.12,Math.abs(yMax)*.004,.001); yMin-=yPadding; yMax+=yPadding;
    const px=value => left+((log ? Math.log10(value) : value)-xMin)/(xMax-xMin)*(right-left), py=value => bottom-(value-yMin)/(yMax-yMin)*(bottom-top);
    const tickFormat = value => { if (value === 0) return "0"; const abs=Math.abs(value); return abs >= 100000 || abs < .001 ? value.toExponential(2) : fmt(value, abs < .1 ? 4 : abs < 10 ? 3 : 2); };
    for(let i=0;i<=5;i++) { const y=top+i*(bottom-top)/5, value=yMax-i*(yMax-yMin)/5; svg.append(svgNode("line",{x1:left,x2:right,y1:y,y2:y,stroke:"#e8eef3","stroke-width":1}),svgNode("text",{x:left-14,y:y+4,"text-anchor":"end",fill:"#718195","font-size":11},tickFormat(value))); }
    for(let i=0;i<=6;i++) { const x=left+i*(right-left)/6, value=xMin+i*(xMax-xMin)/6; svg.append(svgNode("line",{x1:x,x2:x,y1:top,y2:bottom,stroke:"#f0f3f6","stroke-width":1}),svgNode("text",{x,y:bottom+24,"text-anchor":"middle",fill:"#718195","font-size":11},tickFormat(log ? Math.pow(10,value) : value))); }
    svg.append(svgNode("line",{x1:left,x2:right,y1:bottom,y2:bottom,stroke:"#ccd9e3","stroke-width":1}));
    pointsByRun.forEach(({run,points}) => {
      if (!points.length) return;
      // Missing/invalid values break the line instead of inventing continuity.
      let penDown = false;
      const path = run.measurements.slice().sort((a,b) => a.load_a - b.load_a).map(p => {
        const y = metric.get(p);
        if (y === null || !Number.isFinite(y) || !Number.isFinite(p.load_a) || (log && p.load_a <= 0)) { penDown = false; return ""; }
        const command = penDown ? "L" : "M"; penDown = true;
        return command + px(p.load_a).toFixed(3) + "," + py(y).toFixed(3);
      }).join(" ");
      svg.append(svgNode("path",{d:path,fill:"none",stroke:color(run),"stroke-width":2.5,"stroke-linecap":"round","stroke-linejoin":"round"}));
      points.forEach(point => {
        const label = run.source + ", page " + point.page + ", row " + point.row + ", load " + fmt(point.load_a,6," A") + ", " + metric.label + " " + fmt(metric.get(point),6);
        const marker=svgNode("circle",{cx:px(point.load_a),cy:py(metric.get(point)),r:4.5,fill:"#fff",stroke:color(run),"stroke-width":2,class:"point",tabindex:0,role:"button","aria-label":label});
        marker.append(svgNode("title",{},label));
        marker.addEventListener("mouseenter",() => showPoint(run,point)); marker.addEventListener("mouseleave",restorePoint); marker.addEventListener("focus",() => showPoint(run,point)); marker.addEventListener("blur",restorePoint);
        const pin=() => { state.pinned={run,point}; showPoint(run,point,true); };
        marker.addEventListener("click",pin); marker.addEventListener("keydown",event => { if(event.key==="Enter" || event.key===" ") { event.preventDefault(); pin(); } }); svg.append(marker);
      });
    });
    renderLegend(scoped);
  }
  function renderLegend(scoped) {
    const legend=el("legend"); legend.replaceChildren();
    scoped.forEach(run => { const label=node("label"), input=node("input"), swatch=node("span",undefined,"swatch"); input.type="checkbox"; input.checked=!state.hidden.has(run.run_id); swatch.style.backgroundColor=color(run); const labelText=fmt(run.conditions.vin_v,3," V in")+" · "+run.source+(el("mixed").checked ? " · "+conditionText(run.conditions,false) : ""); input.setAttribute("aria-label","Show curve: "+labelText); label.append(input,swatch,node("span",labelText,"legend-label")); input.addEventListener("change",() => { if(input.checked) state.hidden.delete(run.run_id); else state.hidden.add(run.run_id); resetPoint(); drawChart(selectedRuns()); updateStatus(); }); legend.append(label); });
  }
  function emptyRow(body,columns,message) { const row=node("tr"), cell=node("td",message,"empty"); cell.colSpan=columns; row.append(cell); body.append(row); }
  function renderSummary(scoped) {
    const ids=new Set(scoped.map(run => run.run_id)); const rows=summaries.filter(summary => ids.has(summary.run_id)); const body=el("summary-body"); body.replaceChildren(); el("summary-count").textContent=rows.length+" runs";
    rows.forEach(summary => { const row=node("tr"), source=node("td"); source.append(node("div",summary.source),node("div",summary.run_id,"cell-sub")); const conditions=node("td"); conditions.append(node("div",fmt(summary.conditions.vin_v,3," V in")+" / "+fmt(summary.conditions.vout_v,3," V out")),node("div",conditionText(summary.conditions,false),"cell-sub")); row.append(source,conditions);
      const values=[fmt(summary.points,0),fmt(summary.peak_efficiency_pct,3,"%"),fmt(summary.peak_load_a,4," A"),fmt(summary.load_min_a,4)+"–"+fmt(summary.load_max_a,4," A"),fmt(summary.vout_mean_v,6," V"),signed(summary.load_regulation_positive_pct),signed(summary.load_regulation_negative_pct),fmt(summary.load_regulation_span_pct,4,"%")]; values.forEach((value,index) => row.append(node("td",value,index===1 ? "numeric emphasis" : "numeric"))); body.append(row); });
    if(!rows.length) emptyRow(body,10,"No run summaries match this view.");
  }
  function renderLine() {
    const rows=lineEntries.filter(entry => { const c=entry.conditions || {}; return filterDefs.every(([id,key]) => !el(id).value || (key==="vin_v" ? (entry.vin_values_v || []).some(v => String(v)===el(id).value) : String(c[key])===el(id).value)) && (el("mixed").checked || groupKey(c)===state.group) && queryMatches(entry); });
    const body=el("line-body"); body.replaceChildren(); el("line-count").textContent=rows.length+" checks";
    rows.forEach(entry => { const row=node("tr"), conditions=node("td"); conditions.append(node("div",conditionText(entry.conditions || {},false),"cell-sub")); row.append(conditions,node("td",fmt(entry.load_a,4," A"),"numeric"),node("td",(entry.vin_values_v || []).map(v => fmt(v,3," V")).join(" / ") || "—"),node("td",(entry.vout_values_v || []).map(v => fmt(v,6," V")).join(" / ") || "—")); const ok=entry.status==="ok"; row.append(node("td",ok ? signed(entry.positive_pct) : "—","numeric"),node("td",ok ? signed(entry.negative_pct) : "—","numeric"),node("td",ok ? fmt(entry.span_pct,4,"%") : "—","numeric")); const status=node("td"); status.append(node("div",ok ? (entry.interpolated ? "Linearly interpolated sweep" : "Exact measured sweep") : (entry.status || "Unavailable"),ok ? "emphasis" : undefined)); if(!ok) status.append(node("div",entry.message || "This sweep cannot be evaluated.","cell-sub")); if(entry.sources && entry.sources.length) status.append(node("div",entry.sources.join(" · "),"cell-sub")); row.append(status); body.append(row); });
    if(!rows.length) emptyRow(body,8,"No line-regulation entries match this view. A sweep requires the same conditions and unambiguous matched loads across distinct input voltages.");
  }
  function renderIssues() {
    const filtered=issues.filter(issue => (!el("severity").value || issue.severity===el("severity").value) && queryMatches(issue)); const list=el("issue-list"); list.replaceChildren(); el("issue-count").textContent=filtered.length+" / "+issues.length+" events";
    filtered.forEach(issue => { const item=node("article",undefined,"issue"), severity=node("span",String(issue.severity || "warning").toUpperCase(),"severity"+(issue.severity==="error" ? " error" : "")), body=node("div",undefined,"issue-body"); const provenance=[issue.source]; if(issue.page != null) provenance.push("page "+issue.page); if(issue.row != null) provenance.push("row "+issue.row); if(issue.field) provenance.push("field "+issue.field); body.append(node("div",issue.code,"issue-code"),node("p",issue.message,"issue-message"),node("div",provenance.join(" · "),"issue-source")); item.append(severity,body); list.append(item); });
    if(!filtered.length) list.append(node("p",issues.length ? "No quality issues match this search and severity." : "No quality issues were reported. This does not constitute device certification.","hint"));
  }
  function updateStatus() { const scoped=selectedRuns(); el("status").textContent=scoped.filter(run => !state.hidden.has(run.run_id)).length+" visible / "+scoped.length+" scoped / "+runs.length+" total runs"; }
  function refresh() {
    refreshGroups(); resetPoint(); const scoped=selectedRuns(); const mixed=el("mixed").checked; el("scope-note").classList.toggle("mixed",mixed);
    el("scope-note").textContent=mixed ? "Mixed conditions - visual inspection only. All matching condition sets are shown; do not infer comparative performance across different samples, channels, nominal outputs, frequencies or modes." : "Comparable view: sample, channel, nominal Vout, frequency and mode are held constant; only Vin may vary. Repeated runs remain separate. " + scoped.length + " matching run(s).";
    document.querySelectorAll("[data-metric]").forEach(button => button.setAttribute("aria-pressed",String(button.dataset.metric===state.metric)));
    drawChart(scoped); renderSummary(scoped); renderLine(); renderIssues(); updateStatus();
  }
  fillFilters();
  ["runs","measurements","warnings","errors"].forEach(key => el("count-"+key).textContent=fmt((data.counts || {})[key],0));
  el("report-meta").textContent="PACKAGE "+(data.package_version || "—")+" / SCHEMA "+(data.schema_version || "—");
  filterDefs.forEach(([id]) => el(id).addEventListener("change",refresh)); el("search").addEventListener("input",refresh); el("mixed").addEventListener("change",refresh); el("log-x").addEventListener("change",refresh); el("severity").addEventListener("change",renderIssues);
  el("comparison-set").addEventListener("change",() => { state.group=el("comparison-set").value; refresh(); });
  document.querySelectorAll("[data-metric]").forEach(button => button.addEventListener("click",() => { state.metric=button.dataset.metric; refresh(); }));
  el("clear-point").addEventListener("click",resetPoint);
  el("reset").addEventListener("click",() => { filterDefs.forEach(([id]) => el(id).value=""); el("search").value=""; el("mixed").checked=false; el("log-x").checked=false; el("severity").value=""; state.metric="efficiency"; state.group=""; state.hidden.clear(); refresh(); });
  refresh();
})();
</script>
</body>
</html>
"""
