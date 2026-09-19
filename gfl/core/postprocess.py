"""Post-processing for provider flight results."""

from __future__ import annotations

import re
from typing import Any

from gfl.core.models import SearchQuery

_AMPM_TIME_RE = re.compile(r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>[AP]M)", re.IGNORECASE)
_TIME_24H_RE = re.compile(r"(?<!\d)(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)(?!\d)")
_PRICE_AMOUNT_RE = re.compile(r"\d[\d,]*")
_FLIGHT_NUMBER_CODE_RE = re.compile(r"^(?P<code>[A-Z0-9]{2,3})\d{1,4}$")
_CODE_IN_TEXT_RE = re.compile(r"\((?P<code>[A-Z0-9]{2,3})\)")

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
    "JL": ("jal", "japan airlines"),
    "NH": ("ana", "all nippon"),
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
    if match:
        hour = int(match.group("hour"))
        minute = int(match.group("minute"))
        ampm = match.group("ampm").upper()

        if hour == 12:
            hour = 0
        if ampm == "PM":
            hour += 12

        return hour * 60 + minute

    match_24h = _TIME_24H_RE.search(text)
    if not match_24h:
        return None
    return int(match_24h.group("hour")) * 60 + int(match_24h.group("minute"))


def parse_duration_minutes(raw: str) -> int | None:
    text = _normalize_space(raw)
    lower = text.lower()
    hr_match = re.search(r"(\d+)\s*(?:hr|hour|h)\b", lower)
    min_match = re.search(r"(\d+)\s*(?:min|minute|m)\b", lower)

    hr = int(hr_match.group(1)) if hr_match else 0
    minute = int(min_match.group(1)) if min_match else 0

    if not hr_match and not min_match:
        colon_match = re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)", text)
        if colon_match:
            hr = int(colon_match.group(1))
            minute = int(colon_match.group(2))

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


def _extract_airline_codes_from_row(row: dict[str, Any]) -> set[str]:
    found: set[str] = set()

    for field in ("airline", "operated_by"):
        text = _normalize_space(str(row.get(field, ""))).upper()
        for match in _CODE_IN_TEXT_RE.finditer(text):
            found.add(match.group("code"))

    raw_numbers = row.get("flight_numbers")
    if isinstance(raw_numbers, list):
        for value in raw_numbers:
            normalized = str(value).upper().replace(" ", "")
            match = _FLIGHT_NUMBER_CODE_RE.match(normalized)
            if match:
                found.add(match.group("code"))

    return found


def _matches_airline_filter(row: dict[str, Any], codes: tuple[str, ...]) -> bool:
    normalized = _normalize_space(
        f"{row.get('airline', '')} {row.get('operated_by', '')}"
    ).lower()
    if not normalized:
        return False

    row_codes = _extract_airline_codes_from_row(row)

    for code in codes:
        normalized_code = code.upper().strip()
        if normalized_code in row_codes:
            return True
        for keyword in _airline_keywords(code):
            if keyword in normalized:
                return True
    return False


def _parse_price_amount(text: str) -> int | None:
    match = _PRICE_AMOUNT_RE.search(text)
    if not match:
        return None
    return int(match.group(0).replace(",", ""))


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
            if not _matches_airline_filter(row, query.airline):
                continue

        if query.max_price is not None:
            if not isinstance(price_amount, int):
                parsed_amount = _parse_price_amount(str(price.get("text", "")))
                if parsed_amount is not None:
                    price_amount = parsed_amount
                    if isinstance(price, dict):
                        price["amount"] = parsed_amount
                else:
                    unknown_counts["price"] += 1
                    continue
            if price_amount > query.max_price:
                continue

        if query.max_duration_min is not None:
            duration_min = row.get("duration_min")
            if not isinstance(duration_min, int):
                duration_min = parse_duration_minutes(str(row.get("duration", "")))
                if isinstance(duration_min, int):
                    row["duration_min"] = duration_min
            if duration_min is None:
                unknown_counts["duration"] += 1
                continue
            if duration_min > query.max_duration_min:
                continue

        if query.depart_after_min is not None or query.depart_before_min is not None:
            departure_min = row.get("departure_min")
            if not isinstance(departure_min, int):
                departure_min = parse_ampm_time_minutes(str(row.get("departure", "")))
                if isinstance(departure_min, int):
                    row["departure_min"] = departure_min
            if departure_min is None:
                unknown_counts["departure_time"] += 1
                continue
            if query.depart_after_min is not None and departure_min < query.depart_after_min:
                continue
            if query.depart_before_min is not None and departure_min > query.depart_before_min:
                continue

        if query.arrive_after_min is not None or query.arrive_before_min is not None:
            arrival_min = row.get("arrival_min")
            if not isinstance(arrival_min, int):
                arrival_min = parse_ampm_time_minutes(str(row.get("arrival", "")))
                if isinstance(arrival_min, int):
                    row["arrival_min"] = arrival_min
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
