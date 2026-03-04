#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <gfl calendar args...>" >&2
  echo "Example: $0 --origin SFO --destination LAX --start-date 2026-03-23 --end-date 2026-03-25 --currency USD" >&2
  exit 2
fi

tmp_out="$(mktemp)"
trap 'rm -f "$tmp_out"' EXIT

uv run gfl calendar "$@" --view price-graph --format json >"$tmp_out"

uv run python - "$tmp_out" << 'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    payload = json.load(f)

results = payload.get("results", [])
missing = 0
for row in results:
    graph = row.get("graph", {})
    if graph.get("y_is_missing"):
        missing += 1

print(json.dumps({
    "status": payload.get("status"),
    "result_count": len(results),
    "missing_points": missing,
    "warnings": payload.get("meta", {}).get("warnings", []),
}, ensure_ascii=False))
PY

cat "$tmp_out"
