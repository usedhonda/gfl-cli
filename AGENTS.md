# AGENTS.md - gfl (Google Flights CLI)

## Persona and Communication
- Read `.codex/config.toml` in this directory and follow the persona in `instructions`.
- Keep technical accuracy above style.

## Mission
Build a production-usable Google Flights CLI for automation workflows, using `fast-flights` as backend.

## Phase 1 Scope
- In scope:
  - Flight search CLI only
  - JSON-first output contract (machine-readable by default)
  - Market controls (`--currency`)
  - Input validation and stable error codes
  - Retry/timeout hardening
- Out of scope:
  - MCP server
  - Hotel search
  - Browser UI automation
  - Preference memory/recommender logic

## Hard Requirements (Do Not Violate)
1. Default output MUST be JSON to stdout.
2. Human output is opt-in via `--human` or `--format human`.
3. Error output MUST be structured and include stable `error.code`.
4. CLI command behavior MUST be deterministic and contract-tested.
5. Domain logic and CLI wiring MUST stay separated.

## Development Validation Rules (Playwright Boundary)
1. GUI-first investigation is mandatory before parser/provider-mapping changes:
   - Inspect actual Google Flights page structure with Playwright.
   - Capture evidence of selectors/fields before implementation.
2. Playwright is mandatory for development-time parser/design validation.
3. Playwright is prohibited in production runtime path:
   - `gfl/` package must not import or depend on Playwright.
   - Playwright usage is limited to development tooling (for example `scripts/`).
4. This does NOT allow browser UI automation features in product scope; usage is validation-only.

## Technical Baseline
- Python 3.11+
- Backend dependency: `fast-flights`
- CLI framework: Typer (or argparse with explicit rationale)
- Tests: pytest
- Lint/format: ruff

## Required Commands
- `gfl search`
- `gfl calendar`
- `gfl version`

## Shared Flags
- `--currency <ISO4217>`
- `--timeout-sec <int>`
- `--retries <int>`
- `--format json|human` (default: `json`)

## Output Contract Summary
Top-level fields are fixed:
- `status`: `success|failed`
- `request_id`: string
- `query`: object
- `results`: array
- `meta`: object
- `error`: object or null

On failure:
- `status=failed`
- `results=[]`
- `error.code` must be from the approved code set in `SPEC.md`

## Architecture Rules
- Keep modules split by concern:
  - `gfl/cli/` command parsing and presentation only
  - `gfl/core/` validation, normalization, contracts
  - `gfl/adapters/fast_flights/` provider mapping
  - `gfl/contracts/` schema and error code registry
- Never place provider parsing logic directly in CLI command files.

## Definition of Done (per task)
- Implementation complete
- Contract tests added/updated
- CLI help updated when flags/commands change
- Short usage example included in docs

## Handoff Rule for Other Sessions
Before implementation, read in this order:
1. `AGENTS.md`
2. `SPEC.md`
3. repository tests and package config

Any change to output schema or error codes requires explicit approval.
