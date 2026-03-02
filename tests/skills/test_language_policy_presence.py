from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_FILES = [
    ROOT / "skills/gfl-search-operator/SKILL.md",
    ROOT / "skills/gfl-calendar-analyst/SKILL.md",
    ROOT / "skills/gfl-parity-triage/SKILL.md",
]


def test_each_skill_contains_output_language_policy() -> None:
    for path in SKILL_FILES:
        text = path.read_text(encoding="utf-8")
        assert "## Output Language Policy" in text
        assert "Language resolution order:" in text
        assert "1. Explicit language request in the current user message" in text
        assert "2. Dominant language in the current user message" in text
        assert "3. Last confirmed user language in the current session" in text
        assert "4. Fallback: English" in text
