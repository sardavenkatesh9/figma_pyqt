"""Development launcher: runs the CLI/GUI from a source checkout without installing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from figma_to_pyside6.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
