"""Generate a project from a live Figma file: fetch frame detail and exported images first."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

from figma_to_pyside6.adapters.figma_api import (
    build_images_url,
    build_nodes_url,
    frame_from_nodes_response,
)
from figma_to_pyside6.adapters.figma_client import FigmaApiError, FigmaClient
from figma_to_pyside6.application.conversion_service import convert_document
from figma_to_pyside6.application.raster import collect_raster_nodes, raster_bounds
from figma_to_pyside6.domain.models import ConversionResult, FigmaDocument, FigmaFrame, FigmaNode

logger = logging.getLogger(__name__)


class GenerationCancelled(Exception):  # noqa: N818 - a control-flow signal, not an error
    """Raised by a progress callback to stop a running generation."""


ProgressFn = Callable[[str, int], None]
"""Called with a stage description and the overall progress, 0-100 (never decreasing).

The callback may raise :class:`GenerationCancelled`; the pipeline then stops at that point and
nothing is written to the output directory.
"""

IMAGE_BATCH_SIZE = 25
DOWNLOAD_WORKERS = 8
EXPORT_SCALE = 2.0  # exports are 2x so they stay sharp when the page is scaled up
MAX_EXPORT_PIXELS = 24_000_000  # Figma refuses renders much larger than this

# Share of the overall progress each stage covers.
LOAD_END = 30  # 0-30: fetching the selected frames in full
EXPORT_END = 40  # 30-40: asking Figma to render vector and image layers
DOWNLOAD_END = 90  # 40-90: downloading the rendered PNGs
WRITE_AT = 92  # then writing the project; 100 when done


def _no_progress(_message: str, _percent: int) -> None:
    return None


def _between(start: int, end: int, done: int, total: int) -> int:
    """Linear position inside the ``start``-``end`` stage after ``done`` of ``total`` steps."""
    return start + round((end - start) * done / max(total, 1))


def fetch_detailed_frames(
    client: FigmaClient,
    file_key: str,
    frames: Sequence[FigmaFrame],
    progress: ProgressFn = _no_progress,
) -> list[FigmaFrame]:
    """Replace shallow frames (from the verification step) with their complete subtrees."""
    detailed = []
    for index, frame in enumerate(frames):
        progress(
            f"Loading frame {index + 1}/{len(frames)}: {frame.name}",
            _between(0, LOAD_END, index, len(frames)),
        )
        payload = client.get_json(build_nodes_url(file_key, [frame.node_id]))
        detailed.append(frame_from_nodes_response(payload, frame.node_id, frame.container_name))
    progress("Frames loaded", LOAD_END)
    return detailed


def _export_scale(node: FigmaNode) -> float:
    _, _, width, height = raster_bounds(node)
    pixels = max(width, 1) * max(height, 1)
    return EXPORT_SCALE if pixels * EXPORT_SCALE**2 <= MAX_EXPORT_PIXELS else 1.0


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _request_export_links(
    client: FigmaClient,
    file_key: str,
    nodes: dict[str, FigmaNode],
    progress: ProgressFn,
    warnings: list[str],
) -> dict[str, str]:
    """Ask Figma to render the layers; returns the temporary download link per node id."""
    by_scale: dict[float, list[str]] = {}
    for node_id, node in nodes.items():
        by_scale.setdefault(_export_scale(node), []).append(node_id)
    batches = [
        (scale, batch)
        for scale, ids in by_scale.items()
        for batch in _chunks(ids, IMAGE_BATCH_SIZE)
    ]
    links: dict[str, str] = {}
    for done, (scale, batch) in enumerate(batches):
        progress(
            f"Rendering {len(nodes)} vector and image layers in Figma",
            _between(LOAD_END, EXPORT_END, done, len(batches)),
        )
        try:
            reply = client.get_json(build_images_url(file_key, batch, scale))
        except FigmaApiError as exc:
            warnings.append(f"Could not export {len(batch)} layer(s): {exc}")
            continue
        links.update({i: url for i, url in (reply.get("images") or {}).items() if url})
    progress("Layers rendered", EXPORT_END)
    return links


def _download_exports(
    client: FigmaClient, links: dict[str, str], progress: ProgressFn
) -> dict[str, bytes]:
    """Download the rendered PNGs in parallel, reporting progress as each one arrives."""

    def download(item: tuple[str, str]) -> tuple[str, bytes | None]:
        node_id, url = item
        try:
            return node_id, client.get_bytes(url)
        except FigmaApiError:
            return node_id, None

    assets: dict[str, bytes] = {}
    pool = ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS)
    try:
        futures = [pool.submit(download, item) for item in links.items()]
        for done, future in enumerate(as_completed(futures), start=1):
            node_id, data = future.result()
            if data:
                assets[node_id] = data
            progress(
                f"Downloading images {done}/{len(links)}",
                _between(EXPORT_END, DOWNLOAD_END, done, len(links)),
            )
    finally:
        # On cancellation the queued downloads are dropped instead of all being fetched.
        pool.shutdown(wait=True, cancel_futures=True)
    return assets


def fetch_raster_assets(
    client: FigmaClient,
    file_key: str,
    frames: Sequence[FigmaFrame],
    progress: ProgressFn = _no_progress,
) -> tuple[dict[str, bytes], list[str]]:
    """Export every layer the pages draw as an image and download the PNGs.

    Returns:
        PNG bytes by node id, and warnings for layers Figma could not export.
    """
    nodes: dict[str, FigmaNode] = {}
    for frame in frames:
        for node in collect_raster_nodes(frame):
            nodes.setdefault(node.node_id, node)
    if not nodes:
        progress("No images to export", DOWNLOAD_END)
        return {}, []

    warnings: list[str] = []
    links = _request_export_links(client, file_key, nodes, progress, warnings)
    assets = _download_exports(client, links, progress)
    missing = len(nodes) - len(assets)
    if missing:
        warnings.append(f"{missing} of {len(nodes)} exported layer(s) could not be downloaded")
    return assets, warnings


def generate_from_figma(
    client: FigmaClient,
    file_key: str,
    document: FigmaDocument,
    project_name: str,
    output_dir: str | Path,
    progress: ProgressFn = _no_progress,
) -> ConversionResult:
    """Fetch the selected frames in full, export their raster layers, then generate.

    Args:
        client: Figma connection (the token lives inside it, in memory only).
        file_key: Figma file key from the link.
        document: Document whose ``frames`` are the (shallow) frames the user selected.
        project_name: Window title and project name of the generated app.
        output_dir: Target directory.
        progress: Called with a stage description and the overall progress (0-100).
    """
    frames = fetch_detailed_frames(client, file_key, document.frames, progress)
    assets, export_warnings = fetch_raster_assets(client, file_key, frames, progress)
    progress("Writing project files", WRITE_AT)
    result = convert_document(
        replace(document, frames=frames), project_name, output_dir, assets=assets
    )
    result.warnings[:0] = export_warnings
    progress("Done", 100)
    return result
