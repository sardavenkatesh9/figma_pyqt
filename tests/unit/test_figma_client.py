"""Tests for the blocking Figma client (urllib is replaced; nothing touches the network)."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from typing import Any

import pytest

from figma_to_pyside6.adapters import figma_client
from figma_to_pyside6.adapters.figma_client import FigmaApiError, UrllibFigmaClient

SECRET = "figd_super-secret-token"


class _Response(io.BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Record what ``urlopen`` was asked to open; the reply is configurable via ``reply``."""
    requests: list[Any] = []
    state: dict[str, Any] = {"body": b"{}", "error": None}

    def fake_urlopen(target: Any, timeout: float | None = None) -> _Response:
        requests.append((target, timeout))
        if state["error"] is not None:
            raise state["error"]
        return _Response(state["body"])

    monkeypatch.setattr(figma_client.urllib.request, "urlopen", fake_urlopen)
    requests.append(state)  # first element is the control dict
    return requests


def _state(opened: list[Any]) -> dict[str, Any]:
    return opened[0]


def test_get_json_sends_the_token_header_and_a_timeout(opened: list[Any]) -> None:
    _state(opened)["body"] = json.dumps({"ok": True}).encode()

    payload = UrllibFigmaClient(SECRET, timeout=12).get_json("https://api.figma.com/v1/files/K")

    request, timeout = opened[1]
    assert payload == {"ok": True}
    assert isinstance(request, urllib.request.Request)
    assert request.get_header("X-figma-token") == SECRET
    assert timeout == 12


def test_downloads_never_carry_the_token(opened: list[Any]) -> None:
    _state(opened)["body"] = b"PNGDATA"

    data = UrllibFigmaClient(SECRET).get_bytes("https://s3.example/signed.png")

    target, _ = opened[1]
    assert data == b"PNGDATA"
    assert target == "https://s3.example/signed.png"  # a bare URL: no Request, no headers


@pytest.mark.parametrize(
    ("code", "fragment"),
    [(403, "refused access"), (404, "could not find"), (429, "rate limit"), (500, "HTTP 500")],
)
def test_http_errors_become_readable_messages(opened: list[Any], code: int, fragment: str) -> None:
    _state(opened)["error"] = urllib.error.HTTPError("u", code, "x", None, None)  # type: ignore[arg-type]

    with pytest.raises(FigmaApiError, match=fragment):
        UrllibFigmaClient(SECRET).get_json("https://api.figma.com/v1/files/K")


def test_network_errors_and_bad_payloads_are_reported(opened: list[Any]) -> None:
    client = UrllibFigmaClient(SECRET)
    _state(opened)["error"] = urllib.error.URLError("dns")
    with pytest.raises(FigmaApiError, match="Could not reach Figma"):
        client.get_json("https://api.figma.com/v1/files/K")
    with pytest.raises(FigmaApiError, match="Could not download"):
        client.get_bytes("https://s3.example/x.png")

    _state(opened)["error"] = None
    _state(opened)["body"] = b"<html>"
    with pytest.raises(FigmaApiError, match="not valid JSON"):
        client.get_json("https://api.figma.com/v1/files/K")
    _state(opened)["body"] = b"[1, 2]"
    with pytest.raises(FigmaApiError, match="unexpected response"):
        client.get_json("https://api.figma.com/v1/files/K")


def test_error_messages_never_contain_the_token(opened: list[Any]) -> None:
    leaky_url = "https://api.figma.com/?t=" + SECRET
    _state(opened)["error"] = urllib.error.HTTPError(leaky_url, 403, "x", None, None)  # type: ignore[arg-type]

    with pytest.raises(FigmaApiError) as caught:
        UrllibFigmaClient(SECRET).get_json("https://api.figma.com/v1/files/K")

    assert SECRET not in str(caught.value)
    assert caught.value.__cause__ is None  # the original error (and its URL) is not chained
