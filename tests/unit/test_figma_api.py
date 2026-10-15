"""Tests for figma api."""

from __future__ import annotations

import pytest
from helpers import (
    make_frame,
)

from figma_to_pyside6.adapters.figma_api import (
    build_files_request,
    document_from_response,
    extract_figma_file_key,
    extract_figma_node_id,
)


@pytest.mark.parametrize(
    ("link", "key"),
    [
        ("https://www.figma.com/design/AbC123/Name", "AbC123"),
        ("https://figma.com/file/key_-9/Name?node-id=1-2", "key_-9"),
        ("  https://www.figma.com/design/AbC123  ", "AbC123"),
    ],
)
def test_file_key_extraction(link: str, key: str) -> None:
    assert extract_figma_file_key(link) == key


@pytest.mark.parametrize(
    ("link", "message"),
    [
        ("http://www.figma.com/design/AbC/x", "HTTPS"),
        ("https://evil.com/design/AbC/x", "HTTPS"),
        ("https://www.figma.com/proto/AbC/x", "design or file"),
        ("https://www.figma.com/design", "design or file"),
        ("https://www.figma.com/design/bad$key/x", "valid file key"),
        ("not a url", "HTTPS"),
    ],
)
def test_file_key_rejections(link: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        extract_figma_file_key(link)


def test_node_id_extraction() -> None:
    assert extract_figma_node_id("https://www.figma.com/design/A/x") is None
    assert extract_figma_node_id("https://www.figma.com/design/A/x?node-id=12-34") == "12:34"
    assert extract_figma_node_id("https://www.figma.com/design/A/x?node-id=12:34") == "12:34"
    with pytest.raises(ValueError, match="invalid node id"):
        extract_figma_node_id("https://www.figma.com/design/A/x?node-id=abc")


def test_build_files_request_for_file_and_node() -> None:

    assert build_files_request("K", None) == (
        "https://api.figma.com/v1/files/K",
        [("depth", "4")],
    )
    assert build_files_request("K", "1:2") == (
        "https://api.figma.com/v1/files/K/nodes",
        [("ids", "1:2"), ("depth", "3")],
    )


def test_document_from_response_variants() -> None:

    whole = {"name": "F", "document": {"children": [make_frame("A")]}}
    assert [f.name for f in document_from_response(whole, None, "link").frames] == ["A"]

    node = {"nodes": {"1:2": {"document": {"name": "Sec", "children": [make_frame("B")]}}}}
    document = document_from_response(node, "1:2", "link")
    assert (document.name, [f.name for f in document.frames]) == ("Sec", ["B"])

    with pytest.raises(ValueError, match="could not be found"):
        document_from_response(node, "9:9", "link")


def test_extract_figma_node_id_from_link():
    assert (
        extract_figma_node_id("https://www.figma.com/design/AbC123/Mockup?node-id=4431-19072")
        == "4431:19072"
    )
