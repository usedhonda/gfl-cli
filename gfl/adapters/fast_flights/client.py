"""fast-flights provider client."""

from __future__ import annotations

import re
from dataclasses import dataclass
from time import sleep
from typing import Any

from fast_flights import FlightData, Passengers
from fast_flights.core import parse_response
from fast_flights.filter import TFSData
from fast_flights.primp import Client
from selectolax.lexbor import LexborHTMLParser

from gfl.adapters.fast_flights.mapper import map_flights
from gfl.core.models import SearchQuery

FLIGHTS_URL = "https://www.google.com/travel/flights"
TFU_VALUE = "EgQIABABIgA"

_AIRLINE_RE = re.compile(r"flight with (?P<airline>.+?)\. Leaves ")
_TRIP_RE = re.compile(
    r"Leaves (?P<dep_airport>.+?) at (?P<dep_time>.+?) and arrives at "
    r"(?P<arr_airport>.+?) at (?P<arr_time>.+?)\."
)
_DURATION_RE = re.compile(r"Total duration (?P<duration>.+?)\.")
_PRICE_RE = re.compile(r"From (?P<price>[0-9][0-9,]*) ")
_STOPS_RE = re.compile(r"(?P<stops>Nonstop|\d+ stop(?:s)?) flight with ")
_AIRLINE_JA_RE = re.compile(r"。 (?P<airline>.+?) が運航する")
_TRIP_JA_RE = re.compile(
    r"[、 ](?P<dep_time>\d{1,2}:\d{2}).*?発、.*?[、 ](?P<arr_time>\d{1,2}:\d{2}).*?着"
)
_DURATION_JA_RE = re.compile(r"合計時間 (?P<duration>.+?)。")
_PRICE_JA_RE = re.compile(r"合計金額 (?P<price>[0-9][0-9,]*) 円")
_STOPS_JA_RE = re.compile(r"(?P<stops>直行便|\d+\s*か所経由|\d+\s*回乗り継ぎ)")


class UpstreamError(RuntimeError):
    """Base class for provider errors."""


class UpstreamFormatChangedError(UpstreamError):
    """Raised when parser can no longer parse upstream payload."""


class UpstreamUnavailableError(UpstreamError):
    """Raised when upstream returns bad status or network errors."""


class UpstreamRateLimitedError(UpstreamError):
    """Raised when upstream responds with rate limiting."""


class UpstreamTimeoutError(UpstreamError):
    """Raised when request exceeds timeout budget."""


@dataclass(frozen=True)
class ProviderResponse:
    current_price: str
    flights: list[dict[str, Any]]
    warnings: list[str]


def _looks_like_timeout(exc: Exception) -> bool:
    text = str(exc).lower()
    return "timed out" in text or "timeout" in text


def _is_no_flights_runtime_error(exc: RuntimeError) -> bool:
    return "no flights found" in str(exc).lower()


def _backoff_seconds(attempt_index: int) -> float:
    return min(0.25 * (2**attempt_index), 2.0)


def _parse_stops(value: str | None):
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    if "nonstop" in normalized or "non-stop" in normalized or "直行" in value:
        return 0
    digits = re.search(r"\d+", value)
    if digits:
        return int(digits.group(0))
    first = value.split(" ", 1)[0]
    return int(first) if first.isdigit() else None


def _extract_aria_fallback_details(html: str) -> list[dict[str, Any]]:
    parser = LexborHTMLParser(html)
    nodes = parser.css('ul.Rk10dc li div[role="link"][aria-label]')
    details: list[dict[str, Any]] = []

    for node in nodes:
        label = node.attributes.get("aria-label", "")
        airline_match = _AIRLINE_RE.search(label)
        airline_ja_match = _AIRLINE_JA_RE.search(label)
        trip_match = _TRIP_RE.search(label)
        trip_ja_match = _TRIP_JA_RE.search(label)
        duration_match = _DURATION_RE.search(label)
        duration_ja_match = _DURATION_JA_RE.search(label)
        price_match = _PRICE_RE.search(label)
        price_ja_match = _PRICE_JA_RE.search(label)
        stops_match = _STOPS_RE.search(label)
        stops_ja_match = _STOPS_JA_RE.search(label)

        price_value = None
        if price_match:
            raw_price = price_match.group("price").replace(",", "")
            if raw_price.isdigit():
                price_value = int(raw_price)
        elif price_ja_match:
            raw_price = price_ja_match.group("price").replace(",", "")
            if raw_price.isdigit():
                price_value = int(raw_price)

        details.append(
            {
                "airline": (
                    airline_match.group("airline").strip()
                    if airline_match
                    else (
                        airline_ja_match.group("airline").strip()
                        if airline_ja_match
                        else ""
                    )
                ),
                "departure": (
                    trip_match.group("dep_time").strip()
                    if trip_match
                    else (
                        trip_ja_match.group("dep_time").strip()
                        if trip_ja_match
                        else ""
                    )
                ),
                "arrival": (
                    trip_match.group("arr_time").strip()
                    if trip_match
                    else (
                        trip_ja_match.group("arr_time").strip()
                        if trip_ja_match
                        else ""
                    )
                ),
                "duration": (
                    duration_match.group("duration").strip()
                    if duration_match
                    else (
                        duration_ja_match.group("duration").strip()
                        if duration_ja_match
                        else ""
                    )
                ),
                "stops": _parse_stops(
                    stops_match.group("stops")
                    if stops_match
                    else (
                        stops_ja_match.group("stops")
                        if stops_ja_match
                        else None
                    )
                ),
                "price_amount": price_value,
            }
        )
    return details


