"""Deterministic batch orchestration with per-file failure isolation."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from powerbench.models import Batch, Issue, ParseError, Run, Settings
from powerbench.parsers import parse_pdf, parse_table_json

SUPPORTED = {".pdf", ".json"}


def discover_inputs(paths: Iterable[Path], *, recursive: bool = False) -> tuple[Path, ...]:
    """Resolve explicit files/folders; recursive traversal is always opt-in."""
    found: dict[Path, None] = {}
    for path in paths:
        if not path.exists():
            raise ParseError(f"Input does not exist: {path.name}")
        if path.is_symlink():
            raise ParseError(f"Symbolic-link inputs are not followed: {path.name}")
        if path.is_file():
            if path.suffix.lower() not in SUPPORTED:
                raise ParseError(f"Unsupported input extension: {path.suffix}")
            found[path.resolve()] = None
        else:
            candidates = path.rglob("*") if recursive else path.iterdir()
            for candidate in candidates:
                if (
                    candidate.is_file()
                    and not candidate.is_symlink()
                    and candidate.suffix.lower() in SUPPORTED
                ):
                    found[candidate.resolve()] = None
    return tuple(sorted(found, key=lambda item: item.as_posix().casefold()))


def process_batch(paths: Iterable[Path], settings: Settings | None = None) -> Batch:
    settings = settings or Settings()
    runs: list[Run] = []
    issues: list[Issue] = []
    seen: set[str] = set()
    files = tuple(paths)
    failed = skipped = 0
    # Avoid absolute machine paths in exported files while disambiguating equal basenames.
    occurrences: dict[str, int] = {}
    for path in files:
        occurrences[path.name] = occurrences.get(path.name, 0) + 1
    for index, path in enumerate(files, 1):
        source = path.name if occurrences[path.name] == 1 else f"input-{index}/{path.name}"
        try:
            parser = parse_pdf if path.suffix.lower() == ".pdf" else parse_table_json
            run = parser(path, settings, source=source)
            # Same bytes under a different nominal filename can mean a metadata mistake.
            # Do not discard those runs as duplicates; require both content AND conditions.
            key = f"{run.sha256}:{run.conditions.identity}"
            if key in seen:
                skipped += 1
                issues.append(
                    Issue(
                        "duplicate_input",
                        "Identical content and conditions already processed; skipped.",
                        source,
                    )
                )
                continue
            seen.add(key)
            runs.append(run)
        except (ParseError, OSError) as exc:
            failed += 1
            issues.append(Issue("file_parse_failed", str(exc), source, severity="error"))
    return Batch(tuple(runs), tuple(issues), len(files), failed, skipped)
