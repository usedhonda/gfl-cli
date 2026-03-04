# Playwright DOM Investigation Runbook

This runbook is the standard procedure when Google Flights UI changes or parser drift is suspected.

## 1. Prerequisites

```bash
uv sync --extra dev --extra design
uv run python -m playwright install chromium
```

## 2. Baseline probe (single route)

```bash
uv run --extra design python scripts/probe_browser_cli_gap.py \
  --origin HND \
  --destination SIN \
  --date 2026-04-05 \
  --lang ja-JP \
  --currency JPY \
  --dom-snapshot \
  --screenshot \
  --output artifacts/parity/latest-single.json
```

Evidence generated:
- `artifacts/parity/latest-single.json` (browser/CLI comparison)
- `artifacts/parity/screenshots/*.png` (if `--screenshot`)
- `artifacts/parity/dom/*.html` (if `--dom-snapshot`)

## 3. Matrix probe (regression sweep)

```bash
uv run --extra design python scripts/probe_browser_cli_gap.py \
  --matrix-file docs/parity/matrix.json \
  --dom-snapshot \
  --screenshot \
  --output artifacts/parity/latest-matrix.json
```

Then enforce thresholds:

```bash
uv run python scripts/parity_gate.py \
  --input artifacts/parity/latest-matrix.json \
  --thresholds docs/parity/thresholds.json
```

## 4. Drift triage checklist

1. Confirm browser still renders result cards under `ul.Rk10dc li`.
2. Confirm each card still has a `div[role="link"][aria-label]`.
3. Confirm expected fields exist in card text:
   - airline
   - departure/arrival time
   - duration
   - stops
   - price
4. Confirm optional metadata presence:
   - emissions text (`kg CO2e`, `% emissions`)
   - travel impact URL (`data-travelimpactmodelwebsiteurl`)
   - layover snippets (`hr/min + IATA`)
5. Classify failure:
   - `UPSTREAM_FORMAT_CHANGED` if structure drift
   - `UPSTREAM_UNAVAILABLE` if no flights available for the query

## 5. Parser update order

1. Update extraction in `fast-flights` first (`fast_flights/core.py`).
2. Map new fields in `gfl/adapters/fast_flights/mapper.py`.
3. Add/update contract tests in `tests/contracts/`.
4. Re-run matrix probe and parity gate.
5. Commit with captured evidence paths in message/log.

## 6. Non-negotiable rules

- Never ship parser changes without Playwright evidence.
- Never import Playwright in runtime package modules under `gfl/`.
- Keep stable top-level JSON contract (`status/request_id/query/results/meta/error`).
