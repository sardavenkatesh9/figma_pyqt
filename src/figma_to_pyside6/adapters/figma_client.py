"""Blocking Figma REST client used by the background generation job.

Uses only the standard library. The access token is sent to ``api.figma.com`` and never to
the temporary image-download links, which are plain pre-signed URLs.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Protocol

from figma_to_pyside6 import config


class FigmaApiError(RuntimeError):
    """A request to Figma failed; the message is safe to show to the user."""


class FigmaClient(Protocol):
    """What the generation pipeline needs from a Figma connection."""

    def get_json(self, url: str) -> dict[str, Any]:
        """GET a Figma REST URL and return the decoded JSON."""
        ...

    def get_bytes(self, url: str) -> bytes:
        """Download a pre-signed asset URL (no credentials are attached)."""
        ...


_HTTP_MESSAGES = {
    403: "Figma refused access (check the token and file permissions).",
    404: "Figma could not find that file or layer.",
    429: "Figma rate limit reached; wait a moment and try again.",
}


class UrllibFigmaClient:
    """:class:`FigmaClient` backed by ``urllib``."""

    def __init__(self, token: str, timeout: float = config.FIGMA_REQUEST_TIMEOUT_MS / 1000) -> None:
        """Create a client; ``token`` is kept in memory only."""
        self._token = token
        self._timeout = timeout

    def get_json(self, url: str) -> dict[str, Any]:
        """GET ``url`` with the Figma token header and decode the JSON body."""
        request = urllib.request.Request(url, headers={"X-Figma-Token": self._token})
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise FigmaApiError(
                _HTTP_MESSAGES.get(exc.code, f"Figma returned HTTP {exc.code}.")
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise FigmaApiError("Could not reach Figma. Check your connection.") from None
        except json.JSONDecodeError:
            raise FigmaApiError("Figma sent a response that is not valid JSON.") from None
        if not isinstance(payload, dict):
            raise FigmaApiError("Figma sent an unexpected response.")
        return payload

    def get_bytes(self, url: str) -> bytes:
        """Download ``url`` without any Figma credentials."""
        try:
            with urllib.request.urlopen(url, timeout=self._timeout) as response:
                return bytes(response.read())
        except (urllib.error.URLError, TimeoutError, OSError):
            raise FigmaApiError("Could not download an exported image from Figma.") from None
