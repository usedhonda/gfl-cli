from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "skills/_shared/scripts"
FORBIDDEN_UNICODE_OPERATORS = ["≠", "≤", "≥", "→", "←"]


def _script_files() -> list[Path]:
    return sorted(SCRIPT_DIR.glob("*.sh"))


def test_skill_scripts_exist() -> None:
    scripts = _script_files()
    assert scripts, "no skill helper scripts found"


def test_skill_scripts_use_bash_shebang_and_ascii_only() -> None:
    for path in _script_files():
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()

        assert lines, f"{path} is empty"
        assert lines[0] == "#!/usr/bin/env bash", f"{path} must use bash shebang"
        assert text.isascii(), f"{path} should be ASCII-only"

        for op in FORBIDDEN_UNICODE_OPERATORS:
            assert op not in text, f"{path} contains forbidden unicode operator: {op}"


def test_skill_scripts_pass_bash_noexec_syntax_check() -> None:
    for path in _script_files():
        completed = subprocess.run(
            ["bash", "-n", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, (
            f"{path} failed bash -n\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
