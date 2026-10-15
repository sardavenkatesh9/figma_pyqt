from __future__ import annotations

import argparse
from pathlib import Path

from figma_to_pyside6.adapters.figma_json import load_figma_document
from figma_to_pyside6.application.conversion_service import convert_document


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="figma-to-pyside6",
        description="Convert Figma JSON files into PySide6 interface projects",
    )
    parser.add_argument("input", type=Path, help="Path to a Figma JSON file")
    parser.add_argument("--project-name", default="GeneratedApp")
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def command_convert(args: argparse.Namespace) -> int:
    document = load_figma_document(args.input)
    result = convert_document(document, project_name=args.project_name, output_dir=args.output_dir)
    print(f"Generated project at {result.output_dir}")
    return 0
