"""Pytest bootstrap: ensure `app` package is importable without `pip install -e .`.

Adds the backend/ directory (which contains the `app/` package) to sys.path.
Safe no-op when the package is already installed.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
