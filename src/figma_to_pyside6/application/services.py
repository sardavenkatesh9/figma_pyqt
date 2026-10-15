from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from figma_to_pyside6.adapters.figma_json import load_figma_document
from figma_to_pyside6.domain.models import AppSettings


@dataclass(slots=True)
class ProjectContext:
    project_name: str
    input_path: Path | None = None
    settings: AppSettings = AppSettings()


def open_project(path: str | Path) -> ProjectContext:
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"Project or source file does not exist: {input_path}")
    return ProjectContext(project_name=input_path.stem, input_path=input_path)


def inspect_input(path: str | Path) -> dict[str, object]:
    document = load_figma_document(path)
    return {
        "name": document.name,
        "frames": [
            {"id": frame.node_id, "name": frame.name, "width": frame.width, "height": frame.height}
            for frame in document.frames
        ],
    }
