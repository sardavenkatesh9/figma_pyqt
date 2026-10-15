from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from figma_to_pyside6.adapters.figma_json import load_figma_document, parse_figma_document
from figma_to_pyside6.application.conversion_service import convert_document

FIXTURE = Path(__file__).parent / "fixtures" / "figma_json" / "sample_figma.json"


def test_root_main_launches_cli_inspect():
    root_main = Path(__file__).parents[1] / "main.py"
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


def test_load_figma_document_parses_frames():
    document = load_figma_document(FIXTURE)

    assert document.name == "Sample Screen"
    assert len(document.frames) == 2
    assert {frame.name for frame in document.frames} == {"Login", "Dashboard"}


def test_parse_figma_api_document_finds_frames_under_pages():
    payload = {
        "name": "API file",
        "document": {
            "name": "Document",
            "children": [
                {
                    "id": "page:1",
                    "type": "CANVAS",
                    "name": "Page 1",
                    "children": [
                        {
                            "id": "frame:1",
                            "type": "FRAME",
                            "name": "Screen",
                            "width": 320,
                            "height": 640,
                        }
                    ],
                }
            ],
        },
    }

    document = parse_figma_document(payload)

    assert document.name == "API file"
    assert [frame.name for frame in document.frames] == ["Screen"]


def test_parse_figma_section_can_limit_to_direct_frames():
    payload = {
        "name": "Final screens",
        "document": {
            "name": "Final screens",
            "children": [
                {
                    "id": "frame:1",
                    "type": "FRAME",
                    "name": "Screen",
                    "absoluteBoundingBox": {"x": 0, "y": 0, "width": 1200, "height": 800},
                    "children": [{"id": "nested:1", "type": "FRAME", "name": "Nested"}],
                },
                {
                    "id": "group:1",
                    "type": "GROUP",
                    "name": "Internal",
                    "children": [{"id": "nested:2", "type": "FRAME", "name": "Internal frame"}],
                },
            ],
        },
    }

    document = parse_figma_document(payload, recurse_frames=False)

    assert [frame.name for frame in document.frames] == ["Screen"]
    assert (document.frames[0].width, document.frames[0].height) == (1200, 800)


def test_convert_document_creates_runnable_project(tmp_path):
    document = load_figma_document(FIXTURE)
    result = convert_document(document, project_name="SampleApp", output_dir=tmp_path)
    main_file = tmp_path / "main.py"

    assert result.generated_files
    assert main_file.exists()
    assert (tmp_path / "src" / "ui" / "styles" / "main.qss").exists()
    generated_source = main_file.read_text(encoding="utf-8")
    compile(generated_source, str(main_file), "exec")
    assert "QMainWindow" in generated_source
    assert 'for screen_name in ["Login", "Dashboard"]:' in generated_source
    assert "document.frames" not in generated_source
