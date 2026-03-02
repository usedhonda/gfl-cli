# gfl Skill Samples

This directory contains reusable skill samples for operating the `gfl` CLI in automation workflows.

## Included Skills

- `gfl-search-operator`: run and summarize `gfl search` (one-way, round-trip, multi-city)
- `gfl-calendar-analyst`: run `gfl calendar --view price-graph` and analyze fare trends
- `gfl-parity-triage`: classify failures and run parity triage commands

## Output Language Policy

All skill docs are written in English.
When a skill is used, response prose must follow the user's language.

Language resolution order:

1. Explicit language request in the current user message
2. Dominant language in the current user message
3. Last confirmed user language in the current session
4. Fallback: English

Do not translate technical tokens such as CLI flags, command names, JSON keys, and error codes.

## Shared Assets

- `_shared/templates/`: intake and response templates
- `_shared/scripts/`: helper scripts for JSON execution and failure triage

## Notes

- `multi-city` is best-effort with current upstream/backend behavior.
- Parser-facing changes must still follow the project parity validation rules in `docs/development-rules.md`.
