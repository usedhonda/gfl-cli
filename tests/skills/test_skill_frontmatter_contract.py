from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_FILES = [
    ROOT / "skills/gfl-search-operator/SKILL.md",
    ROOT / "skills/gfl-calendar-analyst/SKILL.md",
    ROOT / "skills/gfl-parity-triage/SKILL.md",
]
REQUIRED_KEYS = {
    "name",
    "description",
    "argument-hint",
    "allowed-tools",
    "compression-anchors",
}


def _frontmatter_keys(text: str) -> set[str]:
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---", "frontmatter must start with ---"

    end_index = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_index = idx
            break
    assert end_index is not None, "frontmatter closing --- is required"

    keys: set[str] = set()
    for line in lines[1:end_index]:
        match = re.match(r"^([A-Za-z0-9_-]+):", line)
        if match:
            keys.add(match.group(1))
    return keys


def test_skill_frontmatter_keys_present() -> None:
    for path in SKILL_FILES:
        text = path.read_text(encoding="utf-8")
        keys = _frontmatter_keys(text)
        missing = REQUIRED_KEYS - keys
        assert not missing, f"{path} missing frontmatter keys: {sorted(missing)}"
