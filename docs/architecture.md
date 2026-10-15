# Architecture

## Layers

```
src/figma_to_pyside6/
  domain/        FigmaNode, FigmaFrame, FigmaDocument, ConversionResult   (no dependencies)
  adapters/      figma_json.py  parse Figma JSON into domain models
                 figma_api.py   validate Figma links, build REST requests, parse responses
                 figma_client.py  blocking urllib client used by the background job
  application/   codegen.py             pure source generation (returns strings)
                 styling.py             Figma paints/strokes/radii -> Qt style sheet fragments
                 raster.py              which layers must be exported as images
                 figma_pipeline.py      fetch frame detail + exported images, then generate
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

Figma link -> verify (shallow frame list) -> select -> `figma_pipeline`: full frame detail + exported
PNGs -> `FigmaDocument`; or local JSON -> `adapters` -> `FigmaDocument`. Then `codegen.plan_pages` (unique module and
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

* Verification only lists frames (shallow request); Generate fetches the selected frames in full.
* Positions are absolute at design size: auto-layout and constraints are not reproduced, and the page
  is scaled uniformly to the window.
* Inner shadows, blur effects, blend modes and dashed strokes are not converted. Unsupported node
  types are reported as warnings.
