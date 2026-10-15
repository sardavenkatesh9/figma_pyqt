"""Shared test helpers (importable because ``tests`` is on pytest's pythonpath)."""

from __future__ import annotations

import json
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
