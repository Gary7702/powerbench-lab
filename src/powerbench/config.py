"""Load a deliberately small TOML configuration, rejecting misspelled keys."""

from __future__ import annotations

import tomllib
from dataclasses import fields
from pathlib import Path
from typing import Any

from powerbench.models import PowerBenchError, Settings


def load_settings(path: Path | None = None) -> Settings:
    if path is None:
        return Settings()
    try:
        with path.open("rb") as stream:
            data: dict[str, Any] = tomllib.load(stream)
        unknown = set(data) - {f.name for f in fields(Settings)}
        if unknown:
            raise ValueError(f"Unknown configuration keys: {', '.join(sorted(unknown))}")
        return Settings(**data)
    except (OSError, TypeError, ValueError) as exc:
        raise PowerBenchError(f"Cannot read configuration {path.name}: {exc}") from exc
