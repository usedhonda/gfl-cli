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
  --lang en-US \
  --currency USD
```

```bash
uv run gfl search \
  --trip multi-city \
  --segment SFO:NRT:2026-03-23 \
  --segment NRT:CTS:2026-03-26 \
  --lang en-US \
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

## Locale/Currency Behavior

- `--lang` omitted: query uses `en`
- `--currency` omitted: query uses empty string (`""`) and provider default currency
- any provided `--currency` is normalized to uppercase ISO4217 (example: `jpy` -> `JPY`)

## Search/Calendar Option Notes

- `search --sort best|cheapest` (default: `best`)
- `search` supports additional filters:
  - `--max-price`
  - `--depart-after/--depart-before` (`HH:MM`, 24h)
  - `--arrive-after/--arrive-before` (`HH:MM`, 24h)
  - `--max-duration-min`
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

## Development Rule

See [docs/development-rules.md](docs/development-rules.md).

Summary:

- Playwright is mandatory for development-time parser/design validation.
- Playwright is prohibited in production runtime path (`gfl/`).
- Use development extras only when running design-validation tooling.

```bash
uv sync --extra dev --extra design
uv run python scripts/probe_browser_cli_gap.py --origin SFO --destination LAX --date 2026-03-23
```

Matrix + gate example:

```bash
uv run --extra design python scripts/probe_browser_cli_gap.py \
  --matrix-file docs/parity/matrix.json \
  --limit 3 \
  --screenshot \
  --dom-snapshot \
  --output artifacts/parity/latest-matrix.json

uv run python scripts/parity_gate.py \
  --input artifacts/parity/latest-matrix.json \
  --thresholds docs/parity/thresholds.json
```
