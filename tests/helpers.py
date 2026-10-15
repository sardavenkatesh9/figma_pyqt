"""Shared test helpers (importable because ``tests`` is on pytest's pythonpath)."""

from __future__ import annotations

import json
import zlib
from pathlib import Path
from typing import Any

from PySide6.QtCore import QByteArray
from PySide6.QtNetwork import QNetworkReply, QNetworkRequest

from figma_to_pyside6.adapters.figma_json import parse_figma_document
from figma_to_pyside6.domain.models import FigmaDocument

FIXTURE = Path(__file__).parent / "fixtures" / "figma_json" / "sample_figma.json"


def make_document(*frames: dict[str, Any]) -> FigmaDocument:
    """Build a document from raw Figma frame dicts."""
    return parse_figma_document({"name": "Doc", "document": {"children": list(frames)}})


def make_frame(name: str = "Home", **extra: Any) -> dict[str, Any]:
    """Raw Figma FRAME dict with sensible defaults."""
    return {"id": "f:1", "type": "FRAME", "name": name, "width": 100, "height": 200, **extra}


def page_source(root: Path, slug: str = "home") -> str:
    """Read a generated page module."""
    return (root / "src" / "ui" / "pages" / f"{slug}_page.py").read_text(encoding="utf-8")


class FakeNetworkManager:
    """Records the request instead of sending it."""

    def __init__(self) -> None:
        self.request: QNetworkRequest | None = None

    def get(self, request: QNetworkRequest) -> None:
        self.request = request


class FakeNetworkReply:
    """Minimal stand-in for ``QNetworkReply`` carrying a JSON payload."""

    def __init__(
        self,
        payload: dict[str, Any] | bytes,
        status_code: int = 200,
        error: QNetworkReply.NetworkError = QNetworkReply.NetworkError.NoError,
    ) -> None:
        self.payload = payload
        self.status_code = status_code
        self._error = error
        self.deleted = False

    def error(self) -> QNetworkReply.NetworkError:
        return self._error

    def attribute(self, attribute: QNetworkRequest.Attribute) -> int | None:
        if attribute == QNetworkRequest.Attribute.HttpStatusCodeAttribute:
            return self.status_code
        return None

    def readAll(self) -> QByteArray:
        if isinstance(self.payload, bytes):
            return QByteArray(self.payload)
        return QByteArray(json.dumps(self.payload).encode("utf-8"))

    def deleteLater(self) -> None:
        self.deleted = True


def tiny_png(size: int = 4, color: str = "#ff00ff") -> bytes:
    """A valid PNG, standing in for an image downloaded from Figma."""
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QColor, QImage

    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data().data())


class FakeFigmaClient:
    """A Figma connection that answers from memory and records every request.

    ``frames`` maps frame id to the raw Figma node dict the ``/nodes`` endpoint would return.
    ``missing_images`` are ids the images endpoint reports as not exportable. Each node's
    export has its own picture, unless ``identical_images`` makes every export the same bytes.
    """

    def __init__(
        self,
        frames: dict[str, dict[str, Any]],
        missing_images: frozenset[str] = frozenset(),
        identical_images: bool = False,
    ) -> None:
        self.frames = frames
        self.missing_images = missing_images
        self.identical_images = identical_images
        self.json_urls: list[str] = []
        self.byte_urls: list[str] = []

    def get_json(self, url: str) -> dict[str, Any]:
        self.json_urls.append(url)
        ids = url.split("ids=")[1].split("&")[0].split(",")
        if "/images/" in url:
            return {
                "images": {
                    i: (None if i in self.missing_images else f"https://img/{i}") for i in ids
                }
            }
        return {"nodes": {i: {"document": self.frames[i]} for i in ids}}

    def image_for(self, node_id: str) -> bytes:
        """The PNG this client serves for a node's export."""
        if self.identical_images:
            return tiny_png()
        return tiny_png(color=f"#{zlib.crc32(node_id.encode()) & 0xFFFFFF:06x}")

    def get_bytes(self, url: str) -> bytes:
        self.byte_urls.append(url)
        return self.image_for(url.rsplit("/", 1)[1])


def raw_node(
    kind: str, name: str, x: float, y: float, w: float, h: float, **extra: Any
) -> dict[str, Any]:
    """A raw Figma node dict with an ``absoluteBoundingBox`` (like the REST API returns)."""
    return {
        "id": extra.pop("id", f"{kind[:3]}:{name}"),
        "type": kind,
        "name": name,
        "absoluteBoundingBox": {"x": x, "y": y, "width": w, "height": h},
        **extra,
    }


def solid(r: float, g: float, b: float, a: float = 1.0, **extra: Any) -> dict[str, Any]:
    """A raw SOLID paint."""
    return {"type": "SOLID", "color": {"r": r, "g": g, "b": b, "a": a}, **extra}
