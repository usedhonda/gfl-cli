from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_skill_sample_files_exist() -> None:
    required = [
        "skills/README.md",
        "skills/gfl-search-operator/SKILL.md",
        "skills/gfl-calendar-analyst/SKILL.md",
        "skills/gfl-parity-triage/SKILL.md",
        "skills/_shared/templates/response-style.md",
        "skills/_shared/templates/search-intake.md",
        "skills/_shared/templates/calendar-intake.md",
        "skills/_shared/templates/incident-report.md",
        "skills/_shared/scripts/run-search-json.sh",
        "skills/_shared/scripts/run-calendar-graph.sh",
        "skills/_shared/scripts/triage-failure.sh",
    ]

    missing = [path for path in required if not (ROOT / path).exists()]
    assert not missing, f"missing skill sample files: {missing}"
