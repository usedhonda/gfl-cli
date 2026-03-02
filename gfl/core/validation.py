"""Input validation and normalization."""

from __future__ import annotations

import re
from datetime import datetime

from gfl.core.models import (
    CalendarQuery,
    CalendarQueryInput,
    SegmentSpec,
    SearchQuery,
    SearchQueryInput,
)

IATA_RE = re.compile(r"^[A-Z]{3}$")
LANG_RE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
AIRLINE_RE = re.compile(r"^[A-Z0-9]{2,3}$")
TIME_HHMM_RE = re.compile(r"^(?P<hour>[01]\d|2[0-3]):(?P<minute>[0-5]\d)$")
ALLOWED_TRIPS = {"one-way", "round-trip", "multi-city"}
ALLOWED_SEATS = {"economy", "premium-economy", "business", "first"}
ALLOWED_SORTS = {"best", "cheapest"}
ALLOWED_CALENDAR_VIEWS = {"date-grid", "price-graph"}


class InputValidationError(ValueError):
    """Raised when a user-provided query is invalid."""


def _parse_date(raw: str, field: str):
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise InputValidationError(f"{field} must be YYYY-MM-DD") from exc


def _parse_hhmm(raw: str | None, field: str) -> int | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None

    match = TIME_HHMM_RE.fullmatch(value)
    if not match:
        raise InputValidationError(f"{field} must be HH:MM (24h)")

    return int(match.group("hour")) * 60 + int(match.group("minute"))


def _normalize_iata(raw: str, field: str) -> str:
    value = raw.upper()
    if not IATA_RE.fullmatch(value):
        raise InputValidationError(f"{field} must be a valid IATA code")
    return value


def _require_text(raw: str | None, field: str) -> str:
    if raw is None or not raw.strip():
        raise InputValidationError(f"{field} is required")
    return raw.strip()


def _normalize_lang(raw: str | None) -> str:
    if raw is None or not raw.strip():
        return "en"
    value = raw.strip()
    if not LANG_RE.fullmatch(value):
        raise InputValidationError("lang must be a valid BCP47 tag")
    return value


def _normalize_currency(raw: str | None) -> str:
    if raw is None or not raw.strip():
        return ""
    value = raw.upper().strip()
    if not CURRENCY_RE.fullmatch(value):
        raise InputValidationError("currency must be a valid ISO4217 code")
    return value


