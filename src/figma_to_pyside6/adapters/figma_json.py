from __future__ import annotations

import json
from pathlib import Path

from figma_to_pyside6.domain.models import FigmaDocument, FigmaFrame, FigmaNode


def _read_color(node: dict) -> tuple[float, float, float] | None:
    fills = node.get("fills") or []
    for fill in fills:
        if fill.get("type") == "SOLID":
            color = fill.get("color") or {}
            r = float(color.get("r", 0.0))
            g = float(color.get("g", 0.0))
            b = float(color.get("b", 0.0))
            return (r, g, b)
    return None


def _parse_node(node: dict, *, include_children: bool = True) -> FigmaNode:
    node_id = str(node.get("id") or "unknown")
    name = str(node.get("name") or node_id)
    kind = str(node.get("type") or "UNKNOWN")
    bounds = node.get("absoluteBoundingBox") or {}
    children = []
    if include_children:
        for child in node.get("children") or []:
            children.append(_parse_node(child))
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
        x=int(node.get("x", bounds.get("x", 0)) or 0),
        y=int(node.get("y", bounds.get("y", 0)) or 0),
        width=int(node.get("width", bounds.get("width", 0)) or 0),
        height=int(node.get("height", bounds.get("height", 0)) or 0),
        children=children,
        component_id=str(component_id) if component_id else None,
        fill_color=fill_color,
        warnings=warnings,
    )


def _find_frames(node: dict, *, recurse: bool = True) -> list[FigmaFrame]:
    frames: list[FigmaFrame] = []
    for child in node.get("children") or []:
        if child.get("type") == "FRAME":
            bounds = child.get("absoluteBoundingBox") or {}
            frame = FigmaFrame(
                node_id=str(child.get("id") or "unknown"),
                name=str(child.get("name") or "Unnamed"),
                type="FRAME",
                x=int(child.get("x", bounds.get("x", 0)) or 0),
                y=int(child.get("y", bounds.get("y", 0)) or 0),
                width=int(child.get("width", bounds.get("width", 0)) or 0),
                height=int(child.get("height", bounds.get("height", 0)) or 0),
                children=[_parse_node(grand) for grand in child.get("children") or []],
            )
            frames.append(frame)
        elif recurse:
            frames.extend(_find_frames(child))
    return frames


def parse_figma_document(
    payload: dict,
    source: str = "Figma document",
    *,
    recurse_frames: bool = True,
) -> FigmaDocument:
    document = payload.get("document") or payload
    name = str(payload.get("name") or document.get("name") or Path(source).stem)
    node_id = str(document.get("id") or name)
    frames = _find_frames(document, recurse=recurse_frames)

    if not frames:
        raise ValueError(f"No FRAME nodes were found in {source}")

    return FigmaDocument(name=name, node_id=node_id, frames=frames, source=source)


def load_figma_document(path: str | Path) -> FigmaDocument:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Figma JSON file not found: {file_path}")

    payload = json.loads(file_path.read_text(encoding="utf-8"))
    return parse_figma_document(payload, source=str(file_path))
