#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <gfl search args...>" >&2
  echo "Example: $0 --origin SFO --destination LAX --date 2026-03-23 --lang en-US --currency USD" >&2
  exit 2
fi

tmp_out="$(mktemp)"
trap 'rm -f "$tmp_out"' EXIT

uv run gfl search "$@" --format json >"$tmp_out"

uv run python - "$tmp_out" << 'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    payload = json.load(f)

print(json.dumps({
    "status": payload.get("status"),
    "error": payload.get("error"),
    "warnings": payload.get("meta", {}).get("warnings", []),
    "result_count": len(payload.get("results", [])),
}, ensure_ascii=False))
PY

cat "$tmp_out"
