# Measurement contract and methodology

## 1. What is measured, and what is derived

Each `Run` contains nominal `Conditions`, immutable `Measurement` rows, a safe source identifier and SHA-256 of the source bytes. A row preserves the report's point number, measured quantities, and one-based page/table/row location. Table rows refer to the extracted grid; the text fallback uses text-line rows.

| Quantity | Internal field | Unit |
|---|---|---|
| Output current | `load_a` | A |
| Output voltage | `vout_v` | V |
| Input voltage / current | `vin_v`, `iin_a` | V / A |
| Output / input power | `pout_w`, `pin_w` | W |
| Reported loss | `loss_w` | W |
| Reported efficiency | `efficiency` | fraction, or `None` |
| Nominal frequency | `frequency_khz` | kHz |

The native short headers do not necessarily print physical units. This adapter therefore declares its A/V/W/fraction contract explicitly. Units are not inferred from numeric magnitude. A percent input must opt in through settings; unsupported mA/mV table headers are rejected rather than rescaled silently.

Efficiency is the **reported** value. `efficiency_pct = efficiency × 100` is presentation only. `Pout / Pin` is an optional cross-check when `Pin > 0`; it never overwrites the report. A reported zero at no load remains zero, even if the corresponding rounded `Pin` is zero. Non-finite or missing efficiency is a flagged null. Non-finite required voltage/current/power fields reject the row with an error.

Default consistency tolerances are intentionally configurable: 0.015 absolute efficiency fraction (1.5 percentage points), 0.015 W absolute or 2% relative power difference. They accommodate rounding; they are not instrument uncertainty budgets or universal acceptance limits.

## 2. Load regulation

For all retained output-voltage observations in a run, let `mu = mean(Vout)`:

```text
positive_pct = 100 × (max(Vout) − mu) / mu
negative_pct = 100 × (min(Vout) − mu) / mu
span_pct     = 100 × (max(Vout) − min(Vout)) / mu
```

The negative result stays signed. All three values describe the measured sweep. A one-point sweep has zero observed span, which is not evidence of regulation over a range. Repeated points remain observations; they are not automatically averaged away. The denominator is the **measured mean**, not the nominal setpoint. Do not compare directly with a datasheet whose test procedure or normalization differs.

Peak efficiency ignores null values and reported fractions outside [0, 1], but retains zero. Ties select the lowest measured load, then the point index. No cross-device ranking is inferred.

## 3. Line regulation at a common actual load

A valid Vin comparison holds **sample, channel, nominal Vout, frequency and mode** fixed. It needs at least two distinct nominal input voltages. Timestamps preserve run identity, but do not change the definition of a comparable group.

The available interval is the intersection of all runs' actual measured load ranges:

```text
lower = max(each run's minimum load)
upper = min(each run's maximum load)
```

Default targets are `lower`, `(lower + upper)/2`, and `upper`, deduplicated exactly. They are **not necessarily zero/half/full rated load**. User-specified targets outside this interval produce `out_of_range` records, not extrapolated values.

Within a curve, Vout is linearly interpolated between its neighbouring actual load values. Exact measured points are used directly. Mean-normalized positive/negative/span statistics are then calculated across the input-voltage sweep at that same load. The `interpolated` flag discloses whether any run required interpolation.

Ambiguity is explicit:
- `insufficient_vin`: only one distinct input voltage.
- `ambiguous_replicates`: multiple retained runs at the same nominal Vin; select an explicit input set.
- `ambiguous_loads`: duplicate or near-duplicate actual loads (default absolute tolerance 1e-9 A).
- `no_overlap`: curves have no shared measured load interval.
- `out_of_range`: requested target would require extrapolation.

The same duplicate-load tolerance is used for diagnostics and interpolation. Failed comparisons do not become numeric zero.

## 4. Parsing boundaries

The parser supports a recognized nine-column ATE header, reordered columns, repeated page headers, merged title rows and headerless continuation tables. It processes all pages; a grid-first adapter uses whitespace text as a fallback. A born-digital report is required. OCR, image-only scans, password handling and arbitrary vendor formats are intentionally outside the release scope.

Measurements with invalid required fields are rejected with source/page/table/row diagnostics. Good rows and good files remain available for inspection, but the CLI returns failure for data errors. A header/schema mismatch fails rather than guessing. Equal bytes **and** equal nominal conditions are duplicate inputs; otherwise repeated tests are retained. `--strict` also fails on warnings, including legitimate zero-load warnings.

Filename metadata is the nominal-condition source for native PDFs. Confirm it is correct before interpreting results. The software does not independently authenticate that a report belongs to the sample named in its filename.

## 5. Voltage-log adapter

UTF-16 is detected by its BOM; otherwise the default is UTF-8 with an optional BOM. Other encodings require an explicit setting. The exact metric is in delimiter field 3 and its voltage is in field 4. A, mixed physical quantities, arbitrary trailing text and non-finite values are not accepted as voltages. Explicit `mV` is normalized to V; bare numbers follow the adapter's V convention.

Short lines generate diagnostics. FAIL-marked filenames are skipped unless requested. Tidy output retains file, line and sequence; it does not pretend positional values carry known Vin/load/channel conditions. Wide output requires a complete, explicit, unique list of headers and exactly matching value counts; rejected values prevent positional export.

## 6. Reproducibility, safety and limitations

`results.json` has a schema version; `manifest.json` records effective configuration, source hashes, and generated artifact hashes. HTML/JSON use deterministic serialization. Fonts/rendering, dependency versions and ZIP metadata may change image/workbook bytes across machines; the manifest records the artifact actually created rather than promising cross-platform byte identity.

CSV text with formula prefixes is escaped; numeric negatives remain numbers. Excel input strings are literal, not formulas or hyperlinks. Report data is JSON-escaped against script termination and displayed with `textContent`. The HTML has no CDN, analytics, remote requests or persistence.

Source basenames and all measurements remain in generated reports. They can still be confidential even though machine-specific absolute paths are omitted. Review outputs before sharing. Ignoring PDFs/XLSX/private folders in Git is a safeguard, not a substitute for review.

This is a descriptive software tool, not calibrated metrology, automatic hardware release approval, a thermal/ripple/transient analyzer, or a substitute for an agreed measurement procedure.
