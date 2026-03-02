"""Contract validation helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from gfl.contracts.error_codes import ALLOWED_ERROR_CODES

REQUIRED_TOP_LEVEL_FIELDS = {
    "status",
    "request_id",
    "query",
    "results",
    "meta",
    "error",
}
REQUIRED_META_FIELDS = {"source", "generated_at_utc", "latency_ms", "warnings"}
REQUIRED_ERROR_FIELDS = {"code", "message", "retriable"}


def validate_contract(payload: Any) -> tuple[bool, str]:
    if not isinstance(payload, Mapping):
        return False, "payload must be an object"

    keys = set(payload.keys())
    if keys != REQUIRED_TOP_LEVEL_FIELDS:
        return False, f"invalid top-level fields: {sorted(keys)}"

    status = payload.get("status")
    if status not in {"success", "failed"}:
        return False, "status must be success|failed"

    request_id = payload.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        return False, "request_id must be a non-empty string"

    if not isinstance(payload.get("query"), Mapping):
        return False, "query must be an object"

    results = payload.get("results")
    if not isinstance(results, list):
        return False, "results must be an array"

    meta = payload.get("meta")
    if not isinstance(meta, Mapping):
        return False, "meta must be an object"
    if set(meta.keys()) != REQUIRED_META_FIELDS:
        return False, f"invalid meta fields: {sorted(meta.keys())}"
    if not isinstance(meta.get("source"), str) or not meta.get("source"):
        return False, "meta.source must be a non-empty string"
    if not isinstance(meta.get("generated_at_utc"), str) or not meta.get("generated_at_utc"):
        return False, "meta.generated_at_utc must be a non-empty string"
    if not isinstance(meta.get("latency_ms"), int) or meta.get("latency_ms") < 0:
        return False, "meta.latency_ms must be a non-negative int"
    if not isinstance(meta.get("warnings"), list):
        return False, "meta.warnings must be an array"

    error = payload.get("error")
    if status == "success":
        if error is not None:
            return False, "error must be null for success responses"
    else:
        if results != []:
            return False, "results must be [] for failed responses"
        if not isinstance(error, Mapping):
            return False, "error must be an object for failed responses"
        if set(error.keys()) != REQUIRED_ERROR_FIELDS:
            return False, f"invalid error fields: {sorted(error.keys())}"

        code = error.get("code")
        if not isinstance(code, str) or code not in ALLOWED_ERROR_CODES:
            return False, f"error.code must be one of {sorted(ALLOWED_ERROR_CODES)}"
        if not isinstance(error.get("message"), str) or not error.get("message"):
            return False, "error.message must be a non-empty string"
        if not isinstance(error.get("retriable"), bool):
            return False, "error.retriable must be a bool"

    return True, ""


def assert_contract(payload: Any) -> None:
    valid, reason = validate_contract(payload)
    if not valid:
        raise ValueError(f"contract violation: {reason}")
