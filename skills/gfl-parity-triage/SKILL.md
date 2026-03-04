---
name: gfl-parity-triage
description: |
  Classify gfl failures and run parity triage commands.
  Standardize incident reporting for parser and upstream instability.
argument-hint: "<failure payload or triage request>"
allowed-tools: [Bash, Read]
compression-anchors:
  - "classify canonical gfl error codes"
  - "run probe and parity gate commands"
  - "produce incident report in user language"
---

# gfl-parity-triage

Use this skill to diagnose failures and collect parity evidence before parser-facing changes.

## Output Language Policy

- Keep this skill document in English.
- Render response prose in the user's language.
- Keep technical tokens unchanged: CLI flags, command names, JSON keys, and error codes.

Language resolution order:

1. Explicit language request in the current user message
2. Dominant language in the current user message
3. Last confirmed user language in the current session
4. Fallback: English

## Classification Matrix

Map `error.code` to first action:

- `INVALID_INPUT`: fix parameters and rerun
- `UPSTREAM_UNAVAILABLE`: retry policy and narrower query
- `UPSTREAM_FORMAT_CHANGED`: collect parser parity evidence
- `TIMEOUT`: timeout tuning and bounded retries
- `RATE_LIMITED`: cooldown and retry
- `INTERNAL_ERROR`: capture payload and escalate

## Triage Commands

```bash
uv run gfl search \
  --origin SFO \
  --destination LAX \
  --date 2026-03-23 \
  --currency USD \
  --format json

uv run python scripts/parity_gate.py \
  --input artifacts/parity/latest-matrix.json \
  --thresholds docs/parity/thresholds.json \
  --output artifacts/parity/latest-gate.json
```

## Incident Report Contract

Always include:

1. reproduction command
2. raw `status/error/meta.warnings`
3. observed vs expected behavior
4. proposed next action

Use `_shared/templates/incident-report.md` for consistent structure.

## Guardrails

- Do not change runtime contract during triage.
- Preserve canonical error codes.
- Treat multi-city as best-effort unless upstream stability improves.
