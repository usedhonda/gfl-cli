# gfl

`gfl` is a JSON-first Google Flights CLI for automation workflows, powered by `fast-flights`.

## Install

```bash
uv sync
```

## Commands

- `gfl search`
- `gfl calendar`
- `gfl version`

## Quick Usage

```bash
uv run gfl search \
  --origin SFO \
  --destination LAX \
  --date 2026-03-23 \
  --currency USD
```

```bash
uv run gfl search \
  --trip multi-city \
  --segment SFO:NRT:2026-03-23 \
  --segment NRT:CTS:2026-03-26 \
  --currency USD
```

```bash
uv run gfl calendar \
  --origin SFO \
  --destination LAX \
  --start-date 2026-03-23 \
  --end-date 2026-03-25 \
  --view date-grid
```

```bash
uv run gfl version
```

## Output Contract

All commands default to JSON on stdout with fixed top-level fields:

- `status`
- `request_id`
- `query`
- `results`
- `meta`
- `error`

Use `--format human` or `--human` for opt-in human-readable output.

## Language/Currency Behavior

- runtime provider language is fixed to `en-US`
- `--currency` omitted: query uses empty string (`""`) and provider default currency
- any provided `--currency` is normalized to uppercase ISO4217 (example: `jpy` -> `JPY`)

## Search/Calendar Option Notes

- `search --sort best|cheapest` (default: `best`)
- `search` supports additional filters:
  - `--max-price`
  - `--depart-after/--depart-before` (`HH:MM`, 24h)
  - `--arrive-after/--arrive-before` (`HH:MM`, 24h)
  - `--max-duration-min`
- `search` flight rows include backend metadata when available:
  - `self_transfer`
  - `emissions` (`kg_co2e`, `delta_percent`, `relative_label`)
  - `layovers[]` (`airport_code`, `duration_text`, `duration_min`)
  - `flight_numbers[]`, `operated_by`, `aircraft`, `amenities[]`
- `search --trip multi-city` requires repeated `--segment FROM:TO:YYYY-MM-DD` (>=2)
  - current behavior is best-effort and may return `UPSTREAM_UNAVAILABLE` depending on upstream response shape
- `calendar --view date-grid|price-graph` (default: `date-grid`)
- `calendar --view price-graph` adds `results[*].graph` aggregate fields for AI-friendly parsing

## Error Codes

Allowed stable error codes:

- `INVALID_INPUT`
- `UPSTREAM_FORMAT_CHANGED`
- `UPSTREAM_UNAVAILABLE`
- `RATE_LIMITED`
- `TIMEOUT`
- `INTERNAL_ERROR`

## Skill Samples

This repository includes reusable skill samples under `skills/`.

- `skills/gfl-search-operator`: search execution and result summarization
- `skills/gfl-calendar-analyst`: price-graph analysis for calendar output
- `skills/gfl-parity-triage`: failure classification and parity triage flow

Skill docs are written in English. Runtime prose should follow the user's language.
Technical tokens stay canonical and must not be translated (flags, JSON keys, error codes).

Language resolution order used by the samples:

1. explicit language request in the current user message
2. dominant language in the current user message
3. last confirmed user language in the current session
4. fallback to English

## Development Rule

See [docs/development-rules.md](docs/development-rules.md).
For the full DOM drift workflow, see [docs/playwright-dom-investigation.md](docs/playwright-dom-investigation.md).

Summary:

- Playwright is mandatory for development-time parser/design validation.
- Playwright is prohibited in production runtime path (`gfl/`).
- `gfl` runtime verification should use stable JSON command outputs.

```bash
uv sync --extra dev
uv run gfl search --origin SFO --destination LAX --date 2026-03-23 --currency USD --format json

uv run python scripts/parity_gate.py \
  --input artifacts/parity/latest-matrix.json \
  --thresholds docs/parity/thresholds.json
```
