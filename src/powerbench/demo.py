"""Deterministic, purpose-built synthetic fixtures: no real laboratory records.

The simple loss equation is illustrative, not a fitted or predictive converter
model. Every generated file and run is explicitly labelled synthetic.
"""

from __future__ import annotations

import json
from pathlib import Path

from powerbench.models import Conditions, ParseError

DEMO_LOADS = (0.0, 0.025, 0.05, 0.1, 0.2, 0.4, 0.65, 1.0, 1.5, 2.0, 2.5, 3.0)


def demo_documents() -> list[tuple[str, dict[str, object]]]:
    """Eight 12-point curves: 2 channels x 2 input voltages x 2 mode IDs."""
    documents: list[tuple[str, dict[str, object]]] = []
    for channel, nominal_vout in (("1", 3.3), ("2", 1.8)):
        for vin in (8.0, 14.0):
            for mode in ("1", "2"):
                conditions = Conditions("DEMO", channel, vin, nominal_vout, 600.0, mode)
                rows: list[list[object]] = [
                    ["No.", "Io", "Vo", "Vi", "Ii", "Po", "Pi", "Ploss", "Effi"]
                ]
                for point, load in enumerate(DEMO_LOADS, 1):
                    vout = nominal_vout * (1.0015 - 0.001 * load + 0.00003 * (vin - 8))
                    measured_vin = vin + 0.002 * load
                    fixed_loss = (0.065 if mode == "1" else 0.012) + 0.001 * (vin - 8)
                    conduction = (0.095 if mode == "1" else 0.12) * load * load
                    switching = 0.035 * load
                    loss = fixed_loss + conduction + switching
                    pout = load * vout
                    pin = pout + loss
                    iin = pin / measured_vin
                    efficiency = pout / pin
                    # Include one honest invalid-reading fixture, never a fabricated 0.
                    efficiency_cell: object = (
                        "inf"
                        if channel == "2" and vin == 14 and mode == "2" and load == 0
                        else round(efficiency, 6)
                    )
                    rows.append(
                        [
                            point,
                            round(load, 6),
                            round(vout, 6),
                            round(measured_vin, 6),
                            round(iin, 6),
                            round(pout, 6),
                            round(pin, 6),
                            round(loss, 6),
                            efficiency_cell,
                        ]
                    )
                name = f"demo-ch{channel}-vin{vin:g}-mode{mode}.json"
                documents.append(
                    (
                        name,
                        {
                            "schema_version": "1.0",
                            "synthetic": True,
                            "notice": "SYNTHETIC DEMO ONLY. Not measured, fitted, or a product specification.",
                            "conditions": conditions.as_dict(),
                            "tables": [{"page": 1, "rows": rows}],
                        },
                    )
                )
    return documents


def write_demo_inputs(directory: Path) -> tuple[Path, ...]:
    """Write a fresh demonstration directory; refuse existing contents."""
    if directory.exists() and any(directory.iterdir()):
        raise ParseError("Demo input directory is not empty; choose a new output directory.")
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name, document in demo_documents():
        path = directory / name
        path.write_text(
            json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        paths.append(path)
    return tuple(paths)
