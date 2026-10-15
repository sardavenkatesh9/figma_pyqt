"""Tests for generated app."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from helpers import (
    FIXTURE,
)

from figma_to_pyside6.adapters.figma_json import load_figma_document
from figma_to_pyside6.application.conversion_service import convert_document


def test_generated_app_builds_a_window_with_a_page_per_frame(tmp_path):
    document = load_figma_document(FIXTURE)
    convert_document(document, output_dir=tmp_path)
    script = (
        "import sys; sys.path.insert(0, '.')\n"
        "from PySide6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from src.ui.main_window import MainWindow\n"
        "w = MainWindow()\n"
        "print(w.stack.count())\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "2"


def _run_generated(tmp_path: Path, script: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, '.')\n" + script],
        cwd=tmp_path,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_generated_page_paints_the_figma_colors_and_exported_images(tmp_path: Path) -> None:
    from helpers import raw_node, solid, tiny_png

    from figma_to_pyside6.adapters.figma_json import parse_frame
    from figma_to_pyside6.application.conversion_service import convert_document
    from figma_to_pyside6.application.raster import asset_filename
    from figma_to_pyside6.domain.models import FigmaDocument

    frame = parse_frame(
        raw_node(
            "FRAME",
            "Colors",
            0,
            0,
            300,
            200,
            id="1:1",
            fills=[solid(0, 0, 1)],
            children=[
                raw_node(
                    "RECTANGLE", "Red", 20, 20, 100, 60, fills=[solid(1, 0, 0)], cornerRadius=0
                ),
                raw_node(
                    "RECTANGLE", "Faded", 20, 100, 100, 60, fills=[solid(1, 1, 1)], opacity=0.5
                ),
                raw_node("VECTOR", "Art", 150, 20, 40, 40, id="1:art"),
            ],
        )
    )
    convert_document(
        FigmaDocument("Doc", "0:0", [frame]), output_dir=tmp_path, assets={"1:art": tiny_png()}
    )
    assert (tmp_path / "src" / "ui" / "assets" / asset_filename(tiny_png())).exists()

    script = (
        "from PySide6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from src.ui.pages import PAGES\n"
        "page = PAGES[0][1]()\n"
        "page.resize(300, 200)\n"
        "page.show()\n"
        "image = page.canvas.grab().toImage()\n"
        "def rgb(x, y):\n"
        "    c = image.pixelColor(x, y)\n"
        "    return c.red(), c.green(), c.blue()\n"
        "print(rgb(5, 5), rgb(60, 40), rgb(60, 130), rgb(170, 40))\n"
    )

    background, red, faded, art = _run_generated(tmp_path, script).split(") (")
    assert background.strip("()") == "0, 0, 255"  # frame fill
    assert red.strip("()") == "255, 0, 0"  # rectangle fill
    faded_r, _faded_g, faded_b = (int(v) for v in faded.strip("()").split(","))
    assert 120 <= faded_r <= 135 and faded_b == 255  # 50% white over blue
    assert art.strip("()") == "255, 0, 255"  # the exported image (magenta test PNG)


def test_generated_page_scales_to_the_window_keeping_its_aspect(tmp_path: Path) -> None:
    from helpers import make_document, make_frame

    from figma_to_pyside6.application.conversion_service import convert_document

    convert_document(make_document(make_frame(width=800, height=600)), output_dir=tmp_path)
    script = (
        "from PySide6.QtWidgets import QApplication, QGraphicsView\n"
        "app = QApplication([])\n"
        "from src.ui.pages import PAGES\n"
        "page = PAGES[0][1]()\n"
        "page.resize(400, 300)\n"
        "page.show()\n"
        "view = page.findChild(QGraphicsView)\n"
        "print(round(view.transform().m11(), 2), round(view.transform().m22(), 2))\n"
    )

    scale_x, scale_y = (float(v) for v in _run_generated(tmp_path, script).split())
    assert 0.47 <= scale_x <= 0.5  # 400px window / 800px canvas, minus the view's own margin
    assert scale_x == scale_y  # aspect ratio preserved


def test_drop_shadow_is_painted_behind_the_box_and_fades_out(tmp_path: Path) -> None:
    from helpers import raw_node, solid

    from figma_to_pyside6.adapters.figma_json import parse_frame
    from figma_to_pyside6.application.conversion_service import convert_document
    from figma_to_pyside6.domain.models import FigmaDocument

    card = raw_node(
        "RECTANGLE",
        "Card",
        100,
        60,
        100,
        60,
        fills=[solid(1, 1, 1)],
        effects=[
            {
                "type": "DROP_SHADOW",
                "color": {"r": 0, "g": 0, "b": 0, "a": 1},
                "offset": {"x": 0, "y": 20},
                "radius": 20,
            }
        ],
    )
    frame = parse_frame(
        raw_node("FRAME", "S", 0, 0, 300, 220, id="1:1", fills=[solid(1, 1, 1)], children=[card])
    )
    convert_document(FigmaDocument("Doc", "0:0", [frame]), output_dir=tmp_path)

    script = (
        "from PySide6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from src.ui.pages import PAGES\n"
        "page = PAGES[0][1]()\n"
        "page.resize(300, 220)\n"
        "page.show()\n"
        "image = page.canvas.grab().toImage()\n"
        "def lum(x, y):\n"
        "    return image.pixelColor(x, y).red()\n"
        "print(lum(150, 90), lum(150, 140), lum(150, 205), lum(5, 5))\n"
    )

    on_card, just_below, far_below, corner = (
        int(v) for v in _run_generated(tmp_path, script).split()
    )
    assert on_card == 255  # the white card itself is untouched by its shadow
    assert just_below < 200  # the shadow darkens the page below the card (offset 20px down)
    assert far_below > just_below  # ... and fades with distance
    assert corner == 255  # far from the card there is no shadow
