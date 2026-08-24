"""Win Automator package metadata."""
from pathlib import Path
import sys


def _read_version() -> str:
    candidates = [
        Path(__file__).resolve().parents[2] / "VERSION",
        Path(sys.executable).resolve().parent / "VERSION",
    ]
    for path in candidates:
        try:
            value = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            continue
        if value:
            return value
    return "0.0.0+unknown"


__version__ = _read_version()
