"""Shared fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture
def qt_app() -> Iterator[QApplication]:
    """A QApplication that exists for the duration of one test."""
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    yield app
    app.quit()
