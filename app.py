import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from win_automator import __version__


def _argument_value(name: str):
    try:
        index = sys.argv.index(name)
        return sys.argv[index + 1]
    except (ValueError, IndexError):
        return None


def main():
    smoke_target = _argument_value("--smoke-test")
    smoke_gui_target = _argument_value("--smoke-gui")
    if smoke_target or smoke_gui_target:
        from win_automator.smoke import run_smoke_test, write_report

        report = run_smoke_test(gui=bool(smoke_gui_target))
        report["version"] = __version__
        target = Path(smoke_gui_target or smoke_target)
        write_report(target, report)
        return 0 if report.get("ok") else 2

    from win_automator.ui import run

    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
