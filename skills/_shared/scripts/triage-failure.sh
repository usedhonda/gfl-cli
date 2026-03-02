#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <failure-json-file>" >&2
  exit 2
fi

json_file="$1"
if [[ ! -f "$json_file" ]]; then
  echo "File not found: $json_file" >&2
  exit 2
fi

code="$(uv run python - "$json_file" << 'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    payload = json.load(f)
print((payload.get("error") or {}).get("code") or "")
PY
)"

case "$code" in
  INVALID_INPUT)
    echo "class=client_input"
    echo "next=fix input and rerun"
    ;;
  UPSTREAM_UNAVAILABLE)
    echo "class=upstream_availability"
    echo "next=retry later or narrow query scope"
    ;;
  UPSTREAM_FORMAT_CHANGED)
    echo "class=parser_drift"
    echo "next=run probe + parity gate and inspect selector assumptions"
    ;;
  TIMEOUT)
    echo "class=timeout"
    echo "next=increase timeout and rerun"
    ;;
  RATE_LIMITED)
    echo "class=rate_limit"
    echo "next=backoff and retry"
    ;;
  INTERNAL_ERROR)
    echo "class=internal"
    echo "next=capture payload and escalate"
    ;;
  *)
    echo "class=unknown"
    echo "next=manual triage"
    ;;
esac
