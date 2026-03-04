"""Contract tests for gfl search."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from gfl.adapters.fast_flights import client as ff_client
from gfl.cli.app import app
from gfl.contracts.schema import validate_contract

runner = CliRunner()


def _fake_provider_response() -> ff_client.ProviderResponse:
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
                "price": {"text": "$99", "amount": 99, "currency": "USD"},
            }
        ],
    )


def _base_args() -> list[str]:
    return [
        "search",
        "--origin",
        "SFO",
        "--destination",
        "LAX",
        "--date",
        "2026-03-23",
    ]


def test_search_one_way_success_contract(monkeypatch):
    monkeypatch.setattr(ff_client, "search_flights", lambda _query: _fake_provider_response())

    result = runner.invoke(app, _base_args())
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    valid, reason = validate_contract(payload)
    assert valid, reason
    assert payload["status"] == "success"
    assert payload["results"][0]["trip"] == "one-way"


def test_search_round_trip_success_contract(monkeypatch):
    monkeypatch.setattr(ff_client, "search_flights", lambda _query: _fake_provider_response())

    result = runner.invoke(
        app,
        _base_args()
        + [
            "--trip",
            "round-trip",
            "--return-date",
            "2026-03-30",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    valid, reason = validate_contract(payload)
    assert valid, reason
    assert payload["results"][0]["trip"] == "round-trip"


def test_search_round_trip_splits_directional_rows(monkeypatch):
    calls = []

    def _fake_search(query):
        calls.append((query.trip, query.origin, query.destination, query.date.isoformat()))
        return _fake_provider_response()

    monkeypatch.setattr(ff_client, "search_flights", _fake_search)

    result = runner.invoke(
        app,
        _base_args()
        + [
            "--trip",
            "round-trip",
            "--return-date",
            "2026-03-30",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    flights = payload["results"][0]["flights"]
    assert len(calls) == 2
    assert calls[0][0] == "one-way"
    assert calls[0][1] == "SFO"
    assert calls[0][2] == "LAX"
    assert calls[1][0] == "one-way"
    assert calls[1][1] == "LAX"
    assert calls[1][2] == "SFO"
    assert flights[0]["direction"] == "outbound"
    assert flights[1]["direction"] == "inbound"
    assert "trip.round_trip=split_one_way" in payload["meta"]["warnings"]


def test_search_multi_city_success_contract(monkeypatch):
    monkeypatch.setattr(ff_client, "search_flights", lambda _query: _fake_provider_response())

    result = runner.invoke(
        app,
        [
            "search",
            "--trip",
            "multi-city",
            "--segment",
            "SFO:NRT:2026-03-23",
            "--segment",
            "NRT:CTS:2026-03-26",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    valid, reason = validate_contract(payload)
    assert valid, reason
    assert payload["results"][0]["trip"] == "multi-city"
    assert len(payload["query"]["segments"]) == 2
    assert len(payload["results"][0]["flights"][0]["segments"]) == 2
    assert "multi_city.segments=request_echo" in payload["meta"]["warnings"]


def test_search_invalid_iata_returns_invalid_input():
    result = runner.invoke(
        app,
        [
            "search",
            "--origin",
            "SFOO",
            "--destination",
            "LAX",
            "--date",
            "2026-03-23",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "INVALID_INPUT"


def test_search_invalid_date_returns_invalid_input():
    result = runner.invoke(
        app,
        [
            "search",
            "--origin",
            "SFO",
            "--destination",
            "LAX",
            "--date",
            "2026-23-03",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "INVALID_INPUT"


def test_search_multi_city_segment_format_returns_invalid_input():
    result = runner.invoke(
        app,
        [
            "search",
            "--trip",
            "multi-city",
            "--segment",
            "SFO-NRT-2026-03-23",
            "--segment",
            "NRT:CTS:2026-03-26",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "INVALID_INPUT"


def test_search_multi_city_requires_at_least_two_segments():
    result = runner.invoke(
        app,
        [
            "search",
            "--trip",
            "multi-city",
            "--segment",
            "SFO:NRT:2026-03-23",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "INVALID_INPUT"


def test_search_multi_city_rejects_origin_destination_date_flags():
    result = runner.invoke(
        app,
        _base_args()
        + [
            "--trip",
            "multi-city",
            "--segment",
            "SFO:NRT:2026-03-23",
            "--segment",
            "NRT:CTS:2026-03-26",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "INVALID_INPUT"


def test_search_invalid_passenger_combination_returns_invalid_input():
    result = runner.invoke(
        app,
        _base_args()
        + [
            "--adults",
            "1",
            "--infants-on-lap",
            "2",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "INVALID_INPUT"


def test_search_upstream_format_changed(monkeypatch):
    def _raise(_query):
        raise ff_client.UpstreamFormatChangedError("layout changed")

    monkeypatch.setattr(ff_client, "search_flights", _raise)
    result = runner.invoke(app, _base_args())

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "UPSTREAM_FORMAT_CHANGED"


def test_search_timeout(monkeypatch):
    def _raise(_query):
        raise ff_client.UpstreamTimeoutError("timed out")

    monkeypatch.setattr(ff_client, "search_flights", _raise)
    result = runner.invoke(app, _base_args())

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "TIMEOUT"


def test_search_upstream_unavailable(monkeypatch):
    def _raise(_query):
        raise ff_client.UpstreamUnavailableError("upstream unavailable")

    monkeypatch.setattr(ff_client, "search_flights", _raise)
    result = runner.invoke(app, _base_args())

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "UPSTREAM_UNAVAILABLE"


def test_search_currency_propagation(monkeypatch):
    monkeypatch.setattr(ff_client, "search_flights", lambda _query: _fake_provider_response())

    result = runner.invoke(
        app,
        _base_args()
        + [
            "--currency",
            "JPY",
        ],
    )
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["query"]["currency"] == "JPY"


def test_search_does_not_retry_with_locale_fallback_when_filters_return_empty(monkeypatch):
    calls = []

    def _fake_search(query):
        calls.append((query.origin, query.destination, query.date.isoformat()))
        return ff_client.ProviderResponse(
            current_price="typical",
            warnings=[],
            flights=[],
        )

    monkeypatch.setattr(ff_client, "search_flights", _fake_search)
    result = runner.invoke(
        app,
        _base_args()
        + [
            "--currency",
            "JPY",
            "--max-stops",
            "0",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert calls == [("SFO", "LAX", "2026-03-23")]
    assert payload["results"][0]["flight_count"] == 0
    assert "locale.fallback=ja->en-US" not in payload["meta"]["warnings"]


def test_search_airline_filter_matches_nh_with_english_airline_text(monkeypatch):
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
                    "airline": "All Nippon Airways (ANA)",
                    "departure": "8:00 AM",
                    "arrival": "9:00 AM",
                    "arrival_time_ahead": "",
                    "duration": "1 hr",
                    "stops": 0,
                    "delay": None,
                    "price": {"text": "¥99000", "amount": 99000, "currency": "JPY"},
                },
                {
                    "rank": 2,
                    "is_best": False,
                    "airline": "Japan Airlines (JAL)",
                    "departure": "10:00 AM",
                    "arrival": "11:00 AM",
                    "arrival_time_ahead": "",
                    "duration": "1 hr",
                    "stops": 0,
                    "delay": None,
                    "price": {"text": "¥101000", "amount": 101000, "currency": "JPY"},
                },
            ],
        ),
    )

    result = runner.invoke(
        app,
        _base_args()
        + [
            "--airline",
            "NH",
            "--currency",
            "JPY",
        ],
    )
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    flights = payload["results"][0]["flights"]
    assert len(flights) == 1
    assert payload["results"][0]["flight_count"] == 1
    assert flights[0]["airline"] == "All Nippon Airways (ANA)"


def test_search_airline_filter_matches_jl_with_english_airline_text(monkeypatch):
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
                    "airline": "All Nippon Airways (ANA)",
                    "departure": "8:00 AM",
                    "arrival": "9:00 AM",
                    "arrival_time_ahead": "",
                    "duration": "1 hr",
                    "stops": 0,
                    "delay": None,
                    "price": {"text": "¥99000", "amount": 99000, "currency": "JPY"},
                },
                {
                    "rank": 2,
                    "is_best": False,
                    "airline": "Japan Airlines (JAL)",
                    "departure": "10:00 AM",
                    "arrival": "11:00 AM",
                    "arrival_time_ahead": "",
                    "duration": "1 hr",
                    "stops": 0,
                    "delay": None,
                    "price": {"text": "¥101000", "amount": 101000, "currency": "JPY"},
                },
            ],
        ),
    )

    result = runner.invoke(
        app,
        _base_args()
        + [
            "--airline",
            "JL",
            "--currency",
            "JPY",
        ],
    )
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    flights = payload["results"][0]["flights"]
    assert len(flights) == 1
    assert payload["results"][0]["flight_count"] == 1
    assert flights[0]["airline"] == "Japan Airlines (JAL)"


def test_no_flights_found_maps_to_upstream_unavailable(monkeypatch):
    """RuntimeError('No flights found') must map to UPSTREAM_UNAVAILABLE, not UPSTREAM_FORMAT_CHANGED."""

    def _raise(_query):
        raise RuntimeError("No flights found: SFO to LAX")

    monkeypatch.setattr(
        "gfl.adapters.fast_flights.client.parse_response",
        _raise,
    )
    # Stub the HTTP layer so _request_once reaches parse_response.
    _fake_response = type("R", (), {"status_code": 200, "text": ""})()
    monkeypatch.setattr(
        "gfl.adapters.fast_flights.client.Client.get",
        lambda *_a, **_kw: _fake_response,
    )

    result = runner.invoke(app, _base_args())

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "UPSTREAM_UNAVAILABLE"


def test_search_sort_cheapest_reorders_and_reranks(monkeypatch):
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
                    "arrival": "10:00 AM",
                    "arrival_time_ahead": "",
                    "duration": "2 hr",
                    "stops": 0,
                    "delay": None,
                    "price": {"text": "$120", "amount": 120, "currency": "USD"},
                },
                {
                    "rank": 2,
                    "is_best": False,
                    "airline": "Example Air",
                    "departure": "9:00 AM",
                    "arrival": "11:00 AM",
                    "arrival_time_ahead": "",
                    "duration": "2 hr",
                    "stops": 0,
                    "delay": None,
                    "price": {"text": "$80", "amount": 80, "currency": "USD"},
                },
                {
                    "rank": 3,
                    "is_best": False,
                    "airline": "Example Air",
                    "departure": "10:00 AM",
                    "arrival": "12:00 PM",
                    "arrival_time_ahead": "",
                    "duration": "2 hr",
                    "stops": 0,
                    "delay": None,
                    "price": {"text": "$90", "amount": 90, "currency": "USD"},
                },
            ],
        ),
    )

    result = runner.invoke(app, _base_args() + ["--sort", "cheapest"])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    flights = payload["results"][0]["flights"]
    assert [row["price"]["amount"] for row in flights] == [80, 90, 120]
    assert [row["rank"] for row in flights] == [1, 2, 3]


def test_search_max_price_filters_and_emits_unknown_price_warning(monkeypatch):
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
                    "arrival": "10:00 AM",
                    "arrival_time_ahead": "",
                    "duration": "2 hr",
                    "stops": 0,
                    "delay": None,
                    "price": {"text": "$150", "amount": 150, "currency": "USD"},
                },
                {
                    "rank": 2,
                    "is_best": False,
                    "airline": "Example Air",
                    "departure": "9:00 AM",
                    "arrival": "11:00 AM",
                    "arrival_time_ahead": "",
                    "duration": "2 hr",
                    "stops": 0,
                    "delay": None,
                    "price": {"text": "$?", "amount": None, "currency": "USD"},
                },
                {
                    "rank": 3,
                    "is_best": False,
                    "airline": "Example Air",
                    "departure": "10:00 AM",
                    "arrival": "12:00 PM",
                    "arrival_time_ahead": "",
                    "duration": "2 hr",
                    "stops": 0,
                    "delay": None,
                    "price": {"text": "$95", "amount": 95, "currency": "USD"},
                },
            ],
        ),
    )

    result = runner.invoke(app, _base_args() + ["--max-price", "100"])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    flights = payload["results"][0]["flights"]
    assert len(flights) == 1
    assert flights[0]["price"]["amount"] == 95
    assert "postprocess.price.unknown=1" in payload["meta"]["warnings"]


def test_search_depart_time_window_filters(monkeypatch):
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
                    "departure": "7:00 AM",
                    "arrival": "9:00 AM",
                    "arrival_time_ahead": "",
                    "duration": "2 hr",
                    "stops": 0,
                    "delay": None,
                    "price": {"text": "$120", "amount": 120, "currency": "USD"},
                },
                {
                    "rank": 2,
                    "is_best": False,
                    "airline": "Example Air",
                    "departure": "9:00 AM",
                    "arrival": "11:00 AM",
                    "arrival_time_ahead": "",
                    "duration": "2 hr",
                    "stops": 0,
                    "delay": None,
                    "price": {"text": "$110", "amount": 110, "currency": "USD"},
                },
                {
                    "rank": 3,
                    "is_best": False,
                    "airline": "Example Air",
                    "departure": "11:00 AM",
                    "arrival": "1:00 PM",
                    "arrival_time_ahead": "",
                    "duration": "2 hr",
                    "stops": 0,
                    "delay": None,
                    "price": {"text": "$100", "amount": 100, "currency": "USD"},
                },
            ],
        ),
    )

    result = runner.invoke(
        app,
        _base_args()
        + [
            "--depart-after",
            "08:00",
            "--depart-before",
            "10:00",
        ],
    )
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    flights = payload["results"][0]["flights"]
    assert len(flights) == 1
    assert flights[0]["departure"] == "9:00 AM"


def test_search_max_duration_filters_and_emits_unknown_duration_warning(monkeypatch):
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
                    "price": {"text": "$100", "amount": 100, "currency": "USD"},
                },
                {
                    "rank": 2,
                    "is_best": False,
                    "airline": "Example Air",
                    "departure": "10:00 AM",
                    "arrival": "1:00 PM",
                    "arrival_time_ahead": "",
                    "duration": "3 hr",
                    "stops": 0,
                    "delay": None,
                    "price": {"text": "$90", "amount": 90, "currency": "USD"},
                },
                {
                    "rank": 3,
                    "is_best": False,
                    "airline": "Example Air",
                    "departure": "2:00 PM",
                    "arrival": "4:00 PM",
                    "arrival_time_ahead": "",
                    "duration": "unknown",
                    "stops": 0,
                    "delay": None,
                    "price": {"text": "$80", "amount": 80, "currency": "USD"},
                },
            ],
        ),
    )

    result = runner.invoke(app, _base_args() + ["--max-duration-min", "120"])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    flights = payload["results"][0]["flights"]
    assert len(flights) == 1
    assert flights[0]["duration"] == "1 hr"
    assert "postprocess.duration.unknown=1" in payload["meta"]["warnings"]


def test_search_invalid_depart_window_returns_invalid_input():
    result = runner.invoke(
        app,
        _base_args()
        + [
            "--depart-after",
            "20:00",
            "--depart-before",
            "10:00",
        ],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "INVALID_INPUT"
