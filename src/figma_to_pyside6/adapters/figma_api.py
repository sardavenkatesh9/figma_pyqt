"""Validation and parsing of Figma share links."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

from figma_to_pyside6.adapters.figma_json import parse_figma_document
from figma_to_pyside6.domain.models import FigmaDocument

FIGMA_API_BASE = "https://api.figma.com/v1/files"
# ``depth`` limits how far the REST API traverses the node tree. Per the Figma docs, for
# ``/files/:key`` depth 1 returns pages and depth 2 only the top-level objects of each page,
# i.e. frames *without* children. For ``/files/:key/nodes`` it is counted from the requested
# node. Both depths below reach frame children and grandchildren: deeper nesting is omitted
# from generated pages (keeps responses small and avoids "Request too large").
FIGMA_FILE_DEPTH = 4  # document -> page -> frame -> child -> grandchild
FIGMA_NODE_DEPTH = 3  # section -> frame -> child -> grandchild

_FILE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def extract_figma_file_key(link: str) -> str:
    """Return the file key from a Figma design/file link.

    Raises:
        ValueError: If the link is not an HTTPS figma.com design or file link.
    """
    parsed = urlsplit(link.strip())
    if parsed.scheme != "https" or parsed.hostname not in {"figma.com", "www.figma.com"}:
        raise ValueError("Enter an HTTPS link from figma.com.")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0] not in {"design", "file"}:
        raise ValueError("Use a Figma design or file link.")

    file_key = parts[1]
    if not _FILE_KEY_PATTERN.fullmatch(file_key):
        raise ValueError("The Figma link does not contain a valid file key.")

    return file_key


def extract_figma_node_id(link: str) -> str | None:
    """Return the ``node-id`` query value as ``"1:2"``, or ``None`` if absent.

    Raises:
        ValueError: If the node id is present but malformed.
    """
    node_ids = parse_qs(urlsplit(link.strip()).query).get("node-id", [])
    if not node_ids:
        return None

    node_id = node_ids[0].replace("-", ":", 1)
    if not re.fullmatch(r"\d+:\d+", node_id):
        raise ValueError("The Figma link contains an invalid node id.")
    return node_id


def build_files_request(file_key: str, node_id: str | None) -> tuple[str, list[tuple[str, str]]]:
    """Return the REST URL and query items for a whole file or a single node.

    Args:
        file_key: Key from :func:`extract_figma_file_key`.
        node_id: Node id from :func:`extract_figma_node_id`, or ``None`` for the whole file.
    """
    if node_id is None:
        return f"{FIGMA_API_BASE}/{file_key}", [("depth", str(FIGMA_FILE_DEPTH))]
    return (
        f"{FIGMA_API_BASE}/{file_key}/nodes",
        [("ids", node_id), ("depth", str(FIGMA_NODE_DEPTH))],
    )


def document_from_response(
    payload: dict[str, Any], node_id: str | None, source: str
) -> FigmaDocument:
    """Turn a Figma REST response into a document.

    Args:
        payload: Decoded JSON of ``/files/:key`` or ``/files/:key/nodes``.
        node_id: The node that was requested, or ``None`` for a whole-file response.
        source: Link shown in error messages.

    Raises:
        ValueError: If the requested node is missing or no frames are found.
    """
    if node_id is None:
        return parse_figma_document(payload, source=source)
    entry = payload.get("nodes", {}).get(node_id)
    node = entry.get("document") if entry else None
    if not node:
        raise ValueError("The linked Figma section could not be found.")
    wrapped = {"name": node.get("name"), "document": node}
    return parse_figma_document(wrapped, source=source, recurse_frames=False)
