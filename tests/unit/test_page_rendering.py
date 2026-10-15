"""Tests for the generated page source: what each Figma property becomes."""

from __future__ import annotations

from typing import Any

from helpers import raw_node, solid

from figma_to_pyside6.adapters.figma_json import parse_frame
from figma_to_pyside6.application.codegen import PagePlan, RenderedPage, render_page

PAGE = (0, 0, 400, 300)


def _render(
    *children: dict[str, Any], assets: dict[str, str] | None = None, **frame_extra: Any
) -> RenderedPage:
    frame = parse_frame(
        raw_node("FRAME", "Page", *PAGE, id="1:1", children=list(children), **frame_extra)
    )
    return render_page(PagePlan(frame, "page", "PagePage"), assets)


def _line_with(rendered: RenderedPage, needle: str) -> str:
    return next(line for line in rendered.source.splitlines() if needle in line)


def test_page_skeleton_and_root_fill() -> None:
    rendered = _render(fills=[solid(0.0, 0.0, 0.5)])

    assert "class PagePage(BasePage):" in rendered.source
    assert "FRAME_SIZE = (400, 300)" in rendered.source
    assert 'decorate(canvas, "background: rgba(0, 0, 128, 255);")' in rendered.source
    compile(rendered.source, "page.py", "exec")


def test_box_bakes_opacity_into_colors_and_gets_a_shadow_picture_behind_it() -> None:
    card = raw_node(
        "RECTANGLE",
        "Card",
        10,
        20,
        100,
        50,
        fills=[solid(1, 1, 1, 1, opacity=0.5)],
        strokes=[solid(0, 0, 0, 1, opacity=0.25)],
        strokeWeight=2,
        cornerRadius=8,
        opacity=0.4,
        effects=[
            {
                "type": "DROP_SHADOW",
                "color": {"r": 0, "g": 0, "b": 0, "a": 0.5},
                "offset": {"x": 0, "y": 4},
                "radius": 12,
            }
        ],
    )

    lines = _render(card).source.splitlines()
    box = next(i for i, line in enumerate(lines) if "# Card" in line)
    shadow = next(i for i, line in enumerate(lines) if "shadow(canvas" in line)

    assert "box(canvas, 10, 20, 100, 50," in lines[box]
    # node opacity 0.4 is multiplied into every alpha: fill 0.5 -> 51, stroke 0.25 -> 26
    assert "background: rgba(255, 255, 255, 51)" in lines[box]
    assert "border: 2px solid rgba(0, 0, 0, 26)" in lines[box]
    assert "border-radius: 8px" in lines[box]
    assert "opacity" not in lines[box]  # no Qt graphics effect: it breaks inside a scaled view
    assert "shadow(canvas, 10, 20, 100, 50, 8, 12, 0, 4, (0, 0, 0, 51))" in lines[shadow]
    assert shadow < box  # created first, so it is painted behind the box


def test_ellipse_is_fully_rounded() -> None:
    line = _line_with(
        _render(raw_node("ELLIPSE", "Dot", 0, 0, 20, 20, fills=[solid(1, 0, 0)])), "# Dot"
    )

    assert "border-radius: 10px" in line


def test_extra_fills_become_overlay_boxes_and_the_stroke_goes_on_top() -> None:
    layered = raw_node(
        "FRAME",
        "Layered",
        0,
        0,
        50,
        50,
        fills=[solid(1, 0, 0), solid(0, 1, 0, 0.5)],
        strokes=[solid(1, 1, 1)],
        strokeWeight=1,
        cornerRadius=4,
    )

    lines = _render(layered).source.splitlines()
    base = next(line for line in lines if "# Layered" in line)
    overlay = lines[lines.index(base) + 1]

    assert "background: rgba(255, 0, 0, 255); border-radius: 4px;" in base
    assert "border:" not in base  # the stroke is drawn above every fill
    assert "box(n1, 0, 0, 50, 50," in overlay
    assert "background: rgba(0, 255, 0, 128); border: 1px solid" in overlay


