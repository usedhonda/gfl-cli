"""Contract tests for fast-flights adapter error classification."""

from __future__ import annotations

from datetime import date

import pytest

from gfl.adapters.fast_flights import client as ff_client
from gfl.core.models import SearchQuery, SegmentSpec


class _FakeResponse:
    status_code = 200
    text = "<html></html>"


class _FakeClient:
    def __init__(self, **_kwargs):
        pass

    def get(self, *_args, **_kwargs):
        return _FakeResponse()


def _query(trip: str) -> SearchQuery:
    segments: tuple[SegmentSpec, ...] = ()
    return_date = None
    if trip == "round-trip":
        return_date = date(2026, 6, 30)
    if trip == "multi-city":
        segments = (
            SegmentSpec(origin="HND", destination="JFK", date=date(2026, 5, 23)),
            SegmentSpec(origin="JFK", destination="HND", date=date(2026, 6, 30)),
        )

    return SearchQuery(
        origin="HND",
        destination="JFK",
        date=date(2026, 5, 23),
        return_date=return_date,
        trip=trip,
        seat="premium-economy",
        max_stops=0,
        airline=(),
        adults=1,
        children=0,
        infants_in_seat=0,
        infants_on_lap=0,
        currency="USD",
        timeout_sec=30,
        retries=0,
        sort="best",
        max_price=None,
        depart_after_min=None,
        depart_before_min=None,
        arrive_after_min=None,
        arrive_before_min=None,
        max_duration_min=None,
        segments=segments,
    )


@pytest.mark.parametrize("trip", ["one-way", "round-trip", "multi-city"])
def test_request_once_no_flights_found_maps_to_upstream_unavailable(monkeypatch, trip):
    monkeypatch.setattr(ff_client, "_build_params", lambda _query: {})
    monkeypatch.setattr(ff_client, "Client", _FakeClient)

    def _raise_no_flights(_response):
        raise RuntimeError("No flights found")

    monkeypatch.setattr(ff_client, "parse_response", _raise_no_flights)

    with pytest.raises(ff_client.UpstreamUnavailableError):
        ff_client._request_once(_query(trip))


def test_request_once_runtime_error_without_no_flights_maps_to_format_changed(monkeypatch):
    monkeypatch.setattr(ff_client, "_build_params", lambda _query: {})
    monkeypatch.setattr(ff_client, "Client", _FakeClient)

    def _raise_layout_changed(_response):
        raise RuntimeError("layout parse failed")

    monkeypatch.setattr(ff_client, "parse_response", _raise_layout_changed)

    with pytest.raises(ff_client.UpstreamFormatChangedError):
        ff_client._request_once(_query("one-way"))
