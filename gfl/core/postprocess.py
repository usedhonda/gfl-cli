"""Post-processing for provider flight results."""

from __future__ import annotations

import re
from typing import Any

from gfl.core.models import SearchQuery

_AMPM_TIME_RE = re.compile(r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>[AP]M)", re.IGNORECASE)
_DURATION_RE = re.compile(r"(?:(?P<hr>\d+)\s*hr)?\s*(?:(?P<min>\d+)\s*min)?", re.IGNORECASE)

# Best-effort keyword mapping for common airline IATA codes.
_AIRLINE_CODE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "AA": ("american",),
    "DL": ("delta",),
    "UA": ("united",),
    "AS": ("alaska",),
    "WN": ("southwest",),
    "B6": ("jetblue",),
    "F9": ("frontier",),
    "NK": ("spirit",),
    "HA": ("hawaiian",),
    "JL": ("japan airlines", "jal"),
    "NH": ("all nippon", "ana"),
    "AC": ("air canada",),
    "BA": ("british airways",),
    "AF": ("air france",),
    "LH": ("lufthansa",),
    "KL": ("klm",),
    "IB": ("iberia",),
    "EK": ("emirates",),
    "QR": ("qatar",),
    "TK": ("turkish",),
    "SQ": ("singapore",),
    "CX": ("cathay",),
    "QF": ("qantas",),
    "KE": ("korean air",),
    "OZ": ("asiana",),
}


def _normalize_space(text: str) -> str:
    return text.replace("\u202f", " ").replace("\xa0", " ").strip()


def parse_ampm_time_minutes(raw: str) -> int | None:
    text = _normalize_space(raw)
    match = _AMPM_TIME_RE.search(text)
    if not match:
        return None

    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    ampm = match.group("ampm").upper()

    if hour == 12:
        hour = 0
    if ampm == "PM":
        hour += 12

    return hour * 60 + minute


def parse_duration_minutes(raw: str) -> int | None:
    text = _normalize_space(raw)
    match = _DURATION_RE.search(text)
    if not match:
        return None

    hr = int(match.group("hr")) if match.group("hr") else 0
    minute = int(match.group("min")) if match.group("min") else 0
    total = hr * 60 + minute
    return total if total > 0 else None


def _clone_flight_row(row: dict[str, Any]) -> dict[str, Any]:
    cloned = dict(row)
    price = cloned.get("price")
    if isinstance(price, dict):
        cloned["price"] = dict(price)
    return cloned


def _airline_keywords(code: str) -> tuple[str, ...]:
    normalized = code.upper().strip()
    return _AIRLINE_CODE_KEYWORDS.get(normalized, (normalized.lower(),))


def _matches_airline_filter(airline_text: str, codes: tuple[str, ...]) -> bool:
    normalized = _normalize_space(airline_text).lower()
    if not normalized:
        return False

    for code in codes:
        for keyword in _airline_keywords(code):
            if keyword in normalized:
                return True
    return False


def _filter_rows(
    *,
    rows: list[dict[str, Any]],
    query: SearchQuery,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    unknown_counts = {
        "departure_time": 0,
        "arrival_time": 0,
        "duration": 0,
        "price": 0,
    }

    filtered: list[dict[str, Any]] = []
    for row in rows:
        price = row.get("price") if isinstance(row.get("price"), dict) else {}
        price_amount = price.get("amount")

        if query.max_stops is not None:
            stops = row.get("stops")
            if not isinstance(stops, int) or stops > query.max_stops:
                continue

        if query.airline:
            if not _matches_airline_filter(str(row.get("airline", "")), query.airline):
                continue

        if query.max_price is not None:
            if not isinstance(price_amount, int):
                unknown_counts["price"] += 1
                continue
            if price_amount > query.max_price:
                continue

        if query.max_duration_min is not None:
            duration_min = parse_duration_minutes(str(row.get("duration", "")))
            if duration_min is None:
                unknown_counts["duration"] += 1
                continue
            if duration_min > query.max_duration_min:
                continue

        if query.depart_after_min is not None or query.depart_before_min is not None:
            departure_min = parse_ampm_time_minutes(str(row.get("departure", "")))
            if departure_min is None:
                unknown_counts["departure_time"] += 1
                continue
            if query.depart_after_min is not None and departure_min < query.depart_after_min:
                continue
            if query.depart_before_min is not None and departure_min > query.depart_before_min:
                continue

        if query.arrive_after_min is not None or query.arrive_before_min is not None:
            arrival_min = parse_ampm_time_minutes(str(row.get("arrival", "")))
            if arrival_min is None:
                unknown_counts["arrival_time"] += 1
                continue
            if query.arrive_after_min is not None and arrival_min < query.arrive_after_min:
                continue
            if query.arrive_before_min is not None and arrival_min > query.arrive_before_min:
                continue

        filtered.append(row)

    return filtered, unknown_counts


def _sort_rows(rows: list[dict[str, Any]], sort_mode: str) -> list[dict[str, Any]]:
    if sort_mode == "cheapest":
        rows.sort(
            key=lambda row: (
                not isinstance((row.get("price") or {}).get("amount"), int),
                ((row.get("price") or {}).get("amount") or 0),
                row.get("rank", 0),
            )
        )
    return rows


def _warnings_for_unknowns(unknown_counts: dict[str, int]) -> list[str]:
    warnings: list[str] = []
    for key, count in unknown_counts.items():
        if count > 0:
            warnings.append(f"postprocess.{key}.unknown={count}")
    return warnings


def apply_search_postprocess(
    *,
    flights: list[dict[str, Any]],
    query: SearchQuery,
) -> tuple[list[dict[str, Any]], list[str]]:
    rows = [_clone_flight_row(row) for row in flights]
    rows, unknown_counts = _filter_rows(rows=rows, query=query)
    rows = _sort_rows(rows, query.sort)

    for index, row in enumerate(rows, start=1):
        row["rank"] = index

    warnings = _warnings_for_unknowns(unknown_counts)
    return rows, warnings
