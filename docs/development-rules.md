# Development Rules

## Rule 0: Mandatory GUI investigation before implementation

Before changing parser logic, selector assumptions, or provider mapping, you MUST perform a GUI-first investigation with Playwright and collect evidence.

Required pre-implementation evidence:

1. Target query opened in browser context.
2. Actual DOM/accessible structure snapshot captured.
3. Key selectors and fields mapped to expected CLI output fields.
4. Notes on unstable/async-rendered elements.

No parser-facing code change should start before this GUI investigation is completed.

## Rule 1: Playwright is mandatory for parser/design validation

When changing provider parsing logic, selector assumptions, or result mapping, development validation MUST include Playwright-based browser inspection.

Minimum validation:

1. Open the same flight query in browser context (Playwright).
2. Compare browser-observed structure against CLI fetch output.
3. Record mismatch evidence before and after the change.

Use:

```bash
uv sync --extra dev --extra design
uv run python scripts/probe_browser_cli_gap.py --origin SFO --destination LAX --date 2026-03-23
```

Matrix probe and parity gate:

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

## Rule 2: Playwright is prohibited in production runtime path

The runtime CLI package (`gfl/`) must not depend on or import Playwright.
Playwright usage is restricted to development tooling (for example `scripts/`) and explicit design-validation workflows.

## Rule 3: Contract first

Even when parser internals change, the JSON output contract and stable error codes must remain unchanged unless explicitly approved.
