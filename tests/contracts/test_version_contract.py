"""Contract tests for gfl version."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from gfl.cli.app import app
from gfl.contracts.schema import validate_contract

runner = CliRunner()


def test_version_contract():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    valid, reason = validate_contract(payload)
    assert valid, reason
    assert payload["status"] == "success"
    assert payload["results"][0]["backend"] == "fast-flights"
