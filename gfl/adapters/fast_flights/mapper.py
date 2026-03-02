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
            "price": {
                "text": price_text,
                "amount": parse_price_amount(price_text),
                "currency": currency,
            },
        }
        if segments:
            row["segments"] = [dict(segment) for segment in segments]
        mapped.append(row)
    return mapped
