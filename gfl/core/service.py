"""Service layer bridging CLI inputs and provider adapters."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from importlib.metadata import PackageNotFoundError, version
from time import perf_counter
from uuid import uuid4

from gfl import __version__ as CLI_VERSION
from gfl.adapters.fast_flights import client as ff_client
from gfl.adapters.fast_flights.mapper import parse_price_amount
from gfl.contracts.error_codes import ErrorCode
from gfl.contracts.response import failure_response, success_response
from gfl.core.models import (
    CalendarQuery,
    CalendarQueryInput,
    SearchQuery,
    SearchQueryInput,
)
from gfl.core.postprocess import apply_search_postprocess
from gfl.core.validation import InputValidationError, validate_calendar_input, validate_search_input


def _request_id() -> str:
    return uuid4().hex


def _failure_from_exception(
    *,
    request_id: str,
    query: dict[str, object],
    started_at: float,
    exc: Exception,
):
    if isinstance(exc, InputValidationError):
        return failure_response(
            request_id=request_id,
            query=query,
            code=ErrorCode.INVALID_INPUT,
            message=str(exc),
            retriable=False,
            started_at=started_at,
        )
    if isinstance(exc, ff_client.UpstreamRateLimitedError):
        return failure_response(
            request_id=request_id,
            query=query,
            code=ErrorCode.RATE_LIMITED,
            message=str(exc),
            retriable=True,
            started_at=started_at,
        )
    if isinstance(exc, ff_client.UpstreamTimeoutError):
        return failure_response(
            request_id=request_id,
            query=query,
            code=ErrorCode.TIMEOUT,
            message=str(exc),
            retriable=True,
            started_at=started_at,
        )
    if isinstance(exc, ff_client.UpstreamFormatChangedError):
        return failure_response(
            request_id=request_id,
            query=query,
            code=ErrorCode.UPSTREAM_FORMAT_CHANGED,
            message=str(exc),
            retriable=True,
            started_at=started_at,
        )
    if isinstance(exc, ff_client.UpstreamUnavailableError):
        return failure_response(
            request_id=request_id,
            query=query,
            code=ErrorCode.UPSTREAM_UNAVAILABLE,
            message=str(exc),
            retriable=True,
            started_at=started_at,
        )

    return failure_response(
        request_id=request_id,
        query=query,
        code=ErrorCode.INTERNAL_ERROR,
        message=str(exc) or "internal error",
        retriable=False,
        started_at=started_at,
    )


def _merge_warnings(*warning_groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in warning_groups:
        for warning in group:
            if warning not in merged:
                merged.append(warning)
    return merged


def _normalize_search_result(
    *,
    query: SearchQuery,
    flights: list[dict[str, object]],
    current_price: str,
) -> list[dict[str, object]]:
    return [
        {
            "trip": query.trip,
            "seat": query.seat,
            "current_price_band": current_price,
            "flight_count": len(flights),
            "flights": flights,
        }
    ]


def _search_with_postprocess(
    query: SearchQuery,
) -> tuple[ff_client.ProviderResponse, list[dict[str, object]], list[str]]:
    provider_response = ff_client.search_flights(query)
    processed_flights, postprocess_warnings = apply_search_postprocess(
        flights=provider_response.flights,
        query=query,
    )
    warnings = _merge_warnings(provider_response.warnings, postprocess_warnings)

    return provider_response, processed_flights, warnings


def _annotate_directional_rows(
    *,
    flights: list[dict[str, object]],
    direction: str,
    origin: str,
    destination: str,
    date: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for leg_rank, row in enumerate(flights, start=1):
        cloned = dict(row)
        cloned["direction"] = direction
        cloned["leg_origin"] = origin
        cloned["leg_destination"] = destination
        cloned["leg_date"] = date
        cloned["leg_rank"] = leg_rank
        rows.append(cloned)
    return rows


def _annotate_single_direction_rows(
    *,
    query: SearchQuery,
    flights: list[dict[str, object]],
) -> list[dict[str, object]]:
    annotated: list[dict[str, object]] = []
    default_direction = "multi-city" if query.trip == "multi-city" else "outbound"

    for leg_rank, row in enumerate(flights, start=1):
        cloned = dict(row)
        origin = cloned.get("origin_airport") or query.origin
        destination = cloned.get("destination_airport") or query.destination
        date_value = query.date.isoformat()

        segments = cloned.get("segments")
        if query.trip == "multi-city" and isinstance(segments, list) and segments:
            first_segment = segments[0] if isinstance(segments[0], dict) else {}
            date_value = str(first_segment.get("date") or date_value)

        cloned["direction"] = str(cloned.get("direction") or default_direction)
        cloned["leg_origin"] = str(origin)
        cloned["leg_destination"] = str(destination)
        cloned["leg_date"] = date_value
        cloned["leg_rank"] = leg_rank
        annotated.append(cloned)

    return annotated


def _annotate_calendar_price_rank(results: list[dict[str, object]]) -> None:
    ranked: list[tuple[int, int]] = []
    for index, row in enumerate(results):
        lowest = row.get("lowest_price") if isinstance(row.get("lowest_price"), dict) else {}
        amount = lowest.get("amount")
        if isinstance(amount, int):
            ranked.append((index, amount))

    ranked.sort(key=lambda item: item[1])
    rank_map: dict[int, int] = {}
    current_rank = 0
    last_amount: int | None = None
    for index, amount in ranked:
        if last_amount is None or amount > last_amount:
            current_rank += 1
            last_amount = amount
        rank_map[index] = current_rank

    for index, row in enumerate(results):
        rank = rank_map.get(index)
        row["price_rank"] = rank
        row["is_cheapest"] = rank == 1 if rank is not None else False


def run_search(raw_query: SearchQueryInput) -> dict[str, object]:
    started_at = perf_counter()
    request_id = _request_id()
    fallback_query = {
        "origin": raw_query.origin,
        "destination": raw_query.destination,
        "date": raw_query.date,
        "return_date": raw_query.return_date,
        "trip": raw_query.trip,
        "seat": raw_query.seat,
        "segments": list(raw_query.segments),
    }

    try:
        query = validate_search_input(raw_query)
        warnings: list[str] = []
        current_price_band = "typical"

        if query.trip == "round-trip":
            if query.return_date is None:
                raise InputValidationError("return-date is required when trip=round-trip")

            outbound_query = replace(
                query,
                trip="one-way",
                return_date=None,
                origin=query.origin,
                destination=query.destination,
                date=query.date,
            )
            inbound_query = replace(
                query,
                trip="one-way",
                return_date=None,
                origin=query.destination,
                destination=query.origin,
                date=query.return_date,
            )

            outbound_response, outbound_flights, outbound_warnings = _search_with_postprocess(
                outbound_query
            )
            inbound_response, inbound_flights, inbound_warnings = _search_with_postprocess(
                inbound_query
            )

            outbound_rows = _annotate_directional_rows(
                flights=outbound_flights,
                direction="outbound",
                origin=query.origin,
                destination=query.destination,
                date=query.date.isoformat(),
            )
            inbound_rows = _annotate_directional_rows(
                flights=inbound_flights,
                direction="inbound",
                origin=query.destination,
                destination=query.origin,
                date=query.return_date.isoformat(),
            )
            processed_flights = outbound_rows + inbound_rows
            for rank, row in enumerate(processed_flights, start=1):
                row["rank"] = rank

            warnings = _merge_warnings(
                outbound_warnings,
                inbound_warnings,
                ["trip.round_trip=split_one_way"],
            )
            current_price_band = (
                f"outbound:{outbound_response.current_price}|"
                f"inbound:{inbound_response.current_price}"
            )
        else:
            provider_response, processed_flights, warnings = _search_with_postprocess(query)
            current_price_band = provider_response.current_price
            if query.segments:
                query_segments = [segment.to_payload() for segment in query.segments]
                for row in processed_flights:
                    current_segments = row.get("segments")
                    if isinstance(current_segments, list) and current_segments:
                        continue
                    row["segments"] = [dict(segment) for segment in query_segments]

            processed_flights = _annotate_single_direction_rows(
                query=query,
                flights=processed_flights,
            )

            if query.trip == "multi-city":
                warnings = _merge_warnings(warnings, ["multi_city.segments=request_echo"])

        return success_response(
            request_id=request_id,
            query=query.to_payload(),
            results=_normalize_search_result(
                query=query,
                flights=processed_flights,
                current_price=current_price_band,
            ),
            started_at=started_at,
            warnings=warnings,
        )
    except Exception as exc:  # noqa: BLE001
        return _failure_from_exception(
            request_id=request_id,
            query=fallback_query,
            started_at=started_at,
            exc=exc,
        )


def _calendar_search_query(
    *,
    calendar_query: CalendarQuery,
    depart_date,
    return_date,
) -> SearchQuery:
    return SearchQuery(
        origin=calendar_query.origin,
        destination=calendar_query.destination,
        date=depart_date,
        return_date=return_date,
        trip="round-trip" if calendar_query.is_round_trip else "one-way",
        seat=calendar_query.seat,
        max_stops=calendar_query.max_stops,
        airline=calendar_query.airline,
        adults=1,
        children=0,
        infants_in_seat=0,
        infants_on_lap=0,
        currency=calendar_query.currency,
        timeout_sec=calendar_query.timeout_sec,
        retries=calendar_query.retries,
        sort="cheapest",
        max_price=None,
        depart_after_min=None,
        depart_before_min=None,
        arrive_after_min=None,
        arrive_before_min=None,
        max_duration_min=None,
    )


def run_calendar(raw_query: CalendarQueryInput) -> dict[str, object]:
    started_at = perf_counter()
    request_id = _request_id()
    fallback_query = {
        "origin": raw_query.origin,
        "destination": raw_query.destination,
        "start_date": raw_query.start_date,
        "end_date": raw_query.end_date,
        "trip_duration": raw_query.trip_duration,
        "is_round_trip": raw_query.is_round_trip,
    }

    try:
        query = validate_calendar_input(raw_query)
        cursor = query.start_date
        results: list[dict[str, object]] = []
        warnings: list[str] = []

        while cursor <= query.end_date:
            return_date = None
            if query.is_round_trip and query.trip_duration is not None:
                return_date = cursor + timedelta(days=query.trip_duration)

            search_query = _calendar_search_query(
                calendar_query=query,
                depart_date=cursor,
                return_date=return_date,
            )
            provider_response = ff_client.search_flights(search_query)
            flights, postprocess_warnings = apply_search_postprocess(
                flights=provider_response.flights,
                query=search_query,
            )

            warnings = _merge_warnings(warnings, provider_response.warnings, postprocess_warnings)

            flight_prices = []
            for flight in flights:
                price = flight.get("price") if isinstance(flight.get("price"), dict) else {}
                amount = price.get("amount")
                if isinstance(amount, int):
                    flight_prices.append(amount)
                    continue

                parsed = parse_price_amount(str(price.get("text", "")))
                if parsed is not None:
                    flight_prices.append(parsed)

            lowest_price = min(flight_prices) if flight_prices else None

            results.append(
                {
                    "date": cursor.isoformat(),
                    "return_date": return_date.isoformat() if return_date else None,
                    "trip_duration_days": (
                        (return_date - cursor).days if return_date is not None else None
                    ),
                    "current_price_band": provider_response.current_price,
                    "flight_count": len(flights),
                    "lowest_price": {
                        "amount": lowest_price,
                        "currency": query.currency,
                    },
                }
            )
            cursor += timedelta(days=1)

        _annotate_calendar_price_rank(results)

        if query.view == "price-graph":
            amounts = [
                row["lowest_price"]["amount"]
                for row in results
                if isinstance(row.get("lowest_price"), dict)
                and isinstance(row["lowest_price"].get("amount"), int)
            ]
            min_amount = min(amounts) if amounts else None
            max_amount = max(amounts) if amounts else None
            avg_amount = round(sum(amounts) / len(amounts), 2) if amounts else None

            for index, row in enumerate(results, start=1):
                lowest_price = row.get("lowest_price") if isinstance(row.get("lowest_price"), dict) else {}
                y_amount = lowest_price.get("amount")
                if not isinstance(y_amount, int):
                    y_amount = None

                row["graph"] = {
                    "point_index": index,
                    "y_amount": y_amount,
                    "y_is_missing": y_amount is None,
                    "min_amount_in_range": min_amount,
                    "max_amount_in_range": max_amount,
                    "avg_amount_in_range": avg_amount,
                }

            warnings = _merge_warnings(warnings, ["calendar.view=price-graph"])

        return success_response(
            request_id=request_id,
            query=query.to_payload(),
            results=results,
            started_at=started_at,
            warnings=warnings,
        )
    except Exception as exc:  # noqa: BLE001
        return _failure_from_exception(
            request_id=request_id,
            query=fallback_query,
            started_at=started_at,
            exc=exc,
        )


def run_version() -> dict[str, object]:
    started_at = perf_counter()
    request_id = _request_id()

    try:
        backend_version = version("fast-flights")
    except PackageNotFoundError:
        backend_version = "unknown"

    return success_response(
        request_id=request_id,
        query={},
        results=[
            {
                "cli_version": CLI_VERSION,
                "backend": "fast-flights",
                "backend_version": backend_version,
            }
        ],
        started_at=started_at,
        warnings=[],
    )
