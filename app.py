import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from win_automator import __version__
from win_automator.ui import run


def _argument_value(name: str):
    try:
        index = sys.argv.index(name)
        return sys.argv[index + 1]
    except (ValueError, IndexError):
        return None


def main():
    smoke_target = _argument_value("--smoke-test")
    if smoke_target:
        Path(smoke_target).write_text(__version__, encoding="utf-8")
        return 0
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
