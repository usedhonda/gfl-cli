"""Contract tests for gfl calendar."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from gfl.adapters.fast_flights import client as ff_client
from gfl.cli.app import app
from gfl.contracts.schema import validate_contract

runner = CliRunner()


def _calendar_args() -> list[str]:
    return [
        "calendar",
        "--origin",
        "SFO",
        "--destination",
        "LAX",
        "--start-date",
        "2026-03-23",
        "--end-date",
        "2026-03-25",
    ]


def test_calendar_success_contract(monkeypatch):
    prices = [99, 89, 109]

    def _fake(_query):
        value = prices.pop(0)
        return ff_client.ProviderResponse(
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
                    "price": {"text": f"${value}", "amount": value, "currency": "USD"},
                }
            ],
        )

    monkeypatch.setattr(ff_client, "search_flights", _fake)

    result = runner.invoke(app, _calendar_args())
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    valid, reason = validate_contract(payload)
    assert valid, reason
    assert payload["status"] == "success"
    assert len(payload["results"]) == 3
    assert all("graph" not in row for row in payload["results"])


def test_calendar_invalid_range_returns_invalid_input():
    result = runner.invoke(
        app,
        [
            "calendar",
            "--origin",
            "SFO",
            "--destination",
            "LAX",
            "--start-date",
            "2026-03-25",
            "--end-date",
            "2026-03-23",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "INVALID_INPUT"


def test_calendar_currency_and_view_warning(monkeypatch):
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
                    "price": {"text": "¥12000", "amount": 12000, "currency": "JPY"},
                }
            ],
        ),
    )

    result = runner.invoke(
        app,
        _calendar_args()
        + [
            "--currency",
            "JPY",
            "--view",
            "price-graph",
        ],
    )
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["query"]["currency"] == "JPY"
    assert payload["query"]["view"] == "price-graph"
    assert "calendar.view=price-graph" in payload["meta"]["warnings"]
    assert len(payload["results"]) == 3

    for index, row in enumerate(payload["results"], start=1):
        graph = row["graph"]
        assert graph["point_index"] == index
        assert graph["y_amount"] == 12000
        assert graph["y_is_missing"] is False
        assert graph["min_amount_in_range"] == 12000
        assert graph["max_amount_in_range"] == 12000
        assert graph["avg_amount_in_range"] == 12000.0
