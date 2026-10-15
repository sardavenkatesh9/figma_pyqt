"""Tests for conversion."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from helpers import (
    FIXTURE,
    make_document,
    make_frame,
    page_source,
)

from figma_to_pyside6.adapters.figma_json import load_figma_document, parse_figma_document
from figma_to_pyside6.application.conversion_service import convert_document


def test_generator_maps_node_types_to_widgets(tmp_path: Path) -> None:
    frame = make_frame(
        children=[
            {"id": "1", "type": "TEXT", "name": "Title", "characters": "Hi", "x": 5, "y": 6},
            {"id": "2", "type": "INSTANCE", "name": "Go", "width": 10, "height": 10},
            {"id": "3", "type": "VECTOR", "name": "Icon"},
            {
                "id": "4",
                "type": "GROUP",
                "name": "Box",
                "children": [{"id": "5", "type": "TEXT", "name": "Inner"}],
            },
        ]
    )
    convert_document(make_document(frame), output_dir=tmp_path)
    source = page_source(tmp_path)

    assert 'QLabel("Hi", canvas)' in source  # characters preferred over name
    assert 'QPushButton("Go", canvas)' in source
    assert "= QFrame(canvas)" in source
    assert source.count('setObjectName("card")') == 1  # only frames that have children
    assert 'QLabel("Inner", node_4)' in source  # nested child parented to its group
    assert "FRAME_SIZE = (100, 200)" in source
    assert "setGeometry(5, 6, 1, 1)" in source  # quirk: zero size is bumped to 1


def test_generator_keeps_negative_child_offsets(tmp_path: Path) -> None:
    child = {"id": "1", "type": "TEXT", "name": "t", "x": 40, "y": 90, "width": 5, "height": 5}
    frame = make_frame(x=100, y=100, children=[child])
    convert_document(make_document(frame), output_dir=tmp_path)

    assert "setGeometry(-60, -10, 5, 5)" in page_source(tmp_path)  # B5: no clamping


def test_generator_escapes_hostile_frame_names(tmp_path: Path) -> None:
    name = 'Evil"""\n\\ ; __import__("os")'
    convert_document(make_document(make_frame(name)), output_dir=tmp_path)

    for path in tmp_path.rglob("*.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    pages = {p.name for p in (tmp_path / "src" / "ui" / "pages").glob("*_page.py")}
    assert pages == {"evil_import_os_page.py", "base_page.py"}


def test_generator_manifest_and_validation_report(tmp_path: Path) -> None:
    document = load_figma_document(FIXTURE)
    result = convert_document(document, project_name="Demo", output_dir=tmp_path)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    report = json.loads(result.validation_report_path.read_text(encoding="utf-8"))

    assert manifest["project_name"] == "Demo"
    assert manifest["document_name"] == "Sample Screen"
    assert {f["name"] for f in manifest["frames"]} == {"Login", "Dashboard"}
    listed = {entry["path"] for entry in manifest["files"]}
    assert {"main.py", "src/ui/main_window.py", "src/ui/styles/tokens.qss"} <= listed
    assert all(len(entry["sha256"]) == 64 for entry in manifest["files"])
    assert [(c["id"], c["status"]) for c in report["checks"]] == [
        ("GEN-001", "PASS"),
        ("GEN-002", "PASS"),
        ("GEN-003", "PASS"),
        ("GEN-004", "PASS"),
    ]
    assert result.warnings == []


def test_generated_project_is_maximized_and_has_no_qss_import(tmp_path: Path) -> None:
    convert_document(load_figma_document(FIXTURE), output_dir=tmp_path)

    assert "showMaximized()" in (tmp_path / "main.py").read_text(encoding="utf-8")
    window = (tmp_path / "src" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert "tokens.qss" in window
    qss = (tmp_path / "src" / "ui" / "styles" / "main.qss").read_text(encoding="utf-8")
    assert "@import" not in qss


def test_generator_default_output_dir_is_cwd_generated_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = convert_document(load_figma_document(FIXTURE))

    assert result.output_dir == tmp_path / "generated_project"
    assert (result.output_dir / "main.py").exists()


def test_regeneration_keeps_user_owned_files_and_rewrites_generated_ones(tmp_path: Path) -> None:
    """Audit B1 (fixed): README/pyproject/QSS survive; marker-bearing files are refreshed."""
    document = load_figma_document(FIXTURE)
    convert_document(document, output_dir=tmp_path)
    readme = tmp_path / "README.md"
    qss = tmp_path / "src" / "ui" / "styles" / "main.qss"
    page = tmp_path / "src" / "ui" / "pages" / "login_page.py"
    readme.write_text("mine", encoding="utf-8")
    qss.write_text("/* mine */", encoding="utf-8")
    original_page = page.read_text(encoding="utf-8")
    page.write_text(original_page + "# tampered\n", encoding="utf-8")

    result = convert_document(document, output_dir=tmp_path)

    assert readme.read_text(encoding="utf-8") == "mine"
    assert qss.read_text(encoding="utf-8") == "/* mine */"
    assert page.read_text(encoding="utf-8") == original_page
    assert result.warnings == []


def test_generated_file_without_marker_is_treated_as_hand_written(tmp_path: Path) -> None:
    document = load_figma_document(FIXTURE)
    convert_document(document, output_dir=tmp_path)
    page = tmp_path / "src" / "ui" / "pages" / "login_page.py"
    page.write_text("class LoginPage: ...\n", encoding="utf-8")

    result = convert_document(document, output_dir=tmp_path)

    assert page.read_text(encoding="utf-8") == "class LoginPage: ...\n"
    assert any("login_page.py" in warning for warning in result.warnings)
    assert page in result.generated_files


def test_stale_cleanup_keeps_pages_without_generator_marker(tmp_path: Path) -> None:
    document = load_figma_document(FIXTURE)
    convert_document(document, output_dir=tmp_path)
    pages = tmp_path / "src" / "ui" / "pages"
    (pages / "custom_page.py").write_text("# hand written\n", encoding="utf-8")
    document.frames = document.frames[:1]

    convert_document(document, output_dir=tmp_path)

    assert (pages / "custom_page.py").exists()
    assert not (pages / "dashboard_page.py").exists()


def test_b6_parser_warnings_reach_conversion_result(tmp_path: Path) -> None:
    """B6: unsupported nodes are reported instead of silently becoming plain frames."""
    frame = make_frame(
        "Home",
        children=[
            {
                "id": "g",
                "type": "GROUP",
                "name": "Box",
                "children": [{"id": "e", "type": "ELLIPSE", "name": "Dot"}],
            }
        ],
    )

    result = convert_document(make_document(frame), output_dir=tmp_path)

    assert result.warnings == ["Home / Box / Dot: Unsupported Figma node type: ELLIPSE"]


def test_convert_document_creates_one_page_per_frame(tmp_path):
    document = load_figma_document(FIXTURE)
    result = convert_document(document, project_name="SampleApp", output_dir=tmp_path)
    pages_dir = tmp_path / "src" / "ui" / "pages"

    assert result.generated_files
    assert (tmp_path / "src" / "ui" / "styles" / "main.qss").exists()
    assert {path.name for path in pages_dir.glob("*_page.py")} == {
        "login_page.py",
        "dashboard_page.py",
        "base_page.py",
    }
    for source_file in tmp_path.rglob("*.py"):
        compile(source_file.read_text(encoding="utf-8"), str(source_file), "exec")

    login = (pages_dir / "login_page.py").read_text(encoding="utf-8")
    assert "class LoginPage(BasePage)" in login
    assert "Welcome" in login
    assert "Overview" not in login
    assert "Overview" in (pages_dir / "dashboard_page.py").read_text(encoding="utf-8")
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert [frame["page"] for frame in manifest["frames"]] == [
        "src/ui/pages/login_page.py",
        "src/ui/pages/dashboard_page.py",
    ]


def test_regeneration_removes_pages_of_deselected_frames(tmp_path):
    document = load_figma_document(FIXTURE)
    convert_document(document, output_dir=tmp_path)
    document.frames = document.frames[:1]
    convert_document(document, output_dir=tmp_path)

    pages_dir = tmp_path / "src" / "ui" / "pages"
    assert (pages_dir / "login_page.py").exists()
    assert not (pages_dir / "dashboard_page.py").exists()


def test_duplicate_frame_names_get_unique_pages(tmp_path):
    payload = {
        "name": "Dupes",
        "document": {
            "children": [
                {"id": "1", "type": "FRAME", "name": "Home Screen", "width": 10, "height": 10},
                {"id": "2", "type": "FRAME", "name": "Home-Screen", "width": 10, "height": 10},
                {"id": "3", "type": "FRAME", "name": "404", "width": 10, "height": 10},
            ]
        },
    }
    convert_document(parse_figma_document(payload), output_dir=tmp_path)

    names = {path.name for path in (tmp_path / "src" / "ui" / "pages").glob("*_page.py")}
    assert names == {
        "home_screen_page.py",
        "home_screen_2_page.py",
        "screen_404_page.py",
        "base_page.py",
    }
