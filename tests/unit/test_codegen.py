"""Tests for codegen."""

from __future__ import annotations

from figma_to_pyside6.application.codegen import SlugAllocator


def test_slug_allocator_never_returns_duplicates() -> None:

    allocator = SlugAllocator()
    slugs = [allocator.allocate(n) for n in ["a", "a", "a_2", "A", "a-2", "", "class", "7up"]]

    assert slugs == ["a", "a_2", "a_2_2", "a_3", "a_2_3", "screen", "screen_class", "screen_7up"]
    assert len(set(slugs)) == len(slugs)


def test_slug_allocator_is_linear_for_many_identical_names() -> None:

    allocator = SlugAllocator()

    slugs = [allocator.allocate("Home") for _ in range(2000)]

    assert slugs[:3] == ["home", "home_2", "home_3"]
    assert len(set(slugs)) == 2000


def test_nav_titles_number_repeated_frame_names() -> None:
    from figma_to_pyside6.application.codegen import nav_titles, plan_pages, render_pages_registry
    from figma_to_pyside6.domain.models import FigmaFrame

    frames = [FigmaFrame(str(i), name, "FRAME") for i, name in enumerate(["A", "B", "A", "A"])]
    plans = plan_pages(frames)

    assert nav_titles(plans) == ["A (1)", "B", "A (2)", "A (3)"]
    registry = render_pages_registry(plans)
    assert '("A (2)", A2Page),' in registry and '("B", BPage),' in registry
