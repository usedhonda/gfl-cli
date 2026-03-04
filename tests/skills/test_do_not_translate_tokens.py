from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "skills/_shared/templates/response-style.md"
SKILL_FILES = [
    ROOT / "skills/gfl-search-operator/SKILL.md",
    ROOT / "skills/gfl-calendar-analyst/SKILL.md",
    ROOT / "skills/gfl-parity-triage/SKILL.md",
]
REQUIRED_TOKENS = [
    "gfl",
    "gfl search",
    "gfl calendar",
    "gfl version",
    "--origin --destination --date --return-date --segment --currency --view",
    "status",
    "request_id",
    "query",
    "results",
    "meta",
    "error",
    "INVALID_INPUT",
    "UPSTREAM_FORMAT_CHANGED",
    "UPSTREAM_UNAVAILABLE",
    "RATE_LIMITED",
    "TIMEOUT",
    "INTERNAL_ERROR",
]


def test_response_template_includes_required_do_not_translate_tokens() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "## Do Not Translate Tokens" in text

    missing = [token for token in REQUIRED_TOKENS if f"`{token}`" not in text]
    assert not missing, f"missing do-not-translate tokens: {missing}"


def test_each_skill_mentions_technical_tokens_must_stay_canonical() -> None:
    required = "Keep technical tokens unchanged"
    for path in SKILL_FILES:
        text = path.read_text(encoding="utf-8")
        assert required in text, f"{path} missing token preservation rule"
