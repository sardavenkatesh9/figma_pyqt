"""Domain models shared by adapters, services and the GUI."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class FigmaNode:
    """A node in the Figma layer tree."""

    node_id: str
    name: str
    type: str
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    children: list[FigmaNode] = field(default_factory=list)
    component_id: str | None = None
    fill_color: tuple[float, float, float] | None = None
    characters: str | None = None
    warnings: list[str] = field(default_factory=list)

    def iter_warnings(self, path: str = "") -> Iterator[str]:
        """Yield this node's and its descendants' warnings, prefixed with the node path."""
        here = f"{path} / {self.name}" if path else self.name
        for warning in self.warnings:
            yield f"{here}: {warning}"
        for child in self.children:
            yield from child.iter_warnings(here)

    def summary(self) -> dict[str, object]:
        """Return id, name and size, as shown by ``inspect`` and in the manifest."""
        return {"id": self.node_id, "name": self.name, "width": self.width, "height": self.height}

    @property
    def is_frame(self) -> bool:
        """Whether this node is a top-level FRAME."""
        return self.type == "FRAME"


@dataclass(slots=True)
class FigmaFrame(FigmaNode):
    """A FRAME node, rendered as one generated page."""


@dataclass(slots=True)
class FigmaDocument:
    """A parsed Figma document and its frames."""

    name: str
    node_id: str
    frames: list[FigmaFrame] = field(default_factory=list)
    source: str | None = None


@dataclass(slots=True)
class ConversionResult:
    """Outcome of a generation run."""

    project_name: str
    output_dir: Path
    generated_files: list[Path]
    manifest_path: Path
    validation_report_path: Path
    warnings: list[str] = field(default_factory=list)
