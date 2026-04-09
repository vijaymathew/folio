from __future__ import annotations

import sys
from pathlib import Path

from .ui.app import FolioApp


def run() -> None:
    path_arg = sys.argv[1] if len(sys.argv) > 1 else "docs/example.folio"
    document_path = Path(path_arg).expanduser().resolve()
    app = FolioApp(document_path)
    app.run()


if __name__ == "__main__":
    run()
