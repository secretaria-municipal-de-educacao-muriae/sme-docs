#!/usr/bin/env python
"""Ponto de entrada do SMEDocs.

    python smedocs.py                  modo interativo
    python smedocs.py listar
    python smedocs.py gerar 10 -f pdf -f docx
    python smedocs.py conferir 10
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from smedocs.cli import run  # noqa: E402

if __name__ == "__main__":
    run()
