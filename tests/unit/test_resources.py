"""Tests for resources."""

from __future__ import annotations

from pathlib import Path

from figma_to_pyside6.resources import asset_path


def test_asset_path_points_at_existing_icon() -> None:
    assert asset_path("icon.png").exists()


def test_icons_ship_inside_the_package_and_are_declared_as_package_data() -> None:
    """Audit B7: assets must live in the package so installed wheels include them."""
    import tomllib

    pyproject = tomllib.loads((Path(__file__).parents[2] / "pyproject.toml").read_text("utf-8"))
    package_data = pyproject["tool"]["setuptools"]["package-data"]["figma_to_pyside6"]

    assert "assets/*" in package_data
    for icon in ("icon.png", "icon.ico", "icon.icns"):
        assert asset_path(icon).parent.name == "assets"
        assert asset_path(icon).exists()
