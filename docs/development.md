# Development

## Setup

```bash
python -m pip install -e ".[dev]"
pre-commit install            # optional: ruff, black and mypy before each commit
```

## Checks (same as CI)

```bash
ruff check .
black --check .
mypy
pytest --cov --cov-fail-under=85
```

## Tests

* `tests/unit/` - pure functions: link parsing, JSON parser, slug allocation, validation.
* `tests/integration/` - generation to disk, CLI in-process, GUI flows (offscreen Qt, fake network),
  and a subprocess that imports a generated app.
* `tests/helpers.py` and `tests/conftest.py` hold fakes and fixtures. GUI tests never touch the
  network: `FakeNetworkManager` and `FakeNetworkReply` stand in for Qt's.

## Packaging

```bash
python -m pip install -e ".[build]"
pyinstaller figma_to_pyside6.spec --noconfirm
```

`python scripts/make_icons.py` regenerates the icons in `src/figma_to_pyside6/assets/`. PyInstaller
does not cross-compile; CI builds Windows, Linux and macOS binaries.
