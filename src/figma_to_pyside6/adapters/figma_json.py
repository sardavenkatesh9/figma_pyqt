"""Parse Figma JSON (file export or REST payload) into domain models."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, TypedDict

from figma_to_pyside6.domain.models import (
    Color,
    Effect,
    FigmaDocument,
    FigmaFrame,
    FigmaNode,
    GradientStop,
    Paint,
    TextStyle,
)

SUPPORTED_TYPES = frozenset(
    {
        "FRAME",
        "TEXT",
        "INSTANCE",
        "COMPONENT",
        "COMPONENT_SET",
        "GROUP",
        "SECTION",
        "RECTANGLE",
        "ELLIPSE",
        "LINE",
        "VECTOR",
        "BOOLEAN_OPERATION",
        "STAR",
        "REGULAR_POLYGON",
        "UNKNOWN",
    }
)
_EFFECT_KINDS = frozenset({"DROP_SHADOW", "INNER_SHADOW", "LAYER_BLUR", "BACKGROUND_BLUR"})


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


def _color(raw: dict[str, Any] | None, default_alpha: float = 1.0) -> Color:
    raw = raw or {}
    return Color(
        float(raw.get("r", 0.0)),
        float(raw.get("g", 0.0)),
        float(raw.get("b", 0.0)),
        float(raw.get("a", default_alpha)),
    )


def _paints(node: dict[str, Any], key: str) -> list[Paint]:
    """Visible paints of ``fills`` or ``strokes``, bottom layer first."""
    paints = []
    for raw in node.get(key) or []:
        if raw.get("visible", True) is False:
            continue
        kind = str(raw.get("type") or "UNKNOWN")
        paints.append(
            Paint(
                kind=kind,
                color=_color(raw.get("color")) if kind == "SOLID" else None,
                opacity=float(raw.get("opacity", 1.0)),
                stops=[
                    GradientStop(_color(stop.get("color")), float(stop.get("position", 0.0)))
                    for stop in raw.get("gradientStops") or []
                ],
                handles=[
                    (float(h.get("x", 0.0)), float(h.get("y", 0.0)))
                    for h in raw.get("gradientHandlePositions") or []
                ],
            )
        )
    return paints


def _effects(node: dict[str, Any]) -> list[Effect]:
    effects = []
    for raw in node.get("effects") or []:
        kind = raw.get("type")
        if raw.get("visible", True) is False or kind not in _EFFECT_KINDS:
            continue
        offset = raw.get("offset") or {}
        effects.append(
            Effect(
                kind=kind,
                color=_color(raw.get("color"), default_alpha=0.25),
                offset_x=float(offset.get("x", 0.0)),
                offset_y=float(offset.get("y", 0.0)),
                radius=float(raw.get("radius", 0.0)),
            )
        )
    return effects


def _corner_radii(node: dict[str, Any]) -> tuple[float, float, float, float] | None:
    per_corner = node.get("rectangleCornerRadii")
    if isinstance(per_corner, list) and len(per_corner) == 4:
        radii = tuple(float(v) for v in per_corner)
        return radii if any(radii) else None  # type: ignore[return-value]
    uniform = float(node.get("cornerRadius") or 0.0)
    return (uniform, uniform, uniform, uniform) if uniform else None


def _text_style(node: dict[str, Any]) -> TextStyle | None:
    raw = node.get("style")
    if node.get("type") != "TEXT" or not isinstance(raw, dict):
        return None
    line_height = raw.get("lineHeightPx")
    return TextStyle(
        font_family=str(raw.get("fontFamily") or "Inter"),
        font_size=float(raw.get("fontSize") or 14.0),
        font_weight=int(raw.get("fontWeight") or 400),
        italic=bool(raw.get("italic")) or "italic" in str(raw.get("fontStyle", "")).lower(),
        align_h=str(raw.get("textAlignHorizontal") or "LEFT"),
        align_v=str(raw.get("textAlignVertical") or "TOP"),
        letter_spacing=float(raw.get("letterSpacing") or 0.0),
        line_height=float(line_height) if line_height else None,
        text_case=str(raw.get("textCase") or "ORIGINAL"),
        underline=raw.get("textDecoration") == "UNDERLINE",
    )


def _render_bounds(node: dict[str, Any]) -> tuple[int, int, int, int] | None:
    raw = node.get("absoluteRenderBounds")
    if not isinstance(raw, dict):
        return None
    x, y = math.floor(raw.get("x", 0)), math.floor(raw.get("y", 0))
    right = math.ceil(raw.get("x", 0) + raw.get("width", 0))
    bottom = math.ceil(raw.get("y", 0) + raw.get("height", 0))
    return (x, y, right - x, bottom - y)


def _node_kwargs(node: dict[str, Any], default_name: str) -> dict[str, Any]:
    """Fields shared by plain nodes and frames."""
    node_id = str(node.get("id") or "unknown")
    kind = str(node.get("type") or "UNKNOWN")
    warnings = []
    if kind not in SUPPORTED_TYPES:
        warnings.append(f"Unsupported Figma node type: {kind}")
    if node.get("layoutMode") and kind not in {"FRAME", "INSTANCE", "COMPONENT"}:
        warnings.append(f"Layout metadata on unsupported node: {kind}")
    component_id = node.get("componentId")
    return {
        "node_id": node_id,
        "name": str(node.get("name") or default_name or node_id),
        "type": kind,
        **_geometry(node),
        "children": [_parse_node(child) for child in node.get("children") or []],
        "component_id": str(component_id) if component_id else None,
        "fill_color": _read_color(node),
        "characters": str(node["characters"]) if node.get("characters") else None,
        "warnings": warnings,
        "visible": node.get("visible", True) is not False,
        "opacity": float(node.get("opacity", 1.0)),
        "fills": _paints(node, "fills"),
        "strokes": _paints(node, "strokes"),
        "stroke_weight": float(node.get("strokeWeight") or 0.0),
        "corner_radii": _corner_radii(node),
        "effects": _effects(node),
        "text_style": _text_style(node),
        "rotation": float(node.get("rotation") or 0.0),
        "is_mask": bool(node.get("isMask")),
        "render_bounds": _render_bounds(node),
    }


def _parse_node(node: dict[str, Any]) -> FigmaNode:
    return FigmaNode(**_node_kwargs(node, ""))


def parse_frame(node: dict[str, Any], container: str | None = None) -> FigmaFrame:
    """Parse one FRAME dict, with its full subtree, into a :class:`FigmaFrame`."""
    return FigmaFrame(**_node_kwargs(node, "Unnamed"), container_name=container)


def _find_frames(
    node: dict[str, Any], *, recurse: bool = True, container: str | None = None
) -> list[FigmaFrame]:
    frames: list[FigmaFrame] = []
    for child in node.get("children") or []:
        if child.get("type") == "FRAME":
            frames.append(parse_frame(child, container))
        elif recurse:
            frames.extend(_find_frames(child, container=str(child.get("name") or "") or None))
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
