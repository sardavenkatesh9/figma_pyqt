# Architecture

## Layers

```
src/figma_to_pyside6/
  domain/        FigmaNode, FigmaFrame, FigmaDocument, ConversionResult   (no dependencies)
  adapters/      figma_json.py  parse Figma JSON into domain models
                 figma_api.py   validate Figma links, build REST requests, parse responses
  application/   codegen.py             pure source generation (returns strings)
                 conversion_service.py  writes the project; decides what may be overwritten
                 validation_service.py  checks a generated project (used by CLI and generator)
  ui/            main_window.py  PySide6 workbench (network + widgets only)
  theme.py       the single dark neon theme, shared by the workbench and generated apps
  config.py      defaults and tunables
  resources.py   bundled assets (icons ship inside the package)
  __main__.py    CLI; with no arguments it launches the GUI
```

Dependencies point inwards: `ui` and `__main__` use `application` and `adapters`, which use
`domain`. Nothing below `ui` imports Qt widgets, so conversion is fully headless and testable
(`adapters/figma_api.py` builds URLs and parses responses; the window only does the I/O).

## Data flow

Figma link or JSON -> `adapters` -> `FigmaDocument` -> `codegen.plan_pages` (unique module and
class per frame) -> `codegen.render_*` -> `conversion_service` writes files -> manifest and
`validation_report.json`.

## Generated project

One page module per frame under `src/ui/pages/`, a `BasePage`, a page registry, a sidebar
`MainWindow`, three QSS files, and `main.py` (starts maximized). See `docs/conversion_mapping.md`.

## File ownership on regeneration

* Files starting with the generator marker are rewritten every run.
* README, `pyproject.toml`, QSS files and `__init__.py` files are created once and never overwritten.
* A "generated" file whose marker was removed is treated as hand-written and kept; a warning is
  returned in `ConversionResult.warnings`.
* Pages of frames that are no longer selected are deleted, but only if they carry the marker.

## Known limits

* Only frames, their children and grandchildren are fetched from the REST API (`depth` is capped
  to keep responses small); deeper nesting is not rendered.
* Layout (auto-layout, constraints), images, gradients and effects are not converted; unsupported
  node types are rendered as plain frames and reported as warnings.
