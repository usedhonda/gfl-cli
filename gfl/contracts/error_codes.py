"""Stable error code registry for CLI contract."""

from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    UPSTREAM_FORMAT_CHANGED = "UPSTREAM_FORMAT_CHANGED"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


ALLOWED_ERROR_CODES = frozenset(code.value for code in ErrorCode)
