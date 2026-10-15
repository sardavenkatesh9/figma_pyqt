# Figma to PySide6 Workbench

Turns Figma frames into a runnable PySide6 desktop app: **one page module per frame**, reproducing the
design (fills, gradients, strokes, radii, shadows, opacity, real text; vectors, icons and images exported
from Figma) and a sidebar-navigated main window. The workbench itself uses a single dark neon theme. Use the desktop workbench (paste a
Figma link and a personal access token) or the CLI (local Figma JSON export). The conversion core is
headless and shared by both.

## Install

Requires Python 3.12+.

```bash
python -m pip install -e ".[dev]"
```

## Usage

### Workbench (GUI)

```bash
figma-to-pyside6          # or: python main.py gui
```

Paste a Figma design/file link and token, **Verify link**, tick the frames, set project name and output
folder, **Generate project**. Generation runs in the background: it loads the selected frames in full and
exports vector/image layers from Figma. The window always starts maximized. The token is cleared from the
field after Verify, kept in memory only for Generate, and never written to disk.

### Command line

```bash
figma-to-pyside6 inspect  tests/fixtures/figma_json/sample_figma.json
figma-to-pyside6 convert  tests/fixtures/figma_json/sample_figma.json --project-name DemoApp --output-dir generated_project
figma-to-pyside6 validate generated_project
figma-to-pyside6 report   generated_project
```

### Generated project

```
generated_project/
  main.py                      starts maximized
  src/ui/main_window.py        sidebar + QStackedWidget
  src/ui/pages/<frame>_page.py one BasePage subclass per Figma frame (scales to the window)
  src/ui/pages/widgets.py      box / text / image / shadow helpers used by the pages
  src/ui/assets/fig_<hash>.png  exported vector, icon and image layers (identical images stored once)
  src/ui/pages/__init__.py     PAGES registry
  src/ui/styles/*.qss          tokens, main, components (yours: never overwritten)
  generation_manifest.json, validation_report.json
```

Regenerating rewrites only files carrying the generator marker; README, `pyproject.toml` and QSS files are
created once, and hand-edited generated files are kept with a warning. See `docs/architecture.md`.

## Testing and quality

```bash
ruff check . && black --check . && mypy && pytest --cov --cov-fail-under=85
```

Tests live in `tests/unit` and `tests/integration` (offscreen Qt, fake network). Optional:
`pre-commit install` runs ruff, black and mypy before each commit.

## Build desktop binaries

```bash
pip install -e ".[build]"
pyinstaller figma_to_pyside6.spec --noconfirm
```

Produces `dist/FigmaToPySide6.exe` (Windows), `dist/FigmaToPySide6` (Linux) or `dist/FigmaToPySide6.app`
(macOS) with the combined Figma/Python/Qt icon from `src/figma_to_pyside6/assets/` (regenerate with
`python scripts/make_icons.py`). PyInstaller does not cross-compile; GitHub Actions
(`.github/workflows/ci.yml`) builds all three and attaches them to `v*` tag releases.

## Project structure

```
src/figma_to_pyside6/
  domain/        models (no dependencies)
  adapters/      Figma JSON parser, Figma link and REST helpers
  application/   codegen (pure), conversion_service (I/O), validation_service
  ui/            PySide6 workbench
  theme.py       the one dark neon theme        config.py   defaults
  resources.py   bundled icons                  __main__.py CLI / GUI entry point
tests/{unit,integration}/   conftest.py, helpers.py, fixtures/
docs/            architecture, mapping, GUI workflow, security, troubleshooting
scripts/         make_icons.py
examples/generated_sample/   output of the converter for the test fixture
```

More: `docs/user_guide.md`, `docs/development.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`.
