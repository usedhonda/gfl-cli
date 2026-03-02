"""Response builders for stable CLI output contract."""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from gfl.contracts.error_codes import ErrorCode
from gfl.contracts.schema import assert_contract

SOURCE = "fast-flights"


def _meta(started_at: float, warnings: list[str] | None = None) -> dict[str, Any]:
    latency_ms = int((perf_counter() - started_at) * 1000)
    return {
        "source": SOURCE,
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "latency_ms": max(latency_ms, 0),
        "warnings": list(warnings or []),
    }


def success_response(
    *,
    request_id: str,
    query: dict[str, Any],
    results: list[dict[str, Any]],
    started_at: float,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "success",
        "request_id": request_id,
        "query": query,
        "results": results,
        "meta": _meta(started_at, warnings),
        "error": None,
    }
    assert_contract(payload)
    return payload


def failure_response(
    *,
    request_id: str,
    query: dict[str, Any],
    code: ErrorCode,
    message: str,
    retriable: bool,
    started_at: float,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "failed",
        "request_id": request_id,
        "query": query,
        "results": [],
        "meta": _meta(started_at, warnings),
        "error": {
            "code": code.value,
            "message": message,
            "retriable": retriable,
        },
    }
    assert_contract(payload)
    return payload
