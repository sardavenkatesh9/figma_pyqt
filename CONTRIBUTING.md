# Contributing

1. Create a virtual environment and `pip install -e ".[dev]"`; optionally `pre-commit install`.
2. Write or update a failing test first (`tests/unit` for pure logic, `tests/integration` for I/O, CLI, GUI).
3. Run `ruff check . && black --check . && mypy && pytest --cov --cov-fail-under=85`.
4. Keep conversion (`application/`, `adapters/`) free of Qt widgets; the GUI only does I/O and display.
5. Report unsupported design features as warnings instead of dropping them silently.
6. Add an entry to `CHANGELOG.md`.
