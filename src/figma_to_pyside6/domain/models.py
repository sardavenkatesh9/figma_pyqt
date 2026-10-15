"""Domain models shared by adapters, services and the GUI."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Color:
    """An RGBA color with 0-1 float channels, as Figma reports them."""

    r: float = 0.0
    g: float = 0.0
    b: float = 0.0
    a: float = 1.0


@dataclass(frozen=True, slots=True)
class GradientStop:
    """One color stop of a gradient; ``position`` is 0-1."""

    color: Color
    position: float


@dataclass(slots=True)
class Paint:
    """A fill or stroke layer.

    ``kind`` is the Figma paint type (SOLID, GRADIENT_LINEAR, GRADIENT_RADIAL, IMAGE, ...).
    ``handles`` are the gradient handle positions in the node's 0-1 coordinate space.
    """

    kind: str
    color: Color | None = None
    opacity: float = 1.0
    stops: list[GradientStop] = field(default_factory=list)
    handles: list[tuple[float, float]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Effect:
    """A visual effect: DROP_SHADOW, INNER_SHADOW, LAYER_BLUR or BACKGROUND_BLUR."""

    kind: str
    color: Color = Color(0.0, 0.0, 0.0, 0.25)
    offset_x: float = 0.0
    offset_y: float = 0.0
    radius: float = 0.0


@dataclass(frozen=True, slots=True)
class TextStyle:
    """Typography of a TEXT node."""

    font_family: str = "Inter"
    font_size: float = 14.0
    font_weight: int = 400
    italic: bool = False
    align_h: str = "LEFT"
    align_v: str = "TOP"
    letter_spacing: float = 0.0
    line_height: float | None = None
    text_case: str = "ORIGINAL"
    underline: bool = False


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
    visible: bool = True
    opacity: float = 1.0
    fills: list[Paint] = field(default_factory=list)
    strokes: list[Paint] = field(default_factory=list)
    stroke_weight: float = 0.0
    corner_radii: tuple[float, float, float, float] | None = None  # tl, tr, br, bl
    effects: list[Effect] = field(default_factory=list)
    text_style: TextStyle | None = None
    rotation: float = 0.0
    is_mask: bool = False
    render_bounds: tuple[int, int, int, int] | None = None  # x, y, width, height

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

    def count_nodes(self) -> int:
        """Number of nodes in this subtree, including this one."""
        return 1 + sum(child.count_nodes() for child in self.children)

    @property
    def is_frame(self) -> bool:
        """Whether this node is a top-level FRAME."""
        return self.type == "FRAME"


@dataclass(slots=True)
class FigmaFrame(FigmaNode):
    """A FRAME node, rendered as one generated page."""

    container_name: str | None = None  # page or section the frame lives in


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
