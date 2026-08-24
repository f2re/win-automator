import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell compatibility test")


def _powershell_scripts():
    return sorted(ROOT.rglob("*.ps1"))


def test_non_ascii_powershell_scripts_are_utf8_bom_encoded():
    failures = []
    for script in _powershell_scripts():
        payload = script.read_bytes()
        text = payload.decode("utf-8-sig")
        if any(ord(char) > 127 for char in text) and not payload.startswith(b"\xef\xbb\xbf"):
            failures.append(str(script.relative_to(ROOT)))
    assert not failures, (
        "Windows PowerShell 5.1 needs UTF-8 BOM for non-ASCII scripts: "
        + ", ".join(failures)
    )


def test_all_powershell_scripts_parse_with_windows_powershell():
    scripts = _powershell_scripts()
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
