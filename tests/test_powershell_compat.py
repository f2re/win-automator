import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell compatibility test")


def test_all_powershell_scripts_parse_with_windows_powershell():
    scripts = sorted(ROOT.rglob("*.ps1"))
    assert scripts
    command = (
        "$errors = $null; $tokens = $null; "
        "[void][System.Management.Automation.Language.Parser]::ParseFile("
        "$env:WA_SCRIPT, [ref]$tokens, [ref]$errors); "
        "if ($errors.Count -gt 0) { "
        "$errors | ForEach-Object { [Console]::Error.WriteLine($_.ToString()) }; exit 1 }"
    )
    failures = []
    for script in scripts:
        env = os.environ.copy()
        env["WA_SCRIPT"] = str(script)
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            env=env,
            timeout=20,
        )
        if result.returncode != 0:
            failures.append(
                "{}\n{}".format(
                    script.relative_to(ROOT),
                    result.stderr.decode("utf-8", errors="replace"),
                )
            )
    assert not failures, "Windows PowerShell parser failures:\n\n" + "\n\n".join(failures)
