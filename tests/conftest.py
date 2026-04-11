from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DOCS = ROOT / "docs"
EXAMPLE_DOC = DOCS / "example.folio"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
