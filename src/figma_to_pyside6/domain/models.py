from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class FigmaNode:
    node_id: str
    name: str
    type: str
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    children: list["FigmaNode"] = field(default_factory=list)
    component_id: str | None = None
    fill_color: tuple[float, float, float] | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def is_frame(self) -> bool:
        return self.type == "FRAME"


@dataclass(slots=True)
class FigmaFrame(FigmaNode):
    pass


@dataclass(slots=True)
class FigmaDocument:
    name: str
    node_id: str
    frames: list[FigmaFrame] = field(default_factory=list)
    source: str | None = None


@dataclass(slots=True)
class ConversionResult:
    project_name: str
    output_dir: Path
    generated_files: list[Path]
    manifest_path: Path
    validation_report_path: Path
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AppSettings:
    project_name: str = "GeneratedApp"
    main_window_title: str = "Generated App"
    package_name: str = "ui"
    output_directory: str = "generated_project"
    theme: str = "light"
    validate_output: bool = True
    background_tasks_enabled: bool = True

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()
