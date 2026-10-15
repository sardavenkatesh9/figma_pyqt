"""The live-Figma generation pipeline, driven by a fake Figma connection."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from helpers import FakeFigmaClient, raw_node, solid

from figma_to_pyside6.adapters.figma_client import FigmaApiError
from figma_to_pyside6.application.figma_pipeline import (
    IMAGE_BATCH_SIZE,
    GenerationCancelled,
    fetch_detailed_frames,
    fetch_raster_assets,
    generate_from_figma,
)
from figma_to_pyside6.application.raster import asset_filename
from figma_to_pyside6.domain.models import FigmaDocument, FigmaFrame

FILE_KEY = "FileKey123"


def _frame_dict(frame_id: str, vectors: int = 2, **extra: Any) -> dict[str, Any]:
    children = [
        raw_node(
            "VECTOR",
            f"v{i}",
            10 + (i % 30) * 12,
            60 + (i // 30) * 12,
            10,
            10,
            id=f"{frame_id}:v{i}",
        )
        for i in range(vectors)
    ]
    children.append(
        raw_node("TEXT", "Title", 10, 40, 80, 14, characters="Hello", id=f"{frame_id}:t")
    )
    return raw_node(
        "FRAME",
        f"Screen {frame_id}",
        0,
        0,
        400,
        300,
        id=frame_id,
        children=children,
        fills=[solid(0.1, 0.1, 0.1)],
        **extra,
    )


def _document(*frame_ids: str) -> FigmaDocument:
    # The shallow frames the verification step produced: id and name only, no children.
    frames = [FigmaFrame(i, f"Shallow {i}", "FRAME", width=400, height=300) for i in frame_ids]
    return FigmaDocument("File", "0:0", frames, source="link")


def test_detailed_frames_replace_the_shallow_ones() -> None:
    client = FakeFigmaClient({"1:1": _frame_dict("1:1")})

    (frame,) = fetch_detailed_frames(client, FILE_KEY, _document("1:1").frames)

    assert frame.name == "Screen 1:1" and len(frame.children) == 3
    assert client.json_urls == [f"https://api.figma.com/v1/files/{FILE_KEY}/nodes?ids=1:1"]


def test_generate_writes_pages_with_text_boxes_and_exported_images(tmp_path: Path) -> None:
    client = FakeFigmaClient({"1:1": _frame_dict("1:1"), "2:2": _frame_dict("2:2", vectors=1)})
    events: list[tuple[str, int]] = []

    result = generate_from_figma(
        client,
        FILE_KEY,
        _document("1:1", "2:2"),
        "App",
        tmp_path,
        lambda m, p: events.append((m, p)),
    )

    assets = tmp_path / "src" / "ui" / "assets"

    def exported(node_id: str) -> str:
        return asset_filename(client.image_for(node_id))

    assert sorted(p.name for p in assets.glob("*.png")) == sorted(
        exported(i) for i in ("1:1:v0", "1:1:v1", "2:2:v0")
    )
    page = (tmp_path / "src/ui/pages/screen_1_1_page.py").read_text(encoding="utf-8")
    assert f'image(canvas, "{exported("1:1:v0")}"' in page
    assert 'text(canvas, "Hello"' in page
    assert result.warnings == []
    assert any("Loading frame 1/2" in m for m, _ in events)
    assert any("Writing project files" in m for m, _ in events)
    assert {f.name for f in result.generated_files} >= {"main.py", exported("2:2:v0")}


def test_downloads_use_only_the_signed_links_and_never_the_api_host(tmp_path: Path) -> None:
    client = FakeFigmaClient({"1:1": _frame_dict("1:1")})

    generate_from_figma(client, FILE_KEY, _document("1:1"), "App", tmp_path)

    assert client.byte_urls and all(u.startswith("https://img/") for u in client.byte_urls)


def test_layers_are_requested_in_batches() -> None:
    count = IMAGE_BATCH_SIZE * 2 + 5
    client = FakeFigmaClient({"1:1": _frame_dict("1:1", vectors=count)})
    frames = fetch_detailed_frames(client, FILE_KEY, _document("1:1").frames)
    client.json_urls.clear()

    assets, warnings = fetch_raster_assets(client, FILE_KEY, frames)

    image_calls = [u for u in client.json_urls if "/images/" in u]
    assert len(image_calls) == 3 and all("scale=2" in u for u in image_calls)
    assert len(assets) == count and warnings == []


def test_huge_layers_are_exported_at_scale_one() -> None:
    big = raw_node("VECTOR", "big", 0, 0, 4000, 4000, id="1:big")
    frame = raw_node("FRAME", "F", 0, 0, 5000, 5000, id="1:1", children=[big])
    client = FakeFigmaClient({"1:1": frame})
    frames = fetch_detailed_frames(client, FILE_KEY, _document("1:1").frames)
    client.json_urls.clear()

    fetch_raster_assets(client, FILE_KEY, frames)

    assert "scale=1" in client.json_urls[0] and "scale=2" not in client.json_urls[0]


def test_unexportable_layers_are_reported_and_left_out(tmp_path: Path) -> None:
    client = FakeFigmaClient({"1:1": _frame_dict("1:1")}, missing_images=frozenset({"1:1:v1"}))

    result = generate_from_figma(client, FILE_KEY, _document("1:1"), "App", tmp_path)

    assert any("1 of 2 exported layer(s) could not be downloaded" in w for w in result.warnings)
    assert any("1 vector/image layer(s) were left out" in w for w in result.warnings)
    page = (tmp_path / "src/ui/pages/screen_1_1_page.py").read_text(encoding="utf-8")
    assert asset_filename(client.image_for("1:1:v0")) in page
    assert asset_filename(client.image_for("1:1:v1")) not in page


def test_a_failed_image_request_does_not_abort_generation(tmp_path: Path) -> None:
    class Flaky(FakeFigmaClient):
        def get_json(self, url: str) -> dict[str, Any]:
            if "/images/" in url:
                raise FigmaApiError("Figma rate limit reached; wait a moment and try again.")
            return super().get_json(url)

    result = generate_from_figma(
        Flaky({"1:1": _frame_dict("1:1")}), FILE_KEY, _document("1:1"), "App", tmp_path
    )

    assert any("rate limit" in w for w in result.warnings)
    assert (tmp_path / "src/ui/pages/screen_1_1_page.py").exists()  # the page is still produced


def test_missing_frame_in_the_response_is_an_error(tmp_path: Path) -> None:
    class Empty(FakeFigmaClient):
        def get_json(self, url: str) -> dict[str, Any]:
            return {"nodes": {"1:1": None}}

    with pytest.raises(ValueError, match="could not be found"):
        generate_from_figma(Empty({}), FILE_KEY, _document("1:1"), "App", tmp_path)


def test_regeneration_removes_images_no_page_uses_any_more(tmp_path: Path) -> None:
    client = FakeFigmaClient({"1:1": _frame_dict("1:1", vectors=3)})
    generate_from_figma(client, FILE_KEY, _document("1:1"), "App", tmp_path)
    assets = tmp_path / "src" / "ui" / "assets"
    (assets / "my_logo.png").write_bytes(b"mine")

    client.frames["1:1"] = _frame_dict("1:1", vectors=1)
    generate_from_figma(client, FILE_KEY, _document("1:1"), "App", tmp_path)

    assert sorted(p.name for p in assets.glob("*.png")) == sorted(
        ["my_logo.png", asset_filename(client.image_for("1:1:v0"))]
    )  # stale fig_* files go; files that are not ours stay


def test_progress_is_a_monotonic_percentage_from_start_to_finish(tmp_path: Path) -> None:
    client = FakeFigmaClient({"1:1": _frame_dict("1:1", vectors=30), "2:2": _frame_dict("2:2")})
    events: list[tuple[str, int]] = []

    generate_from_figma(
        client,
        FILE_KEY,
        _document("1:1", "2:2"),
        "App",
        tmp_path,
        lambda m, p: events.append((m, p)),
    )

    percents = [p for _, p in events]
    assert percents == sorted(percents)  # never goes backwards
    assert percents[0] == 0 and percents[-1] == 100 and all(0 <= p <= 100 for p in percents)
    stages = [m.split(":")[0].split(" ")[0] for m, _ in events]
    for expected in ("Loading", "Rendering", "Downloading", "Writing", "Done"):
        assert expected in stages  # every stage is reported
    downloads = [p for m, p in events if m.startswith("Downloading")]
    assert len(downloads) == 32 and 40 < downloads[0] < downloads[-1] <= 90  # one step per image


def test_progress_skips_straight_to_writing_when_there_is_nothing_to_download(
    tmp_path: Path,
) -> None:
    text_only = raw_node(
        "FRAME",
        "T",
        0,
        0,
        100,
        100,
        id="9:9",
        children=[raw_node("TEXT", "t", 0, 0, 50, 14, characters="Hi")],
    )
    events: list[tuple[str, int]] = []

    generate_from_figma(
        FakeFigmaClient({"9:9": text_only}),
        FILE_KEY,
        _document("9:9"),
        "App",
        tmp_path,
        lambda m, p: events.append((m, p)),
    )

    assert ("No images to export", 90) in events
    assert not any(m.startswith(("Rendering", "Downloading")) for m, _ in events)
    assert events[-1] == ("Done", 100)


def test_identical_exports_are_stored_once_and_reused(tmp_path: Path) -> None:
    client = FakeFigmaClient({"1:1": _frame_dict("1:1", vectors=5)}, identical_images=True)

    result = generate_from_figma(client, FILE_KEY, _document("1:1"), "App", tmp_path)

    files = list((tmp_path / "src" / "ui" / "assets").glob("*.png"))
    assert len(files) == 1  # five exported layers, one picture on disk
    page = (tmp_path / "src/ui/pages/screen_1_1_page.py").read_text(encoding="utf-8")
    assert page.count(f'image(canvas, "{files[0].name}"') == 5  # all five reuse it
    assert [p.name for p in result.generated_files].count(files[0].name) == 1  # listed once


def test_different_exports_keep_separate_files(tmp_path: Path) -> None:
    client = FakeFigmaClient({"1:1": _frame_dict("1:1", vectors=4)})

    generate_from_figma(client, FILE_KEY, _document("1:1"), "App", tmp_path)

    assert len(list((tmp_path / "src" / "ui" / "assets").glob("*.png"))) == 4


def test_the_same_artwork_on_several_frames_is_shared_between_pages(tmp_path: Path) -> None:
    client = FakeFigmaClient(
        {"1:1": _frame_dict("1:1", vectors=2), "2:2": _frame_dict("2:2", vectors=2)},
        identical_images=True,
    )

    generate_from_figma(client, FILE_KEY, _document("1:1", "2:2"), "App", tmp_path)

    assert len(list((tmp_path / "src" / "ui" / "assets").glob("*.png"))) == 1

    def image_used_by(page: str) -> str:
        source = (tmp_path / "src" / "ui" / "pages" / page).read_text(encoding="utf-8")
        match = re.search(r'image\(canvas, "(fig_\w+\.png)"', source)
        assert match is not None
        return match[1]

    names = {image_used_by("screen_1_1_page.py"), image_used_by("screen_2_2_page.py")}
    assert len(names) == 1


def test_cancelling_stops_further_downloads_and_writes_nothing(tmp_path: Path) -> None:
    client = FakeFigmaClient({"1:1": _frame_dict("1:1", vectors=30)})
    seen_downloads = 0

    def progress(message: str, _percent: int) -> None:
        nonlocal seen_downloads
        if message.startswith("Downloading"):
            seen_downloads += 1
            if seen_downloads == 3:
                raise GenerationCancelled

    with pytest.raises(GenerationCancelled):
        generate_from_figma(client, FILE_KEY, _document("1:1"), "App", tmp_path, progress)

    assert len(client.byte_urls) < 30  # the queued downloads were dropped, not all fetched
    assert not (tmp_path / "main.py").exists()  # and no half-finished project is left
