from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

_FILE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def extract_figma_file_key(link: str) -> str:
    parsed = urlsplit(link.strip())
    if parsed.scheme != "https" or parsed.hostname not in {"figma.com", "www.figma.com"}:
        raise ValueError("Enter an HTTPS link from figma.com.")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0] not in {"design", "file"}:
        raise ValueError("Use a Figma design or file link.")

    file_key = parts[1]
    if not _FILE_KEY_PATTERN.fullmatch(file_key):
        raise ValueError("The Figma link does not contain a valid file key.")

    return file_key


def extract_figma_node_id(link: str) -> str | None:
    node_ids = parse_qs(urlsplit(link.strip()).query).get("node-id", [])
    if not node_ids:
        return None

    node_id = node_ids[0].replace("-", ":", 1)
    if not re.fullmatch(r"\d+:\d+", node_id):
        raise ValueError("The Figma link contains an invalid node id.")
    return node_id
