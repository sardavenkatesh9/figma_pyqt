from __future__ import annotations

import json
from pathlib import Path


def validate_generated_project(path: str | Path) -> dict[str, object]:
    project_dir = Path(path)
    checks = []
    main_file = project_dir / "main.py"
    checks.append(
        {"id": "GEN-001", "status": "PASS", "severity": "INFO", "description": "main.py exists"}
        if main_file.exists()
        else {
            "id": "GEN-001",
            "status": "FAIL",
            "severity": "ERROR",
            "description": "main.py missing",
        }
    )
    manifest = project_dir / "generation_manifest.json"
    checks.append(
        {"id": "GEN-002", "status": "PASS", "severity": "INFO", "description": "manifest exists"}
        if manifest.exists()
        else {
            "id": "GEN-002",
            "status": "WARN",
            "severity": "WARNING",
            "description": "manifest missing",
        }
    )
    return {"project_dir": str(project_dir), "checks": checks}


def write_validation_report(path: str | Path, payload: dict[str, object]) -> Path:
    report_path = Path(path) / "validation_report.json"
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return report_path
