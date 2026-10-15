"""Translate Figma paints, strokes and corner radii into Qt style sheet (QSS) fragments."""

from __future__ import annotations

import math

from figma_to_pyside6.domain.models import Color, Paint

GRADIENT_KINDS = frozenset({"GRADIENT_LINEAR", "GRADIENT_RADIAL"})
_OTHER_GRADIENTS = frozenset({"GRADIENT_ANGULAR", "GRADIENT_DIAMOND"})


def css_color(color: Color, opacity: float = 1.0) -> str:
    """Return ``rgba(r, g, b, a)`` with 0-255 channels, as Qt style sheets expect."""
    alpha = max(0.0, min(1.0, color.a * opacity))
    r, g, b = (round(max(0.0, min(1.0, c)) * 255) for c in (color.r, color.g, color.b))
    return f"rgba({r}, {g}, {b}, {round(alpha * 255)})"


def _gradient_stops(paint: Paint, factor: float) -> str:
    return ", ".join(
        f"stop:{max(0.0, min(1.0, stop.position)):.3f} "
        f"{css_color(stop.color, paint.opacity * factor)}"
        for stop in paint.stops
    )


def _first_color(paint: Paint) -> Color | None:
    if paint.color is not None:
        return paint.color
    return paint.stops[0].color if paint.stops else None


def background_qss(paint: Paint, factor: float = 1.0) -> str | None:
    """QSS ``background`` value for a fill, or ``None`` if it cannot be expressed.

    ``factor`` is the opacity inherited from the node and its ancestors, baked into the colors.

    Linear and radial gradients map to ``qlineargradient`` / ``qradialgradient`` in
    object-bounding coordinates; angular and diamond gradients fall back to their first stop.
    """
    if paint.kind == "SOLID" and paint.color is not None:
        return css_color(paint.color, paint.opacity * factor)
    if paint.kind == "GRADIENT_LINEAR" and len(paint.stops) >= 2 and len(paint.handles) >= 2:
        (x1, y1), (x2, y2) = paint.handles[0], paint.handles[1]
        return (
            f"qlineargradient(x1:{x1:.4f}, y1:{y1:.4f}, x2:{x2:.4f}, y2:{y2:.4f}, "
            f"{_gradient_stops(paint, factor)})"
        )
    if paint.kind == "GRADIENT_RADIAL" and len(paint.stops) >= 2 and len(paint.handles) >= 3:
        (cx, cy), edge_x, edge_y = paint.handles[0], paint.handles[1], paint.handles[2]
        radius = (math.dist((cx, cy), edge_x) + math.dist((cx, cy), edge_y)) / 2
        return (
            f"qradialgradient(cx:{cx:.4f}, cy:{cy:.4f}, radius:{max(radius, 0.001):.4f}, "
            f"fx:{cx:.4f}, fy:{cy:.4f}, {_gradient_stops(paint, factor)})"
        )
    if paint.kind in GRADIENT_KINDS | _OTHER_GRADIENTS:
        color = _first_color(paint)
        return css_color(color, paint.opacity * factor) if color else None
    return None


def border_qss(stroke: Paint | None, weight: float, factor: float = 1.0) -> str | None:
    """QSS ``border`` declaration for a stroke (gradients use their first stop)."""
    if stroke is None or weight <= 0:
        return None
    color = _first_color(stroke)
    if color is None:
        return None
    return f"border: {max(1, round(weight))}px solid {css_color(color, stroke.opacity * factor)}"


def radius_qss(radii: tuple[float, float, float, float] | None, width: int, height: int) -> str:
    """QSS corner radius declarations, clamped so they never exceed half the box."""
    if not radii or not any(radii):
        return ""
    # Qt drops the rounding entirely when a radius exceeds half the box, so round down.
    limit = max(min(width, height) / 2, 0.0)
    tl, tr, br, bl = (math.floor(min(r, limit)) for r in radii)
    if tl == tr == br == bl:
        return f"border-radius: {tl}px"
    return (
        f"border-top-left-radius: {tl}px; border-top-right-radius: {tr}px; "
        f"border-bottom-right-radius: {br}px; border-bottom-left-radius: {bl}px"
    )


def box_qss(
    fill: Paint | None,
    stroke: Paint | None,
    stroke_weight: float,
    radii: tuple[float, float, float, float] | None,
    width: int,
    height: int,
    factor: float = 1.0,
) -> str:
    """Compose the QSS body for one box layer (background, border and corner radius)."""
    parts = []
    background = background_qss(fill, factor) if fill is not None else None
    parts.append(f"background: {background}" if background else "background: transparent")
    border = border_qss(stroke, stroke_weight, factor)
    if border:
        parts.append(border)
    radius = radius_qss(radii, width, height)
    if radius:
        parts.append(radius)
    return "; ".join(parts) + ";"
