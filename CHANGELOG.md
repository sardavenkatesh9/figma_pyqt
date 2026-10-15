# Changelog

## Unreleased

- Structure: `__init__.py` for every package, `.pre-commit-config.yaml` (ruff, black, mypy), broader `.gitignore`.
- Docs rewritten to match the code (removed claims about staged output, path-traversal blocking and process isolation that the code does not implement); README gained usage, testing and structure sections.
- Tests reorganised into `tests/unit` and `tests/integration` with shared `conftest.py`/`helpers.py`; 84 tests, 99% branch-aware coverage; CI enforces `--cov-fail-under=85`.
- Fix (B2): whole-file Figma fetches used `depth=2`, which per the Figma docs returns frames without children (blank pages). Now `depth=4` for files and `depth=3` for node links.
- Fix (B4): Figma requests time out after 30 s with a clear message instead of leaving "Verifying…" stuck.
- Fix (B5): child offsets are no longer clamped to 0 and sizes are rounded, not truncated.
- Fix (B6): parser warnings (unsupported node types) are returned in `ConversionResult.warnings` and shown in the GUI.
- Fix (B7): icons moved into the package (`src/figma_to_pyside6/assets`) and declared as package data, so installed wheels and PyInstaller builds find them.
- Fix (B11/B12): GUI catches `OSError` only when generating; empty project name / output folder fall back to defaults (an empty output folder used to write into the working directory).
- Refactor: code generation split into pure `application/codegen.py`; `conversion_service` only does I/O; one shared validator (`validation_service`, now GEN-001..004 incl. page and syntax checks) used by the CLI and the generator; Figma request/response logic moved to `adapters/figma_api.py`; GUI widgets created up front (no `None` guards) and layout split per step; new `config.py`.
- Fix (B1): regeneration no longer overwrites hand-edited README, pyproject, QSS or marker-less files; skipped files are reported in `ConversionResult.warnings`.
- `validate <dir>` now also fails on missing manifest pages or unparseable Python files.
- Removed dead code: `application/services.py`, `cli/commands.py`, `AppSettings`, `_load_document`.
- Single dark neon theme (shared `theme.py`); removed theme/style switchers. App always starts maximized.
- Generator emits one page module per Figma frame plus a navigable main window; stale pages are removed on regeneration.
- Fixed `@import` in generated QSS (unsupported by Qt) by concatenating style files at load time.
- Ruff (B/UP/SIM added), Black and strict-ish mypy are clean; fixed GUI test failure.
- PyInstaller spec, combined Figma/Python/Qt icons (ico/icns/png) and GitHub Actions CI/build/release.
- Established the project skeleton and package layout.
- Implemented local Figma JSON parsing and conversion to a generated PySide6 project.
- Added CLI entry points and a desktop workbench shell.
- Added real tests covering JSON parsing and conversion output.
