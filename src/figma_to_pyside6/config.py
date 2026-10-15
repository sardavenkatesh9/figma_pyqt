"""Central defaults and tunables shared by the CLI, the GUI and the generator."""

from __future__ import annotations

from pathlib import Path

DEFAULT_PROJECT_NAME = "GeneratedApp"
DEFAULT_OUTPUT_DIRNAME = "generated_project"

# Figma REST requests abort after this long instead of leaving the UI stuck.
FIGMA_REQUEST_TIMEOUT_MS = 30_000

# Workbench window
WINDOW_DEFAULT_SIZE = (1280, 800)
WINDOW_MIN_SIZE = (640, 600)
CONTENT_MAX_WIDTH = 1040


def default_output_dir() -> Path:
    """Default generation target: ``./generated_project`` under the working directory."""
    return Path.cwd() / DEFAULT_OUTPUT_DIRNAME
