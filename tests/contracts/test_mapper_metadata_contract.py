"""Contract tests for metadata mapping from fast-flights rows."""

from __future__ import annotations

from types import SimpleNamespace

from gfl.adapters.fast_flights.mapper import map_flights


def test_map_flights_includes_extended_metadata_fields():
    flight = SimpleNamespace(
        is_best=True,
        name="All Nippon Airways",
        departure="10:55 AM",
        arrival="5:15 PM",
        arrival_time_ahead="",
        duration="7 hr 20 min",
        stops=1,
        delay=None,
        price="$1,234",
        self_transfer=False,
        emissions=SimpleNamespace(kg_co2e=300, delta_percent=-16, relative_label="lower"),
        layovers=[
            SimpleNamespace(airport_code="SIN", duration_text="2 hr 50 min", duration_min=170),
        ],
        flight_numbers=["NH801"],
        operated_by="All Nippon Airways",
        aircraft="Boeing 787-9",
        amenities=["wifi", "power"],
    )

    rows = map_flights(flights=[flight], currency="USD")
    assert len(rows) == 1

    row = rows[0]
    assert row["self_transfer"] is False
    assert row["emissions"] == {
        "kg_co2e": 300,
        "delta_percent": -16,
        "relative_label": "lower",
    }
    assert row["layovers"] == [
        {
            "airport_code": "SIN",
            "duration_text": "2 hr 50 min",
            "duration_min": 170,
        }
    ]
    assert row["flight_numbers"] == ["NH801"]
    assert row["operated_by"] == "All Nippon Airways"
    assert row["aircraft"] == "Boeing 787-9"
    assert row["amenities"] == ["wifi", "power"]


def test_map_flights_defaults_extended_metadata_fields_when_missing():
    flight = SimpleNamespace(
        is_best=False,
        name="Example Air",
        departure="8:00 AM",
        arrival="9:00 AM",
        arrival_time_ahead="",
        duration="1 hr",
        stops=0,
        delay=None,
        price="$99",
    )

    rows = map_flights(flights=[flight], currency="USD")
    row = rows[0]

    assert row["self_transfer"] is False
    assert row["emissions"] == {
        "kg_co2e": None,
        "delta_percent": None,
        "relative_label": None,
    }
    assert row["layovers"] == []
    assert row["flight_numbers"] == []
    assert row["operated_by"] is None
    assert row["aircraft"] is None
    assert row["amenities"] == []
