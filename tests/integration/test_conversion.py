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


def test_generator_builds_widgets_from_figma_layers(tmp_path: Path) -> None:
    frame = make_frame(
        children=[
            {
                "id": "1",
                "type": "TEXT",
                "name": "Title",
                "characters": "Hi",
                "x": 5,
                "y": 6,
                "width": 40,
                "height": 14,
            },
            {
                "id": "2",
                "type": "INSTANCE",
                "name": "Go",
                "x": 0,
                "y": 30,
                "width": 30,
                "height": 12,
            },
            {
                "id": "3",
                "type": "VECTOR",
                "name": "Icon",
                "x": 50,
                "y": 50,
                "width": 8,
                "height": 8,
            },
            {
                "id": "4",
                "type": "GROUP",
                "name": "Box",
                "x": 20,
                "y": 60,
                "width": 50,
                "height": 20,
                "children": [
                    {
                        "id": "5",
                        "type": "TEXT",
                        "name": "Inner",
                        "x": 22,
                        "y": 62,
                        "width": 30,
                        "height": 14,
                    }
                ],
            },
        ]
    )
    result = convert_document(make_document(frame), output_dir=tmp_path)
    source = page_source(tmp_path)

    assert 'text(canvas, "Hi", 5, ' in source  # characters preferred over the layer name
    assert "box(canvas, 0, 30, 30, 12," in source  # an instance is a box, not a push button
    assert "QPushButton" not in source and "QLabel" not in source
    assert "FRAME_SIZE = (100, 200)" in source
    assert 'text(n2, "Inner"' in source or 'text(canvas, "Inner"' in source
    assert "image(" not in source  # the vector needs an exported image that was not supplied
    assert any("1 vector/image layer(s) were left out" in w for w in result.warnings)


def test_generator_keeps_negative_offsets_but_drops_layers_outside_the_frame(
    tmp_path: Path,
) -> None:
    frame = make_frame(
        x=100,
        y=100,
        children=[
            {
                "id": "1",
                "type": "RECTANGLE",
                "name": "peeks",
                "x": 90,
                "y": 95,
                "width": 30,
                "height": 30,
            },
            {
                "id": "2",
                "type": "RECTANGLE",
                "name": "outside",
                "x": 10,
                "y": 10,
                "width": 5,
                "height": 5,
            },
        ],
    )
    convert_document(make_document(frame), output_dir=tmp_path)
    source = page_source(tmp_path)

    assert "box(canvas, -10, -5, 30, 30," in source  # B5: no clamping of partial overlaps
    assert "# outside" not in source  # fully outside the frame: nothing to draw


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
                "children": [{"id": "e", "type": "STICKY", "name": "Dot"}],
            }
        ],
    )

    result = convert_document(make_document(frame), output_dir=tmp_path)

    assert result.warnings == ["Home / Box / Dot: Unsupported Figma node type: STICKY"]


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


def test_convert_document_writes_identical_images_once(tmp_path: Path) -> None:
    from helpers import raw_node, tiny_png

    from figma_to_pyside6.adapters.figma_json import parse_frame
    from figma_to_pyside6.application.raster import asset_filename
    from figma_to_pyside6.domain.models import FigmaDocument

    frame = parse_frame(
        raw_node(
            "FRAME",
            "F",
            0,
            0,
            100,
            100,
            id="1:1",
            children=[
                raw_node("VECTOR", f"v{i}", i * 12, 0, 10, 10, id=f"1:v{i}") for i in range(3)
            ],
        )
    )
    same, other = tiny_png(), tiny_png(color="#00ff00")
    assets = {"1:v0": same, "1:v1": same, "1:v2": other}

    result = convert_document(
        FigmaDocument("D", "0:0", [frame]), output_dir=tmp_path, assets=assets
    )

    files = sorted(p.name for p in (tmp_path / "src/ui/assets").glob("*.png"))
    assert files == sorted({asset_filename(same), asset_filename(other)})
    page = page_source(tmp_path, "f")
    assert page.count(asset_filename(same)) == 2 and page.count(asset_filename(other)) == 1
    listed = [p.name for p in result.generated_files if p.suffix == ".png"]
    assert sorted(listed) == files  # the manifest lists each picture once
