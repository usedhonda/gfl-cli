"""Map provider entities into CLI result objects."""

from __future__ import annotations

import re
from typing import Any

_PRICE_RE = re.compile(r"\d[\d,]*")


def parse_price_amount(price_text: str) -> int | None:
    match = _PRICE_RE.search(price_text)
    if not match:
        return None
    return int(match.group(0).replace(",", ""))


def _map_emissions(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {
            "kg_co2e": None,
            "delta_percent": None,
            "relative_label": None,
        }

    return {
        "kg_co2e": getattr(raw, "kg_co2e", None),
        "delta_percent": getattr(raw, "delta_percent", None),
        "relative_label": getattr(raw, "relative_label", None),
    }


def _map_layovers(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    mapped: list[dict[str, Any]] = []
    for item in raw:
        mapped.append(
            {
                "airport_code": getattr(item, "airport_code", None),
                "duration_text": getattr(item, "duration_text", None),
                "duration_min": getattr(item, "duration_min", None),
            }
        )
    return mapped


def _map_fare_policy(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {
            "carry_on_included": None,
            "checked_bag_included": None,
            "changeable": None,
            "refundable": None,
        }

    return {
        "carry_on_included": getattr(raw, "carry_on_included", None),
        "checked_bag_included": getattr(raw, "checked_bag_included", None),
        "changeable": getattr(raw, "changeable", None),
        "refundable": getattr(raw, "refundable", None),
    }


def map_flights(
    *,
    flights: list[Any],
    currency: str,
    itinerary_segments: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    segments = [dict(segment) for segment in (itinerary_segments or [])]
    mapped: list[dict[str, Any]] = []
    for index, flight in enumerate(flights, start=1):
        price_text = str(getattr(flight, "price", ""))
        row: dict[str, Any] = {
            "rank": index,
            "is_best": bool(getattr(flight, "is_best", False)),
            "airline": str(getattr(flight, "name", "")),
            "departure": str(getattr(flight, "departure", "")),
            "arrival": str(getattr(flight, "arrival", "")),
            "arrival_time_ahead": str(getattr(flight, "arrival_time_ahead", "")),
            "duration": str(getattr(flight, "duration", "")),
            "stops": getattr(flight, "stops", None),
            "delay": getattr(flight, "delay", None),
            "origin_airport": getattr(flight, "origin_airport", None),
            "destination_airport": getattr(flight, "destination_airport", None),
            "return_departure": getattr(flight, "return_departure", None),
            "return_arrival": getattr(flight, "return_arrival", None),
            "return_duration": getattr(flight, "return_duration", None),
            "return_stops": getattr(flight, "return_stops", None),
            "return_origin_airport": getattr(flight, "return_origin_airport", None),
            "return_destination_airport": getattr(flight, "return_destination_airport", None),
            "return_leg_available": bool(getattr(flight, "return_leg_available", False)),
            "price": {
                "text": price_text,
                "amount": parse_price_amount(price_text),
                "currency": currency,
            },
            "self_transfer": bool(getattr(flight, "self_transfer", False)),
            "emissions": _map_emissions(getattr(flight, "emissions", None)),
            "layovers": _map_layovers(getattr(flight, "layovers", None)),
            "flight_numbers": list(getattr(flight, "flight_numbers", []) or []),
            "operated_by": getattr(flight, "operated_by", None),
            "aircraft": getattr(flight, "aircraft", None),
            "amenities": list(getattr(flight, "amenities", []) or []),
            "fare_policy": _map_fare_policy(getattr(flight, "fare_policy", None)),
        }
        if segments:
            row["segments"] = [dict(segment) for segment in segments]
        mapped.append(row)
    return mapped
