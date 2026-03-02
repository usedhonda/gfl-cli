---
name: gfl-search-operator
description: |
  Operate gfl search for one-way, round-trip, and multi-city requests.
  Produce concise automation-friendly summaries from JSON output.
argument-hint: "<flight search request>"
allowed-tools: [Bash, Read]
compression-anchors:
  - "run gfl search with stable JSON output"
  - "support one-way round-trip multi-city input patterns"
  - "follow user-language response policy"
---

# gfl-search-operator

Use this skill when the task is to run `gfl search` and summarize results safely for automation.

## Output Language Policy

- Keep this skill document in English.
- Render response prose in the user's language.
- Keep technical tokens unchanged: CLI flags, command names, JSON keys, and error codes.

Language resolution order:

1. Explicit language request in the current user message
2. Dominant language in the current user message
3. Last confirmed user language in the current session
4. Fallback: English

## Intake Checklist

Collect and confirm:

- trip mode: `one-way` | `round-trip` | `multi-city`
- locale: `--lang`
- currency: `--currency`
- seat, passenger counts, and filters if requested

Trip-specific required inputs:

- one-way: `--origin --destination --date`
- round-trip: one-way inputs + `--trip round-trip --return-date`
- multi-city: `--trip multi-city` + repeated `--segment FROM:TO:YYYY-MM-DD` (2+)

## Execution Commands

### One-way

```bash
uv run gfl search \
  --origin SFO \
  --destination LAX \
  --date 2026-03-23 \
  --lang en-US \
  --currency USD \
  --format json
```

### Round-trip

```bash
uv run gfl search \
  --origin JFK \
  --destination LHR \
  --date 2026-03-27 \
  --trip round-trip \
  --return-date 2026-04-02 \
  --lang en-US \
  --currency USD \
  --format json
```

### Multi-city (best-effort)

```bash
uv run gfl search \
  --trip multi-city \
  --segment SFO:NRT:2026-03-23 \
  --segment NRT:CTS:2026-03-26 \
  --lang en-US \
  --currency USD \
  --format json
```

## Validation and Summary Rules

After execution:

1. Parse JSON and check `status`.
2. If `status=success`, summarize:
   - route context and trip mode
   - result count and top fare signals
   - warnings in `meta.warnings`
3. If `status=failed`, report:
   - `error.code`
   - `error.message`
   - retriable hint from `error.retriable`

## Failure Routing

- `INVALID_INPUT`: fix parameters and re-run
- `UPSTREAM_UNAVAILABLE`: retry later or adjust query scope
- `UPSTREAM_FORMAT_CHANGED`: run parity triage workflow
- `TIMEOUT`: increase timeout or retry
- `RATE_LIMITED`: wait and retry
- `INTERNAL_ERROR`: capture raw payload and escalate
