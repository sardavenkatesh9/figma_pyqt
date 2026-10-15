"""Tests for deciding which Figma layers are exported as images."""

from __future__ import annotations

import re
from typing import Any

import pytest
from helpers import raw_node, solid

from figma_to_pyside6.adapters.figma_json import parse_frame
from figma_to_pyside6.application.raster import (
    MAX_RASTER_SIDE,
    asset_filename,
    collect_raster_nodes,
    needs_raster,
    renderable_children,
    too_large,
)
from figma_to_pyside6.domain.models import FigmaFrame, FigmaNode


def _frame(*children: dict[str, Any]) -> FigmaFrame:
    return parse_frame(
        raw_node("FRAME", "Page", 0, 0, 400, 300, id="1:1", children=list(children)), "Section"
    )


def _only(child: dict[str, Any]) -> FigmaNode:
    return _frame(child).children[0]


def test_asset_filename_is_derived_from_the_content() -> None:
    name = asset_filename(b"icon-bytes")

    assert re.fullmatch(r"fig_[0-9a-f]{16}\.png", name)  # safe on every file system
    assert name == asset_filename(b"icon-bytes")  # same content, same file
    assert name != asset_filename(b"other-bytes")


@pytest.mark.parametrize("kind", ["VECTOR", "BOOLEAN_OPERATION", "STAR", "LINE", "REGULAR_POLYGON"])
def test_vector_like_types_are_exported(kind: str) -> None:
    assert needs_raster(_only(raw_node(kind, "v", 0, 0, 10, 10)))


def test_plain_boxes_and_text_are_built_from_widgets() -> None:
    assert not needs_raster(_only(raw_node("RECTANGLE", "r", 0, 0, 10, 10, fills=[solid(1, 0, 0)])))
    assert not needs_raster(_only(raw_node("ELLIPSE", "e", 0, 0, 10, 10)))
    assert not needs_raster(_only(raw_node("TEXT", "t", 0, 0, 10, 10, characters="x")))


def test_bitmap_fill_rotation_and_masks_are_exported() -> None:
    image_fill = {"type": "IMAGE", "imageRef": "abc", "scaleMode": "FILL"}
    assert needs_raster(_only(raw_node("RECTANGLE", "img", 0, 0, 10, 10, fills=[image_fill])))
    assert needs_raster(_only(raw_node("RECTANGLE", "rot", 0, 0, 10, 10, rotation=0.5)))
    mask = raw_node("RECTANGLE", "m", 0, 0, 10, 10, isMask=True)
    inner = raw_node("RECTANGLE", "i", 0, 0, 10, 10)
    assert needs_raster(_only(raw_node("GROUP", "masked", 0, 0, 10, 10, children=[mask, inner])))


def test_icon_containers_are_exported_whole_but_mixed_ones_are_not() -> None:
    icon = raw_node("FRAME", "Icon", 0, 0, 16, 16, children=[raw_node("VECTOR", "v", 0, 0, 16, 16)])
    assert needs_raster(_only(icon))

    mixed = raw_node(
        "FRAME",
        "Button",
        0,
        0,
        80,
        30,
        children=[
            raw_node("VECTOR", "v", 0, 0, 10, 10),
            raw_node("TEXT", "t", 20, 0, 50, 20, characters="Go"),
        ],
    )
    assert not needs_raster(_only(mixed))  # text stays real text; only the vector is exported


def test_empty_container_is_not_exported() -> None:
    assert not needs_raster(_only(raw_node("FRAME", "empty", 0, 0, 10, 10)))


def test_hidden_children_do_not_make_a_container_an_icon() -> None:
    hidden_text = raw_node("TEXT", "t", 0, 0, 10, 10, characters="x", visible=False)
    icon = raw_node(
        "FRAME", "f", 0, 0, 16, 16, children=[raw_node("VECTOR", "v", 0, 0, 16, 16), hidden_text]
    )

    assert needs_raster(_only(icon))


def test_renderable_children_skip_hidden_and_fully_outside_nodes() -> None:
    frame = _frame(
        raw_node("RECTANGLE", "visible", 10, 10, 20, 20),
        raw_node("RECTANGLE", "hidden", 10, 10, 20, 20, visible=False),
        raw_node("RECTANGLE", "right-of-page", 500, 10, 20, 20),
        raw_node("RECTANGLE", "below-page", 10, 400, 20, 20),
        raw_node("RECTANGLE", "overlaps-edge", 390, 290, 50, 50),
    )

    assert [c.name for c in renderable_children(frame)] == ["visible", "overlaps-edge"]


def test_collect_raster_nodes_stops_at_exported_layers() -> None:
    icon = raw_node(
        "FRAME",
        "Icon",
        0,
        0,
        16,
        16,
        id="2:1",
        children=[raw_node("VECTOR", "v", 0, 0, 16, 16, id="2:2")],
    )
    card = raw_node(
        "FRAME",
        "Card",
        0,
        0,
        100,
        100,
        children=[
            icon,
            raw_node("VECTOR", "loose", 30, 30, 5, 5, id="2:3"),
            raw_node("TEXT", "label", 40, 40, 30, 12, characters="Hi"),  # keeps the card mixed
        ],
    )

    ids = [n.node_id for n in collect_raster_nodes(_frame(card))]

    assert ids == ["2:1", "2:3"]  # the icon once (not its inner vector), plus the loose vector


def test_oversized_layers_are_not_requested() -> None:
    huge = _only(raw_node("VECTOR", "huge", 0, 0, MAX_RASTER_SIDE + 1, 10, id="9:9"))

    assert too_large(huge)
    assert (
        collect_raster_nodes(_frame(raw_node("VECTOR", "huge", 0, 0, MAX_RASTER_SIDE + 1, 10)))
        == []
    )
