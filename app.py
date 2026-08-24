import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> int:
    if "--smoke-test" in sys.argv or "--smoke-gui" in sys.argv:
        from win_automator.smoke import run_smoke_test

        return run_smoke_test(gui="--smoke-gui" in sys.argv)

    from win_automator.ui import run

    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
