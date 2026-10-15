"""Tests for figma json."""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import (
    FIXTURE,
    make_document,
    make_frame,
)

from figma_to_pyside6.adapters.figma_json import load_figma_document, parse_figma_document
from figma_to_pyside6.domain.models import FigmaFrame


def test_parser_reads_node_fields_and_fill_color() -> None:
    login = load_figma_document(FIXTURE).frames[0]
    text, button = login.children

    assert (login.node_id, login.width, login.height) == ("frame-1", 360, 640)
    assert (text.type, text.x, text.y, text.width, text.height) == ("TEXT", 32, 48, 160, 40)
    assert text.fill_color == (0.1, 0.1, 0.1)
    assert button.component_id == "comp-1"
    assert button.fill_color is None


def test_parser_uses_bounding_box_and_rounds_floats() -> None:
    frame = {
        "id": "f",
        "type": "FRAME",
        "name": "F",
        "absoluteBoundingBox": {"x": 10.9, "y": 5.2, "width": 99.9, "height": 50.5},
    }
    parsed = make_document(frame).frames[0]

    assert (parsed.x, parsed.y, parsed.width, parsed.height) == (
        11,
        5,
        100,
        50,
    )  # B5: rounded, not truncated


def test_parser_collects_characters_for_text_nodes() -> None:
    frame = make_frame(children=[{"id": "t", "type": "TEXT", "name": "n", "characters": "Hello"}])

    assert make_document(frame).frames[0].children[0].characters == "Hello"


def test_parser_warns_on_unsupported_node_and_stray_layout() -> None:
    frame = make_frame(
        children=[
            {"id": "a", "type": "STICKY", "name": "e"},
            {"id": "b", "type": "TEXT", "name": "t", "layoutMode": "HORIZONTAL"},
        ]
    )
    ellipse, text = make_document(frame).frames[0].children

    assert ellipse.warnings == ["Unsupported Figma node type: STICKY"]
    assert text.warnings == ["Layout metadata on unsupported node: TEXT"]


def test_parser_does_not_recurse_into_frames_inside_frames() -> None:
    frame = make_frame(children=[{"id": "n", "type": "FRAME", "name": "Nested"}])

    document = make_document(frame)

    assert [f.name for f in document.frames] == ["Home"]
    assert document.frames[0].children[0].name == "Nested"


def test_parser_defaults_when_ids_and_names_missing() -> None:
    document = parse_figma_document(
        {"document": {"children": [{"type": "FRAME"}]}}, source="dir/my_file.json"
    )

    assert document.name == "my_file"
    assert (document.frames[0].node_id, document.frames[0].name) == ("unknown", "Unnamed")


def test_parser_without_frames_raises() -> None:
    with pytest.raises(ValueError, match="No FRAME nodes"):
        parse_figma_document({"document": {"children": [{"type": "TEXT"}]}}, source="x.json")


def test_loader_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        load_figma_document(Path("does/not/exist.json"))


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


def test_frame_summary_is_shared_by_inspect_and_manifest() -> None:
    frame = load_figma_document(FIXTURE).frames[0]

    assert frame.summary() == {"id": "frame-1", "name": "Login", "width": 360, "height": 640}


def test_frame_defaults() -> None:
    frame = FigmaFrame(node_id="1", name="n", type="FRAME")

    assert frame.is_frame
    assert frame.children == [] and frame.warnings == []
    assert frame.characters is None


def test_only_solid_fills_provide_a_color() -> None:
    frame = make_frame(
        children=[
            {"id": "a", "type": "TEXT", "name": "g", "fills": [{"type": "GRADIENT_LINEAR"}]},
            {
                "id": "b",
                "type": "TEXT",
                "name": "s",
                "fills": [
                    {"type": "IMAGE"},
                    {"type": "SOLID", "color": {"r": 1, "g": 0.5}},
                ],
            },
            {"id": "c", "type": "TEXT", "name": "none"},
        ]
    )

    gradient, solid, none = make_document(frame).frames[0].children

    assert gradient.fill_color is None
    assert solid.fill_color == (1.0, 0.5, 0.0)  # missing channel defaults to 0
    assert none.fill_color is None