def test_text_uses_figma_typography() -> None:
    text = raw_node(
        "TEXT",
        "Title",
        10,
        10,
        200,
        20,
        characters="Hello",
        fills=[solid(0.9, 0.9, 0.9)],
        style={
            "fontFamily": "Inter",
            "fontSize": 14,
            "fontWeight": 600,
            "textAlignHorizontal": "CENTER",
            "letterSpacing": 0.5,
            "textCase": "UPPER",
            "textDecoration": "UNDERLINE",
            "fontStyle": "Semi Bold Italic",
            "lineHeightPx": 20,
        },
    )

    line = _line_with(_render(text), "text(canvas")

    assert '"HELLO"' in line  # text case applied
    assert '"Inter", 14, 600, "rgba(230, 230, 230, 255)"' in line
    for option in ("align_h='CENTER'", "spacing=0.50", "italic=True", "underline=True"):
        assert option in line


def test_single_line_text_gets_a_roomy_vertically_centred_box() -> None:
    text = raw_node(
        "TEXT", "t", 10, 100, 100, 14, characters="x", style={"fontSize": 14, "lineHeightPx": 17}
    )

    line = _line_with(_render(text), "text(canvas")

    # 14px text needs 21px: the box grows 3px above (and 4 below), and gains side padding
    assert ", 10, 97, 120, 21," in line and "align_v='CENTER'" in line


def test_multi_line_text_wraps_in_its_original_box() -> None:
    text = raw_node(
        "TEXT",
        "t",
        10,
        10,
        120,
        60,
        characters="a long paragraph",
        style={"fontSize": 14, "lineHeightPx": 20},
    )

    line = _line_with(_render(text), "text(canvas")

    assert ", 10, 10, 120, 60," in line and "wrap=True" in line and "align_v" not in line


def test_hidden_and_out_of_bounds_layers_are_not_emitted() -> None:
    rendered = _render(
        raw_node("RECTANGLE", "ok", 10, 10, 20, 20),
        raw_node("RECTANGLE", "hidden", 10, 10, 20, 20, visible=False),
        raw_node("RECTANGLE", "far", 900, 900, 20, 20),
    )

    assert "# ok" in rendered.source
    assert "# hidden" not in rendered.source and "# far" not in rendered.source


def test_nested_children_are_positioned_relative_to_their_parent() -> None:
    panel = raw_node(
        "FRAME",
        "Panel",
        100,
        50,
        200,
        100,
        children=[raw_node("RECTANGLE", "Inner", 120, 70, 30, 30)],
    )

    source = _render(panel).source

    assert "n1 = box(canvas, 100, 50, 200, 100," in source
    assert "n2 = box(n1, 20, 20, 30, 30," in source


def test_vector_layers_become_images_when_exported() -> None:
    vector = raw_node("VECTOR", "Logo", 5, 6, 40, 20, id="7:7", opacity=0.5)
    name = "fig_0123456789abcdef.png"

    rendered = _render(vector, assets={"7:7": name})

    line = _line_with(rendered, "image(")
    assert f'image(canvas, "{name}", 5, 6, 40, 20, opacity=0.500)' in line
    assert rendered.warnings == []


def test_exported_layers_use_render_bounds_so_shadows_are_not_cut_off() -> None:
    glow = raw_node(
        "VECTOR",
        "Glow",
        10,
        10,
        20,
        20,
        id="8:8",
        absoluteRenderBounds={"x": 0, "y": 0, "width": 40, "height": 40},
    )

    line = _line_with(_render(glow, assets={"8:8": "fig_glow.png"}), "image(")

    assert ", 0, 0, 40, 40" in line


def test_missing_exports_are_skipped_and_reported_once() -> None:
    rendered = _render(
        raw_node("VECTOR", "a", 0, 0, 10, 10, id="1:a"),
        raw_node("VECTOR", "b", 20, 0, 10, 10, id="1:b"),
    )

    assert "image(" not in rendered.source
    assert len(rendered.warnings) == 1 and "2 vector/image layer(s)" in rendered.warnings[0]


