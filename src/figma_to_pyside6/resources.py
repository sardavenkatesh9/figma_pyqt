"""Locate bundled assets (shipped inside the package, so wheels and PyInstaller both work)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def asset_path(name: str) -> Path:
    """Return the path of a bundled asset such as ``icon.png``."""
    return ASSETS_DIR / name


def app_icon() -> QIcon:
    """Return the application icon."""
    return QIcon(str(asset_path("icon.png")))
