# SPEC.md - gfl v0.1 (Phase 1)

## 1. Summary
`gfl` is a JSON-first Google Flights CLI built on top of `fast-flights`.
Primary consumer is automation (OpenClaw wrappers, schedulers, bots). Human terminal usage is secondary.

## 2. Goals
- Stable machine-readable output for every command.
- Explicit locale controls (`lang`, `currency`).
- Predictable failure semantics with fixed error code taxonomy.
- Minimal command surface with high reliability.

## 3. Non-Goals
- MCP server support.
- Hotel recommendation/search.
- Browser automation workflow.
- Personalized recommendation engine.

## 4. Command Surface

### 4.1 `gfl search`
Search one-way or round-trip flights.

Required arguments:
- `--origin <IATA>`
- `--destination <IATA>`
- `--date <YYYY-MM-DD>`

Optional arguments:
- `--return-date <YYYY-MM-DD>`
- `--trip one-way|round-trip|multi-city`
- `--seat economy|premium-economy|business|first`
- `--max-stops <int>`
- `--airline <IATA>` (repeatable)
- `--segment <FROM:TO:YYYY-MM-DD>` (repeatable, for `trip=multi-city`)
- `--adults <int>` default `1`
- `--children <int>` default `0`
- `--infants-in-seat <int>` default `0`
- `--infants-on-lap <int>` default `0`
- `--lang <BCP47>` default provider default
- `--currency <ISO4217>` default provider default
- `--timeout-sec <int>` default `30`
- `--retries <int>` default `2`
- `--format json|human` default `json`

### 4.2 `gfl calendar`
Find cheapest trend across a date range.

Required arguments:
- `--origin <IATA>`
- `--destination <IATA>`
- `--start-date <YYYY-MM-DD>`
- `--end-date <YYYY-MM-DD>`

Optional arguments:
- `--trip-duration <int>`
- `--is-round-trip`
- `--seat ...`
- `--max-stops ...`
- `--airline ...`
- shared flags from `search`

### 4.3 `gfl version`
Returns CLI and backend version metadata.

## 5. JSON Contract (Fixed)

### 5.1 Success shape
```json
{
  "status": "success",
  "request_id": "uuid-or-hash",
  "query": {},
  "results": [],
  "meta": {
    "source": "fast-flights",
    "generated_at_utc": "2026-03-02T00:00:00Z",
    "latency_ms": 1234,
    "warnings": []
  },
  "error": null
}
```

### 5.2 Failure shape
```json
{
  "status": "failed",
  "request_id": "uuid-or-hash",
  "query": {},
  "results": [],
  "meta": {
    "source": "fast-flights",
    "generated_at_utc": "2026-03-02T00:00:00Z",
    "latency_ms": 456,
    "warnings": []
  },
  "error": {
    "code": "INVALID_INPUT",
    "message": "origin must be a valid IATA code",
    "retriable": false
  }
}
```

## 6. Error Code Registry (v0.1)
Allowed codes:
- `INVALID_INPUT`
- `UPSTREAM_FORMAT_CHANGED`
- `UPSTREAM_UNAVAILABLE`
- `RATE_LIMITED`
- `TIMEOUT`
- `INTERNAL_ERROR`

No undocumented code is allowed in output.

## 7. Validation Rules
- IATA: exactly 3 uppercase letters.
- Date: strict `YYYY-MM-DD`.
- Passenger constraints:
  - total passengers <= 9
  - `infants-on-lap <= adults`
- `trip=round-trip` requires `return-date`.
- `trip=multi-city` requires at least two `--segment` values.
- `trip=multi-city` disallows `--origin/--destination/--date/--return-date`.
- `end-date >= start-date` for calendar.

## 8. Runtime Behavior
- stdout: primary result object only.
- stderr: logs/diagnostics only.
- `--debug`: verbose diagnostics to stderr only.
- retry policy: bounded retries with exponential backoff.

## 9. Suggested Package Layout
- `gfl/cli/`
- `gfl/core/`
- `gfl/adapters/fast_flights/`
- `gfl/contracts/`
- `tests/`

## 10. Test Requirements
Minimum test matrix:
1. `search` one-way success
2. `search` round-trip success
3. invalid IATA -> `INVALID_INPUT`
4. invalid date -> `INVALID_INPUT`
5. invalid passenger combination -> `INVALID_INPUT`
6. mocked parser drift -> `UPSTREAM_FORMAT_CHANGED`
7. timeout path -> `TIMEOUT`
8. schema compliance for all commands
9. `--format human` smoke test
10. `version` contract test

## 11. Release Criteria for v0.1
- Contract tests pass.
- Manual smoke checks for:
  - `--lang ja-JP --currency JPY`
  - `--lang en-US --currency USD`
- README includes install, examples, output schema, and error table.

## 12. Change Control
Any change to command names, output schema, or error code registry requires explicit approval before implementation.

## 13. Phase 2 Additions (Implemented)
- `search trip=multi-city` is available in best-effort mode with repeatable `--segment FROM:TO:YYYY-MM-DD`.
- `query.segments` is included in JSON output.
- `results[0].flights[*].segments` is included for multi-city (request-echo model).
- `meta.warnings` includes `multi_city.segments=request_echo` for multi-city responses.
- upstream may return `UPSTREAM_UNAVAILABLE` when multi-city payload cannot be parsed.
- `calendar --view price-graph` includes `results[*].graph` with:
  - `point_index`
  - `y_amount`
  - `y_is_missing`
  - `min_amount_in_range`
  - `max_amount_in_range`
  - `avg_amount_in_range`

## 14. Extended Flight Metadata (Implemented)
`results[0].flights[*]` may include the following backend-derived fields:
- `self_transfer` (bool)
- `emissions` object:
  - `kg_co2e`
  - `delta_percent`
  - `relative_label`
- `layovers[]` objects:
  - `airport_code`
  - `duration_text`
  - `duration_min`
- `flight_numbers[]`
- `operated_by`
- `aircraft`
- `amenities[]`
