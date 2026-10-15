"""Tests for generated app."""

from __future__ import annotations

import os
import subprocess
import sys

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
