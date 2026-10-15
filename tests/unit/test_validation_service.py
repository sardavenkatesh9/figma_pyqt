"""Tests for validation service."""

from __future__ import annotations

from pathlib import Path

from helpers import (
    FIXTURE,
)

from figma_to_pyside6.adapters.figma_json import load_figma_document
from figma_to_pyside6.application.conversion_service import convert_document
from figma_to_pyside6.application.validation_service import (
    has_failures,
    validate_generated_project,
)


def test_validation_service_detects_problems(tmp_path: Path) -> None:

    convert_document(load_figma_document(FIXTURE), output_dir=tmp_path)
    assert not has_failures(validate_generated_project(tmp_path))

    (tmp_path / "src" / "ui" / "pages" / "login_page.py").unlink()
    (tmp_path / "src" / "ui" / "broken.py").write_text("def (:\n", encoding="utf-8")
    statuses = {c["id"]: c["status"] for c in validate_generated_project(tmp_path)["checks"]}

    assert statuses["GEN-003"] == "FAIL"
    assert statuses["GEN-004"] == "FAIL"
    (tmp_path / "generation_manifest.json").unlink()
    assert validate_generated_project(tmp_path)["checks"][1]["status"] == "WARN"
