"""Human format smoke tests."""

from __future__ import annotations

from typer.testing import CliRunner

from gfl.adapters.fast_flights import client as ff_client
from gfl.cli.app import app

runner = CliRunner()


def test_search_human_format_smoke(monkeypatch):
    monkeypatch.setattr(
        ff_client,
        "search_flights",
        lambda _query: ff_client.ProviderResponse(
            current_price="typical",
            warnings=[],
            flights=[
                {
                    "rank": 1,
                    "is_best": True,
                    "airline": "Example Air",
                    "departure": "8:00 AM",
                    "arrival": "9:00 AM",
                    "arrival_time_ahead": "",
                    "duration": "1 hr",
                    "stops": 0,
                    "delay": None,
                    "price": {"text": "$99", "amount": 99, "currency": "USD"},
                }
            ],
        ),
    )

    result = runner.invoke(
        app,
        [
            "search",
            "--origin",
            "SFO",
            "--destination",
            "LAX",
            "--date",
            "2026-03-23",
            "--format",
            "human",
        ],
    )

    assert result.exit_code == 0
    assert "search success" in result.stdout
    assert "{" not in result.stdout
