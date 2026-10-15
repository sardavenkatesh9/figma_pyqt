# Figma to PySide6 Workbench

This project provides a small but working Figma-to-PySide6 conversion pipeline and a desktop workbench shell. The core conversion logic is headless and reusable from both CLI and GUI entry points.

## Install

```bash
python -m pip install -e ".[dev]"
```

## Run the GUI

```bash
python main.py gui
# or
figma-to-pyside6 gui
```

## Convert a local Figma JSON export

```bash
figma-to-pyside6 convert tests/fixtures/figma_json/sample_figma.json --project-name DemoApp --output-dir generated_project
```

## Inspect a document

```bash
figma-to-pyside6 inspect tests/fixtures/figma_json/sample_figma.json
```

## Notes

- The GUI verifies Figma file links using a personal access token, then generates from the selected frames.
- Local JSON conversion remains available through the CLI.
- The token is used only for the verification request and is not persisted.