def _normalize_airlines(airlines: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for airline in airlines:
        value = airline.upper().strip()
        if not AIRLINE_RE.fullmatch(value):
            raise InputValidationError("airline must be a valid IATA airline code")
        normalized.append(value)
    return tuple(normalized)


def _parse_segment(raw: str) -> SegmentSpec:
    parts = [part.strip() for part in raw.split(":")]
    if len(parts) != 3 or any(not part for part in parts):
        raise InputValidationError("segment must be FROM:TO:YYYY-MM-DD")

    origin = _normalize_iata(parts[0], "segment origin")
    destination = _normalize_iata(parts[1], "segment destination")
    segment_date = _parse_date(parts[2], "segment date")
    return SegmentSpec(origin=origin, destination=destination, date=segment_date)


def _validate_common_runtime(timeout_sec: int, retries: int) -> None:
    if timeout_sec <= 0:
        raise InputValidationError("timeout-sec must be greater than 0")
    if retries < 0:
        raise InputValidationError("retries must be >= 0")


def _validate_passengers(
    *,
    adults: int,
    children: int,
    infants_in_seat: int,
    infants_on_lap: int,
) -> None:
    if adults <= 0:
        raise InputValidationError("adults must be >= 1")
    values = [children, infants_in_seat, infants_on_lap]
    if any(value < 0 for value in values):
        raise InputValidationError("children and infant counts must be >= 0")

    total = adults + children + infants_in_seat + infants_on_lap
    if total > 9:
        raise InputValidationError("total passengers must be <= 9")

    if infants_on_lap > adults:
        raise InputValidationError("infants-on-lap must be <= adults")


def validate_search_input(raw: SearchQueryInput) -> SearchQuery:
    trip = raw.trip.strip().lower()
    if trip not in ALLOWED_TRIPS:
        raise InputValidationError("trip must be one-way|round-trip|multi-city")

    seat = raw.seat.strip().lower()
    if seat not in ALLOWED_SEATS:
        raise InputValidationError("seat must be economy|premium-economy|business|first")

    if raw.max_stops is not None and raw.max_stops < 0:
        raise InputValidationError("max-stops must be >= 0")

    sort = raw.sort.strip().lower()
    if sort not in ALLOWED_SORTS:
        raise InputValidationError("sort must be best|cheapest")

    if raw.max_price is not None and raw.max_price <= 0:
        raise InputValidationError("max-price must be > 0")

    depart_after_min = _parse_hhmm(raw.depart_after, "depart-after")
    depart_before_min = _parse_hhmm(raw.depart_before, "depart-before")
    arrive_after_min = _parse_hhmm(raw.arrive_after, "arrive-after")
    arrive_before_min = _parse_hhmm(raw.arrive_before, "arrive-before")

    if depart_after_min is not None and depart_before_min is not None:
        if depart_after_min > depart_before_min:
            raise InputValidationError("depart-after must be <= depart-before")

    if arrive_after_min is not None and arrive_before_min is not None:
        if arrive_after_min > arrive_before_min:
            raise InputValidationError("arrive-after must be <= arrive-before")

    if raw.max_duration_min is not None and raw.max_duration_min <= 0:
        raise InputValidationError("max-duration-min must be > 0")

    origin: str
    destination: str
    depart_date = None
    return_date = None
    segments: tuple[SegmentSpec, ...] = ()

    if trip == "multi-city":
        if raw.origin and raw.origin.strip():
            raise InputValidationError("origin is not allowed when trip=multi-city")
        if raw.destination and raw.destination.strip():
            raise InputValidationError("destination is not allowed when trip=multi-city")
        if raw.date and raw.date.strip():
            raise InputValidationError("date is not allowed when trip=multi-city")
        if raw.return_date and raw.return_date.strip():
            raise InputValidationError("return-date is not allowed when trip=multi-city")

        parsed_segments = tuple(_parse_segment(item) for item in raw.segments)
        if len(parsed_segments) < 2:
            raise InputValidationError("at least 2 --segment values are required when trip=multi-city")

        segments = parsed_segments
        origin = segments[0].origin
        destination = segments[-1].destination
        depart_date = segments[0].date
    else:
        origin = _normalize_iata(_require_text(raw.origin, "origin"), "origin")
        destination = _normalize_iata(_require_text(raw.destination, "destination"), "destination")
        depart_date = _parse_date(_require_text(raw.date, "date"), "date")

        if raw.segments:
            raise InputValidationError("segment is only allowed when trip=multi-city")

        if raw.return_date:
            return_date = _parse_date(raw.return_date, "return-date")
        if trip == "round-trip" and return_date is None:
            raise InputValidationError("return-date is required when trip=round-trip")
        if return_date and return_date < depart_date:
            raise InputValidationError("return-date must be on or after date")

    _validate_passengers(
        adults=raw.adults,
        children=raw.children,
        infants_in_seat=raw.infants_in_seat,
        infants_on_lap=raw.infants_on_lap,
    )
    _validate_common_runtime(raw.timeout_sec, raw.retries)

    return SearchQuery(
        origin=origin,
        destination=destination,
        date=depart_date,
        return_date=return_date,
        trip=trip,
        seat=seat,
        max_stops=raw.max_stops,
        airline=_normalize_airlines(raw.airline),
        adults=raw.adults,
        children=raw.children,
        infants_in_seat=raw.infants_in_seat,
        infants_on_lap=raw.infants_on_lap,
        lang=_normalize_lang(raw.lang),
        currency=_normalize_currency(raw.currency),
        timeout_sec=raw.timeout_sec,
        retries=raw.retries,
        sort=sort,
        max_price=raw.max_price,
        depart_after_min=depart_after_min,
        depart_before_min=depart_before_min,
        arrive_after_min=arrive_after_min,
        arrive_before_min=arrive_before_min,
        max_duration_min=raw.max_duration_min,
        segments=segments,
    )


def validate_calendar_input(raw: CalendarQueryInput) -> CalendarQuery:
    start_date = _parse_date(raw.start_date, "start-date")
    end_date = _parse_date(raw.end_date, "end-date")
    if end_date < start_date:
        raise InputValidationError("end-date must be on or after start-date")

    if raw.trip_duration is not None and raw.trip_duration <= 0:
        raise InputValidationError("trip-duration must be > 0")
    if raw.is_round_trip and raw.trip_duration is None:
        raise InputValidationError("trip-duration is required when is-round-trip is set")

    seat = raw.seat.strip().lower()
    if seat not in ALLOWED_SEATS:
        raise InputValidationError("seat must be economy|premium-economy|business|first")

    if raw.max_stops is not None and raw.max_stops < 0:
        raise InputValidationError("max-stops must be >= 0")

    view = raw.view.strip().lower()
    if view not in ALLOWED_CALENDAR_VIEWS:
        raise InputValidationError("view must be date-grid|price-graph")

    _validate_common_runtime(raw.timeout_sec, raw.retries)

    return CalendarQuery(
        origin=_normalize_iata(raw.origin, "origin"),
        destination=_normalize_iata(raw.destination, "destination"),
        start_date=start_date,
        end_date=end_date,
        trip_duration=raw.trip_duration,
        is_round_trip=raw.is_round_trip,
        seat=seat,
        max_stops=raw.max_stops,
        airline=_normalize_airlines(raw.airline),
        lang=_normalize_lang(raw.lang),
        currency=_normalize_currency(raw.currency),
        timeout_sec=raw.timeout_sec,
        retries=raw.retries,
        view=view,
    )
