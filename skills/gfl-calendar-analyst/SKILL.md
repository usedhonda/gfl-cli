---
name: gfl-calendar-analyst
description: |
  Run gfl calendar with date-grid or price-graph view and summarize fare trends.
  Focus on machine-friendly interpretation of graph aggregate fields.
argument-hint: "<calendar analysis request>"
allowed-tools: [Bash, Read]
compression-anchors:
  - "run gfl calendar in price-graph mode"
  - "interpret results and graph aggregates"
  - "respond in user language while preserving technical tokens"
---

# gfl-calendar-analyst

Use this skill for date-range fare trend analysis using `gfl calendar` JSON output.

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

- `--origin --destination`
- `--start-date --end-date`
- optional `--trip-duration --is-round-trip`
- `--view date-grid|price-graph`
- locale and currency

## Execution Command (price-graph)

```bash
uv run gfl calendar \
  --origin SFO \
  --destination LAX \
  --start-date 2026-03-23 \
  --end-date 2026-03-25 \
  --view price-graph \
  --lang en-US \
  --currency USD \
  --format json
```

## Analysis Rules

If `status=success`:

1. Read `results[*].lowest_price.amount` for raw daily values.
2. For `price-graph`, use `results[*].graph`:
   - `point_index`
   - `y_amount`
   - `y_is_missing`
   - `min_amount_in_range`
   - `max_amount_in_range`
   - `avg_amount_in_range`
3. Report:
   - cheapest day(s)
   - spread (`max-min`)
   - missing points count
   - warning list

If `status=failed`, report canonical error fields and recommended next action.

## Failure Routing

- `INVALID_INPUT`: date range or option mismatch
- `UPSTREAM_UNAVAILABLE`: retry later
- `TIMEOUT`: retry with larger timeout
- other codes: route to triage skill
