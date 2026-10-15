"""Generate a runnable PySide6 project, one page per Figma frame.

File ownership on regeneration:

* *Generated* files carry :data:`GENERATED_MARKER` and are rewritten every run
  (main entry point, main window, base page, page registry, one module per frame).
* *User-owned* files (README, pyproject, style sheets, package ``__init__`` files) are
  only created when missing, so hand edits survive regeneration.
* A generated file that has lost its marker is treated as hand-written: it is left
  alone and reported in :attr:`ConversionResult.warnings`.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from figma_to_pyside6 import config
from figma_to_pyside6.application import codegen
from figma_to_pyside6.application.codegen import GENERATED_MARKER, PagePlan
from figma_to_pyside6.application.raster import asset_filename
from figma_to_pyside6.application.validation_service import (
    MANIFEST_NAME,
    validate_generated_project,
    write_validation_report,
)
from figma_to_pyside6.domain.models import ConversionResult, FigmaDocument
from figma_to_pyside6.theme import components_qss, main_qss, tokens_qss

logger = logging.getLogger(__name__)


class _ProjectWriter:
    """Writes project files while honoring the generated/user-owned distinction."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.files: list[Path] = []
        self.warnings: list[str] = []

    def generated(self, relative: str, content: str) -> None:
        """Write a generated file, unless it was taken over by hand."""
        path = self.base_dir / relative
        if path.exists() and GENERATED_MARKER not in path.read_text(encoding="utf-8"):
            message = f"{relative} has no generator marker; kept your version"
            logger.warning(message)
            self.warnings.append(message)
        else:
            self._write(path, content)
        self.files.append(path)

    def user_owned(self, relative: str, content: str) -> None:
        """Create a user-owned file only if it does not exist yet."""
        path = self.base_dir / relative
        if not path.exists():
            self._write(path, content)
        self.files.append(path)

    def asset(self, relative: str, data: bytes) -> None:
        """Write an exported image; images carry no marker and are always refreshed."""
        path = self.base_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.files.append(path)

    @staticmethod
    def _write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _remove_stale_pages(pages_dir: Path, plans: list[PagePlan]) -> None:
    """Delete generated pages of frames that are no longer part of the document."""
    wanted = {plan.module_file for plan in plans}
    for stale in pages_dir.glob("*_page.py"):
        if stale.name not in wanted and GENERATED_MARKER in stale.read_text(encoding="utf-8"):
            logger.info("Removing stale generated page %s", stale)
            stale.unlink()


def _remove_stale_assets(assets_dir: Path, wanted: set[str]) -> None:
    """Delete exported images (``fig_*.png``) that no page uses any more."""
    if assets_dir.is_dir():
        for stale in assets_dir.glob("fig_*.png"):
            if stale.name not in wanted:
                stale.unlink()


def _write_project_files(
    writer: _ProjectWriter,
    document: FigmaDocument,
    project_name: str,
    plans: list[PagePlan],
    assets: Mapping[str, bytes],
) -> None:
    pages = "src/ui/pages"
    writer.generated("main.py", codegen.render_main())
    writer.user_owned("src/__init__.py", "")
    writer.user_owned("src/ui/__init__.py", "")
    writer.generated("src/ui/main_window.py", codegen.render_main_window(project_name))
    writer.generated(f"{pages}/base_page.py", codegen.BASE_PAGE_SOURCE)
    writer.generated(f"{pages}/widgets.py", codegen.WIDGETS_SOURCE)
    available: dict[str, str] = {}  # node id -> shared file name
    for node_id, data in assets.items():
        name = asset_filename(data)
        if name not in available.values():
            writer.asset(f"src/ui/assets/{name}", data)
        available[node_id] = name
    if len(set(available.values())) < len(available):
        logger.info(
            "%d exported layers share %d image files", len(available), len(set(available.values()))
        )
    writer.generated(f"{pages}/__init__.py", codegen.render_pages_registry(plans))
    for plan in plans:
        rendered = codegen.render_page(plan, available)
        writer.generated(f"{pages}/{plan.module_file}", rendered.source)
        writer.warnings.extend(rendered.warnings)
    writer.user_owned("src/ui/styles/tokens.qss", tokens_qss())
    writer.user_owned("src/ui/styles/main.qss", main_qss())
    writer.user_owned("src/ui/styles/components.qss", components_qss())
    writer.user_owned("README.md", codegen.render_readme(project_name, document.name))
    writer.user_owned("pyproject.toml", codegen.render_pyproject())


def _build_manifest(
    document: FigmaDocument, project_name: str, plans: list[PagePlan], writer: _ProjectWriter
) -> dict[str, object]:
    return {
        "project_name": project_name,
        "document_name": document.name,
        "created_at": datetime.now(UTC).isoformat(),
        "frames": [
            {**plan.frame.summary(), "page": f"src/ui/pages/{plan.module_file}"} for plan in plans
        ],
        "files": [
            {
                "path": path.relative_to(writer.base_dir).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size": path.stat().st_size,
            }
            for path in writer.files
        ],
    }


def convert_document(
    document: FigmaDocument,
    project_name: str = config.DEFAULT_PROJECT_NAME,
    output_dir: str | Path | None = None,
    assets: Mapping[str, bytes] | None = None,
) -> ConversionResult:
    """Generate a PySide6 project with one page module per frame.

    Args:
        document: Parsed Figma document; its ``frames`` become pages.
        project_name: Window title and project name.
        output_dir: Target directory; defaults to ``./generated_project``.
        assets: Exported PNG bytes by Figma node id, for layers that widgets cannot draw
            (vectors, icons, bitmap fills, masks). Without them such layers are skipped and
            reported in ``warnings``.

    Returns:
        Paths of the generated files, manifest and validation report. ``warnings`` lists
        generated files that were left untouched because they were edited by hand.
    """
    base_dir = Path(output_dir) if output_dir is not None else config.default_output_dir()
    plans = codegen.plan_pages(document.frames)
    pages_dir = base_dir / "src" / "ui" / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    _remove_stale_pages(pages_dir, plans)
    assets = assets or {}
    _remove_stale_assets(
        base_dir / "src" / "ui" / "assets", {asset_filename(d) for d in assets.values()}
    )

    writer = _ProjectWriter(base_dir)
    _write_project_files(writer, document, project_name, plans, assets)
    for plan in plans:
        writer.warnings.extend(plan.frame.iter_warnings())

    manifest_path = base_dir / MANIFEST_NAME
    manifest = _build_manifest(document, project_name, plans, writer)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    report = validate_generated_project(base_dir)
    report["project_name"] = project_name
    report["document_name"] = document.name
    report_path = write_validation_report(base_dir, report)

    logger.info("Generated %d pages in %s", len(plans), base_dir)
    return ConversionResult(
        project_name=project_name,
        output_dir=base_dir,
        generated_files=writer.files,
        manifest_path=manifest_path,
        validation_report_path=report_path,
        warnings=writer.warnings,
    )
