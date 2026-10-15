"""Command line interface and GUI entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from figma_to_pyside6 import config
from figma_to_pyside6.adapters.figma_json import load_figma_document
from figma_to_pyside6.application.conversion_service import convert_document
from figma_to_pyside6.application.validation_service import validate_generated_project
from figma_to_pyside6.ui.main_window import main as launch_gui


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all sub-commands."""
    parser = argparse.ArgumentParser(
        prog="figma-to-pyside6", description="Figma to PySide6 converter"
    )
    subparsers = parser.add_subparsers(dest="command")

    inspect_parser = subparsers.add_parser("inspect", help="Inspect a local Figma JSON document")
    inspect_parser.add_argument("path", type=Path, help="Path to a Figma JSON export")

    convert_parser = subparsers.add_parser(
        "convert", help="Convert a local Figma JSON document into a generated PySide6 app"
    )
    convert_parser.add_argument("path", type=Path, help="Path to a Figma JSON export")
    convert_parser.add_argument("--project-name", default=config.DEFAULT_PROJECT_NAME)
    convert_parser.add_argument("--output-dir", type=Path, default=None)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate the generated output or local document"
    )
    validate_parser.add_argument("path", type=Path)

    report_parser = subparsers.add_parser(
        "report", help="Summarize a generated project or document"
    )
    report_parser.add_argument("path", type=Path)

    gui_parser = subparsers.add_parser("gui", help="Launch the desktop workbench")
    gui_parser.set_defaults(command="gui")

    return parser


def _handle_inspect(path: Path) -> int:
    document = load_figma_document(path)
    payload = {
        "name": document.name,
        "frame_count": len(document.frames),
        "frames": [frame.summary() for frame in document.frames],
    }
    print(json.dumps(payload, indent=2))
    return 0


def _handle_convert(path: Path, project_name: str, output_dir: Path | None) -> int:
    document = load_figma_document(path)
    result = convert_document(document, project_name=project_name, output_dir=output_dir)
    print(
        json.dumps(
            {
                "project_name": result.project_name,
                "output_dir": str(result.output_dir),
                "generated_files": [str(item) for item in result.generated_files],
            },
            indent=2,
        )
    )
    return 0


def _handle_validate(path: Path) -> int:
    if path.is_dir():
        report = validate_generated_project(path)
        failed = [c for c in report["checks"] if c["status"] == "FAIL"]
        if failed:
            for check in failed:
                print(
                    f"Validation failed: {check['id']} {check['description']} (missing or invalid)"
                )
            return 2
        print(f"Validated project directory: {path}")
        return 0

    document = load_figma_document(path)
    print(f"Validated document: {document.name} (frames={len(document.frames)})")
    return 0


def _handle_report(path: Path) -> int:
    if path.is_file():
        document = load_figma_document(path)
        print(f"Document: {document.name} | frames: {len(document.frames)}")
        return 0
    manifest_path = path / "generation_manifest.json"
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        print(json.dumps(payload, indent=2))
        return 0
    print(f"No manifest found in {path}")
    return 1


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Arguments to parse; defaults to ``sys.argv[1:]``.

    Returns:
        Process exit code. With no sub-command the GUI is launched.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        launch_gui()
        return 0

    if args.command == "inspect":
        return _handle_inspect(args.path)
    if args.command == "convert":
        return _handle_convert(args.path, args.project_name, args.output_dir)
    if args.command == "validate":
        return _handle_validate(args.path)
    if args.command == "report":
        return _handle_report(args.path)
    if args.command == "gui":
        launch_gui()
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
