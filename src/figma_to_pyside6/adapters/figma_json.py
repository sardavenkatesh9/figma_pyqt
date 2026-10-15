"""Parse Figma JSON (file export or REST payload) into domain models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

from figma_to_pyside6.domain.models import FigmaDocument, FigmaFrame, FigmaNode


def _read_color(node: dict[str, Any]) -> tuple[float, float, float] | None:
    fills = node.get("fills") or []
    for fill in fills:
        if fill.get("type") == "SOLID":
            color = fill.get("color") or {}
            r = float(color.get("r", 0.0))
            g = float(color.get("g", 0.0))
            b = float(color.get("b", 0.0))
            return (r, g, b)
    return None


class _Geometry(TypedDict):
    x: int
    y: int
    width: int
    height: int


def _geometry(node: dict[str, Any]) -> _Geometry:
    """Read x/y/width/height, preferring explicit keys over ``absoluteBoundingBox``.

    Values are rounded to the nearest pixel (not truncated) so 99.9 becomes 100.
    """
    bounds = node.get("absoluteBoundingBox") or {}

    def read(key: str) -> int:
        return round(node.get(key, bounds.get(key, 0)) or 0)

    return {"x": read("x"), "y": read("y"), "width": read("width"), "height": read("height")}


def _parse_node(node: dict[str, Any]) -> FigmaNode:
    node_id = str(node.get("id") or "unknown")
    name = str(node.get("name") or node_id)
    kind = str(node.get("type") or "UNKNOWN")
    children = [_parse_node(child) for child in node.get("children") or []]
    fill_color = _read_color(node)
    component_id = node.get("componentId")
    warnings = []
    if kind not in {"FRAME", "TEXT", "INSTANCE", "COMPONENT", "GROUP", "VECTOR", "UNKNOWN"}:
        warnings.append(f"Unsupported Figma node type: {kind}")
    if node.get("layoutMode") and kind not in {"FRAME", "INSTANCE"}:
        warnings.append(f"Layout metadata on unsupported node: {kind}")
    return FigmaNode(
        node_id=node_id,
        name=name,
        type=kind,
        **_geometry(node),
        children=children,
        component_id=str(component_id) if component_id else None,
        fill_color=fill_color,
        characters=str(node["characters"]) if node.get("characters") else None,
        warnings=warnings,
    )


def _find_frames(node: dict[str, Any], *, recurse: bool = True) -> list[FigmaFrame]:
    frames: list[FigmaFrame] = []
    for child in node.get("children") or []:
        if child.get("type") == "FRAME":
            frame = FigmaFrame(
                node_id=str(child.get("id") or "unknown"),
                name=str(child.get("name") or "Unnamed"),
                type="FRAME",
                **_geometry(child),
                children=[_parse_node(grand) for grand in child.get("children") or []],
            )
            frames.append(frame)
        elif recurse:
            frames.extend(_find_frames(child))
    return frames


def parse_figma_document(
    payload: dict[str, Any],
    source: str = "Figma document",
    *,
    recurse_frames: bool = True,
) -> FigmaDocument:
    """Build a :class:`FigmaDocument` from a Figma JSON payload.

    Args:
        payload: Parsed JSON, either a REST response or a bare document node.
        source: Label used in error messages and as a name fallback.
        recurse_frames: Search below non-frame containers (pages, groups) for frames.

    Raises:
        ValueError: If the payload contains no FRAME nodes.
    """
    document = payload.get("document") or payload
    name = str(payload.get("name") or document.get("name") or Path(source).stem)
    node_id = str(document.get("id") or name)
    frames = _find_frames(document, recurse=recurse_frames)

    if not frames:
        raise ValueError(f"No FRAME nodes were found in {source}")

    return FigmaDocument(name=name, node_id=node_id, frames=frames, source=source)


def load_figma_document(path: str | Path) -> FigmaDocument:
    """Read and parse a Figma JSON file.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the file contains no frames.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Figma JSON file not found: {file_path}")

    payload = json.loads(file_path.read_text(encoding="utf-8"))
    return parse_figma_document(payload, source=str(file_path))
