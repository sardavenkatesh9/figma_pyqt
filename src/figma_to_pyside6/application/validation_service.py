"""Validate a generated project directory."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
MANIFEST_NAME = "generation_manifest.json"
REPORT_NAME = "validation_report.json"


def _check(check_id: str, ok: bool, description: str, *, fail: str = FAIL) -> dict[str, str]:
    """Build one result row; ``fail`` is the status used when ``ok`` is false."""
    severity = {PASS: "INFO", WARN: "WARNING", FAIL: "ERROR"}
    status = PASS if ok else fail
    return {
        "id": check_id,
        "status": status,
        "severity": severity[status],
        "description": description,
    }


def _load_manifest(path: Path) -> dict[str, Any] | None:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _unparseable_sources(project_dir: Path) -> list[str]:
    bad = []
    for source in sorted(project_dir.rglob("*.py")):
        try:
            ast.parse(source.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            bad.append(source.relative_to(project_dir).as_posix())
    return bad


def validate_generated_project(path: str | Path) -> dict[str, Any]:
    """Run structural checks on a generated project.

    Checks: ``main.py`` exists (GEN-001), manifest exists (GEN-002), every manifest page
    exists (GEN-003), and every Python file parses (GEN-004).

    Returns:
        ``{"project_dir": ..., "checks": [...]}`` where each check has ``id``, ``status``
        (PASS/WARN/FAIL), ``severity`` and ``description``.
    """
    project_dir = Path(path)
    manifest = _load_manifest(project_dir / MANIFEST_NAME)
    missing_pages = [
        frame["page"]
        for frame in (manifest or {}).get("frames", [])
        if not (project_dir / frame["page"]).exists()
    ]
    bad_sources = _unparseable_sources(project_dir)
    checks = [
        _check("GEN-001", (project_dir / "main.py").exists(), "main.py exists"),
        _check("GEN-002", manifest is not None, "manifest exists and is valid", fail=WARN),
        _check("GEN-003", not missing_pages, "one page exists per manifest frame"),
        _check("GEN-004", not bad_sources, "all Python files parse"),
    ]
    return {"project_dir": str(project_dir), "checks": checks}


def has_failures(report: dict[str, Any]) -> bool:
    """Whether any check in ``report`` has status FAIL."""
    return any(check["status"] == FAIL for check in report["checks"])


def write_validation_report(path: str | Path, payload: dict[str, Any]) -> Path:
    """Write ``validation_report.json`` into the project directory."""
    report_path = Path(path) / REPORT_NAME
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return report_path