def _apply_fallback_details(
    flights: list[dict[str, Any]],
    fallback_details: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    for index, detail in enumerate(fallback_details):
        if index >= len(flights):
            break
        row = flights[index]

        if not row.get("airline") and detail.get("airline"):
            row["airline"] = detail["airline"]
        if not row.get("departure") and detail.get("departure"):
            row["departure"] = detail["departure"]
        if not row.get("arrival") and detail.get("arrival"):
            row["arrival"] = detail["arrival"]
        if not row.get("duration") and detail.get("duration"):
            row["duration"] = detail["duration"]
        if row.get("stops") in {None, "Unknown", ""} and detail.get("stops") is not None:
            row["stops"] = detail["stops"]

        price = row.get("price")
        if (
            isinstance(price, dict)
            and price.get("amount") is None
            and detail.get("price_amount") is not None
        ):
            price["amount"] = detail["price_amount"]
    return flights


def _build_segments(query: SearchQuery) -> list[FlightData]:
    if query.trip == "multi-city":
        if not query.segments:
            raise UpstreamFormatChangedError("multi-city query missing segments")
        return [
            FlightData(
                date=segment.date.isoformat(),
                from_airport=segment.origin,
                to_airport=segment.destination,
                max_stops=query.max_stops,
            )
            for segment in query.segments
        ]

    segments = [
        FlightData(
            date=query.date.isoformat(),
            from_airport=query.origin,
            to_airport=query.destination,
            max_stops=query.max_stops,
        )
    ]
    if query.trip == "round-trip":
        if query.return_date is None:
            raise UpstreamFormatChangedError("round-trip query missing return_date")
        segments.append(
            FlightData(
                date=query.return_date.isoformat(),
                from_airport=query.destination,
                to_airport=query.origin,
                max_stops=query.max_stops,
            )
        )
    return segments


def _build_params(query: SearchQuery) -> dict[str, str]:
    tfs = TFSData.from_interface(
        flight_data=_build_segments(query),
        trip=query.trip,
        passengers=Passengers(
            adults=query.adults,
            children=query.children,
            infants_in_seat=query.infants_in_seat,
            infants_on_lap=query.infants_on_lap,
        ),
        seat=query.seat,
        max_stops=query.max_stops,
    ).as_b64()

    return {
        "tfs": tfs.decode("utf-8"),
        "hl": query.lang,
        "tfu": TFU_VALUE,
        "curr": query.currency,
    }


def _request_once(query: SearchQuery) -> ProviderResponse:
    params = _build_params(query)
    client = Client(impersonate="chrome_144", verify=False, timeout=query.timeout_sec)

    try:
        response = client.get(FLIGHTS_URL, params=params, timeout=query.timeout_sec)
    except Exception as exc:
        if _looks_like_timeout(exc):
            raise UpstreamTimeoutError(f"request timed out: {exc}") from exc
        raise UpstreamUnavailableError(f"upstream request failed: {exc}") from exc

    if response.status_code == 429:
        raise UpstreamRateLimitedError("upstream returned 429")
    if response.status_code != 200:
        raise UpstreamUnavailableError(f"upstream returned HTTP {response.status_code}")

    try:
        parsed = parse_response(response)
    except RuntimeError as exc:
        if _is_no_flights_runtime_error(exc):
            raise UpstreamUnavailableError("no flights found from upstream source") from exc
        raise UpstreamFormatChangedError(str(exc)) from exc
    except Exception as exc:
        raise UpstreamFormatChangedError(f"provider parse failed: {exc}") from exc

    mapped_flights = map_flights(
        flights=parsed.flights,
        currency=query.currency,
        itinerary_segments=[segment.to_payload() for segment in query.segments],
    )
    fallback_details = _extract_aria_fallback_details(response.text)
    mapped_flights = _apply_fallback_details(mapped_flights, fallback_details)

    return ProviderResponse(
        current_price=str(parsed.current_price),
        flights=mapped_flights,
        warnings=[],
    )


def search_flights(query: SearchQuery) -> ProviderResponse:
    attempts = query.retries + 1
    last_exc: Exception | None = None

    for attempt in range(attempts):
        try:
            return _request_once(query)
        except UpstreamRateLimitedError:
            raise
        except (UpstreamTimeoutError, UpstreamUnavailableError, UpstreamFormatChangedError) as exc:
            last_exc = exc
            if attempt >= attempts - 1:
                raise
            sleep(_backoff_seconds(attempt))

    raise UpstreamUnavailableError(str(last_exc) if last_exc else "unknown upstream error")
