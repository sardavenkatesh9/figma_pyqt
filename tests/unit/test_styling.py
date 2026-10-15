"""Tests for the Figma paint to QSS translation."""

from __future__ import annotations

import pytest

from figma_to_pyside6.application.styling import (
    background_qss,
    border_qss,
    box_qss,
    css_color,
    radius_qss,
)
from figma_to_pyside6.domain.models import Color, GradientStop, Paint


def _linear() -> Paint:
    return Paint(
        "GRADIENT_LINEAR",
        stops=[GradientStop(Color(1, 0, 0, 1), 0.0), GradientStop(Color(0, 0, 1, 0.5), 1.0)],
        handles=[(0.0, 0.25), (1.0, 0.75), (0.0, 1.0)],
        opacity=0.5,
    )


def test_css_color_scales_channels_and_multiplies_opacity() -> None:
    assert css_color(Color(1, 0.5, 0, 1)) == "rgba(255, 128, 0, 255)"
    assert css_color(Color(0, 0, 0, 0.5), opacity=0.5) == "rgba(0, 0, 0, 64)"
    assert css_color(Color(2, -1, 0, 5)) == "rgba(255, 0, 0, 255)"  # clamped


def test_solid_background_uses_paint_opacity() -> None:
    assert background_qss(Paint("SOLID", Color(0, 0, 0), opacity=0.1)) == "rgba(0, 0, 0, 26)"


def test_linear_gradient_maps_handles_and_stops() -> None:
    qss = background_qss(_linear())

    assert qss is not None and qss.startswith("qlineargradient(x1:0.0000, y1:0.2500, x2:1.0000")
    assert "stop:0.000 rgba(255, 0, 0, 128)" in qss  # paint opacity applied to every stop
    assert "stop:1.000 rgba(0, 0, 255, 64)" in qss


def test_radial_gradient_uses_mean_handle_distance_as_radius() -> None:
    paint = Paint(
        "GRADIENT_RADIAL",
        stops=[GradientStop(Color(1, 1, 1, 1), 0), GradientStop(Color(0, 0, 0, 0), 1)],
        handles=[(0.5, 0.5), (1.0, 0.5), (0.5, 1.5)],
    )

    qss = background_qss(paint)

    assert qss is not None and "radius:0.7500" in qss and "cx:0.5000, cy:0.5000" in qss


@pytest.mark.parametrize("kind", ["GRADIENT_ANGULAR", "GRADIENT_DIAMOND"])
def test_unsupported_gradients_fall_back_to_first_stop(kind: str) -> None:
    paint = Paint(kind, stops=[GradientStop(Color(0, 1, 0, 1), 0), GradientStop(Color(0, 0, 0), 1)])

    assert background_qss(paint) == "rgba(0, 255, 0, 255)"


def test_image_and_malformed_paints_have_no_background() -> None:
    assert background_qss(Paint("IMAGE")) is None
    assert background_qss(Paint("GRADIENT_LINEAR", stops=[], handles=[])) is None


def test_border_needs_a_stroke_and_a_positive_weight() -> None:
    stroke = Paint("SOLID", Color(1, 1, 1), opacity=0.1)

    assert border_qss(stroke, 1.0) == "border: 1px solid rgba(255, 255, 255, 26)"
    assert border_qss(stroke, 0.4) == "border: 1px solid rgba(255, 255, 255, 26)"  # at least 1px
    assert border_qss(stroke, 0) is None
    assert border_qss(None, 2) is None


def test_radius_is_clamped_and_rounded_down_so_qt_keeps_the_rounding() -> None:
    assert radius_qss((999, 999, 999, 999), 72, 31) == "border-radius: 15px"  # 15.5 -> 15
    assert radius_qss((12, 12, 0, 0), 100, 100) == (
        "border-top-left-radius: 12px; border-top-right-radius: 12px; "
        "border-bottom-right-radius: 0px; border-bottom-left-radius: 0px"
    )
    assert radius_qss(None, 10, 10) == ""
    assert radius_qss((0, 0, 0, 0), 10, 10) == ""


def test_box_qss_defaults_to_a_transparent_background() -> None:
    assert box_qss(None, None, 0, None, 10, 10) == "background: transparent;"
    qss = box_qss(
        Paint("SOLID", Color(0, 0, 0)), Paint("SOLID", Color(1, 1, 1)), 2, (4,) * 4, 50, 50
    )
    assert qss == (
        "background: rgba(0, 0, 0, 255); border: 2px solid rgba(255, 255, 255, 255); "
        "border-radius: 4px;"
    )
