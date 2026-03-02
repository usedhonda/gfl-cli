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


def map_flights(*, flights: list[Any], currency: str) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for index, flight in enumerate(flights, start=1):
        price_text = str(getattr(flight, "price", ""))
        mapped.append(
            {
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
        )
    return mapped