def test_text_moves_up_to_an_ancestor_that_can_hold_its_grown_box() -> None:
    tight = raw_node(
        "FRAME",
        "Tight",
        10,
        10,
        100,
        14,
        children=[
            raw_node(
                "TEXT",
                "t",
                10,
                10,
                100,
                14,
                characters="Gg",
                style={"fontSize": 14, "lineHeightPx": 14},
            )
        ],
    )
    page_child = raw_node("FRAME", "Wrapper", 0, 0, 300, 200, children=[tight])

    source = _render(page_child).source

    assert (
        "n1 = box(canvas, 0, 0, 300, 200," in source and "n2 = box(n1, 10, 10, 100, 14," in source
    )
    assert 'text(n1, "Gg", 10, 7, 120, 21,' in source  # hosted by the roomy wrapper, not n2


def test_opacity_is_inherited_and_text_may_still_move_up_the_tree() -> None:
    faded = raw_node(
        "FRAME",
        "Faded",
        10,
        10,
        100,
        14,
        opacity=0.5,
        children=[
            raw_node(
                "TEXT",
                "t",
                10,
                10,
                100,
                14,
                characters="Gg",
                fills=[solid(1, 1, 1)],
                style={"fontSize": 14, "lineHeightPx": 14},
            )
        ],
    )

    source = _render(raw_node("FRAME", "Wrapper", 0, 0, 300, 200, children=[faded])).source

    # the faded parent's 0.5 reaches the text colour, so hosting it higher changes nothing
    assert 'text(n1, "Gg", 10, 7, 120, 21, "Inter", 14, 400, "rgba(255, 255, 255, 128)"' in source


def test_opacity_compounds_down_the_tree_into_fills_text_and_images() -> None:
    panel = raw_node(
        "FRAME",
        "Panel",
        0,
        0,
        200,
        100,
        opacity=0.5,
        fills=[solid(1, 0, 0)],
        children=[
            raw_node("RECTANGLE", "Inner", 10, 10, 50, 50, opacity=0.5, fills=[solid(0, 1, 0)]),
            raw_node("VECTOR", "Art", 70, 10, 20, 20, id="3:3", opacity=0.5),
        ],
    )

    source = _render(panel, assets={"3:3": "fig_panel.png"}).source

    assert "background: rgba(255, 0, 0, 128)" in source  # 1.0 * 0.5
    assert "background: rgba(0, 255, 0, 64)" in source  # 0.5 * 0.5
    assert "opacity=0.250" in _line_with(_render(panel, assets={"3:3": "fig_panel.png"}), "image(")


def test_shadow_is_skipped_when_it_has_no_blur() -> None:
    sharp = raw_node(
        "RECTANGLE",
        "Sharp",
        0,
        0,
        20,
        20,
        effects=[{"type": "DROP_SHADOW", "color": {"r": 0, "g": 0, "b": 0, "a": 1}, "radius": 0}],
    )

    assert "shadow(" not in _render(sharp).source


def test_hostile_text_cannot_break_out_of_its_string_literal() -> None:
    evil = 'x"); __import__("os").system("echo pwned"); ("'
    rendered = _render(raw_node("TEXT", "t", 0, 0, 50, 14, characters=evil))

    compile(rendered.source, "page.py", "exec")
    assert rendered.source.count("__import__") == 1  # only inside the quoted literal


def test_layers_sharing_an_exported_image_all_point_at_the_same_file() -> None:
    a = raw_node("VECTOR", "icon", 10, 10, 16, 16, id="1:a")
    b = raw_node("VECTOR", "icon", 50, 10, 16, 16, id="1:b")

    rendered = _render(a, b, assets={"1:a": "fig_same.png", "1:b": "fig_same.png"})

    assert rendered.source.count('image(canvas, "fig_same.png"') == 2
    assert rendered.warnings == []
