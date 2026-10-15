"""Decide which Figma nodes cannot be built from Qt widgets and must be exported as images.

Widgets handle frames, rectangles, ellipses and text. Everything else (vector art, icons,
image fills, masks, rotated layers) is rendered by Figma itself through its images API and
shipped as a PNG, so the generated page looks like the design.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator

from figma_to_pyside6.domain.models import FigmaFrame, FigmaNode

VECTOR_TYPES = frozenset({"VECTOR", "BOOLEAN_OPERATION", "STAR", "LINE", "REGULAR_POLYGON"})
CONTAINER_TYPES = frozenset({"GROUP", "FRAME", "INSTANCE", "COMPONENT", "COMPONENT_SET"})
MAX_RASTER_SIDE = 8000  # larger nodes are skipped instead of asking Figma for a huge render
_ROTATION_EPSILON = 1e-3


def asset_filename(data: bytes) -> str:
    """File name of an exported PNG, derived from its content (``fig_<hash>.png``).

    Naming by content means identical exports (the same icon used in many places, or on
    many frames) end up as one file that every page reuses.
    """
    return "fig_" + hashlib.sha256(data).hexdigest()[:16] + ".png"


def has_image_fill(node: FigmaNode) -> bool:
    """Whether any visible fill is a bitmap."""
    return any(paint.kind == "IMAGE" for paint in node.fills)


def _vector_only(node: FigmaNode) -> tuple[bool, bool]:
    """Return (all visible descendants are vector art or containers, at least one vector)."""
    saw_vector = node.type in VECTOR_TYPES
    for child in node.children:
        if not child.visible:
            continue
        if child.type in VECTOR_TYPES:
            saw_vector = True
        elif child.type in CONTAINER_TYPES and not has_image_fill(child):
            only, vector = _vector_only(child)
            if not only:
                return False, saw_vector
            saw_vector = saw_vector or vector
        else:
            return False, saw_vector
    return True, saw_vector


def needs_raster(node: FigmaNode) -> bool:
    """Whether ``node`` (never the page frame itself) must be exported as an image."""
    if node.type in VECTOR_TYPES or has_image_fill(node) or node.is_mask:
        return True
    if abs(node.rotation) > _ROTATION_EPSILON:
        return True
    if any(child.is_mask and child.visible for child in node.children):
        return True
    if node.type in CONTAINER_TYPES and node.children:
        only_vectors, saw_vector = _vector_only(node)
        return only_vectors and saw_vector
    return False


def raster_bounds(node: FigmaNode) -> tuple[int, int, int, int]:
    """Absolute x, y, width, height of the exported image (render bounds include shadows)."""
    return node.render_bounds or (node.x, node.y, node.width, node.height)


def too_large(node: FigmaNode) -> bool:
    """Whether the node's render would exceed what we are willing to request."""
    _, _, width, height = raster_bounds(node)
    return width > MAX_RASTER_SIDE or height > MAX_RASTER_SIDE


def is_inside(child: FigmaNode, parent: FigmaNode) -> bool:
    """Whether ``child`` overlaps ``parent``'s box at all (others are clipped away by Qt)."""
    cx, cy, cw, ch = raster_bounds(child) if needs_raster(child) else _box(child)
    return (
        cx < parent.x + parent.width
        and cx + cw > parent.x
        and cy < parent.y + parent.height
        and cy + ch > parent.y
    )


def _box(node: FigmaNode) -> tuple[int, int, int, int]:
    return (node.x, node.y, node.width, node.height)


def renderable_children(parent: FigmaNode) -> Iterator[FigmaNode]:
    """Visible children that overlap the parent, in paint order (bottom first)."""
    for child in parent.children:
        if child.visible and is_inside(child, parent):
            yield child


def collect_raster_nodes(frame: FigmaFrame) -> list[FigmaNode]:
    """All nodes of ``frame`` that will be drawn from an exported image.

    Mirrors the traversal of the page generator (it stops descending at raster nodes), so
    the set of images fetched is exactly the set of images the page uses.
    """
    found: list[FigmaNode] = []

    def visit(node: FigmaNode) -> None:
        for child in renderable_children(node):
            if needs_raster(child):
                if not too_large(child):
                    found.append(child)
            else:
                visit(child)

    visit(frame)
    return found
