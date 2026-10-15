"""Tests for cli."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from helpers import (
    FIXTURE,
)

from figma_to_pyside6.__main__ import build_parser, main
from figma_to_pyside6.adapters.figma_json import load_figma_document
from figma_to_pyside6.application.conversion_service import convert_document


def test_parser_rejects_unknown_subcommand() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["bogus"])


def test_cli_inspect_outputs_frames(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", str(FIXTURE)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["name"] == "Sample Screen"
    assert payload["frames"][0] == {"id": "frame-1", "name": "Login", "width": 360, "height": 640}


def test_cli_convert_writes_project(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "out"

    assert main(["convert", str(FIXTURE), "--project-name", "X", "--output-dir", str(out)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["project_name"] == "X"
    assert (out / "src" / "ui" / "pages" / "login_page.py").exists()
    assert str(out / "main.py") in payload["generated_files"]


def test_cli_validate_document_and_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate", str(FIXTURE)]) == 0
    assert "frames=2" in capsys.readouterr().out
    assert main(["validate", str(tmp_path)]) == 2
    assert "missing" in capsys.readouterr().out
    convert_document(load_figma_document(FIXTURE), output_dir=tmp_path)
    assert main(["validate", str(tmp_path)]) == 0


def test_cli_report_document_manifest_and_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["report", str(FIXTURE)]) == 0
    assert "frames: 2" in capsys.readouterr().out
    assert main(["report", str(tmp_path)]) == 1
    assert "No manifest" in capsys.readouterr().out
    convert_document(load_figma_document(FIXTURE), project_name="Rep", output_dir=tmp_path)
    assert main(["report", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["project_name"] == "Rep"


def test_cli_without_command_and_gui_command_launch_gui(monkeypatch: pytest.MonkeyPatch) -> None:
    launched: list[bool] = []
    monkeypatch.setattr("figma_to_pyside6.__main__.launch_gui", lambda: launched.append(True))

    assert main([]) == 0
    assert main(["gui"]) == 0
    assert launched == [True, True]


def test_cli_missing_input_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        main(["inspect", "nope.json"])


def test_cli_validate_fails_on_unparseable_project(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    convert_document(load_figma_document(FIXTURE), output_dir=tmp_path)
    (tmp_path / "src" / "ui" / "broken.py").write_text("def (:\n", encoding="utf-8")

    assert main(["validate", str(tmp_path)]) == 2
    assert "GEN-004" in capsys.readouterr().out


def test_root_main_launches_cli_inspect():
    root_main = Path(__file__).parents[2] / "main.py"
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, str(root_main), "inspect", str(FIXTURE)],
        cwd=root_main.parent,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["frame_count"] == 2
