"""Error code registry contract test."""

from gfl.contracts.error_codes import ErrorCode


def test_error_code_registry_is_fixed():
    assert {code.value for code in ErrorCode} == {
        "INVALID_INPUT",
        "UPSTREAM_FORMAT_CHANGED",
        "UPSTREAM_UNAVAILABLE",
        "RATE_LIMITED",
        "TIMEOUT",
        "INTERNAL_ERROR",
    }
