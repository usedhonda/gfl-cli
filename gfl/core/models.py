"""Core query models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

TripType = Literal["one-way", "round-trip", "multi-city"]
SeatType = Literal["economy", "premium-economy", "business", "first"]
OutputFormat = Literal["json", "human"]
SortType = Literal["best", "cheapest"]
CalendarViewType = Literal["date-grid", "price-graph"]


@dataclass(frozen=True)
class SegmentSpec:
    origin: str
    destination: str
    date: date

    def to_payload(self) -> dict[str, str]:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "date": self.date.isoformat(),
        }


@dataclass(frozen=True)
class SearchQueryInput:
    origin: str | None
    destination: str | None
    date: str | None
    return_date: str | None
    trip: str
    seat: str
    max_stops: int | None
    airline: tuple[str, ...]
    adults: int
    children: int
    infants_in_seat: int
    infants_on_lap: int
    currency: str | None
    timeout_sec: int
    retries: int
    sort: str = "best"
    max_price: int | None = None
    depart_after: str | None = None
    depart_before: str | None = None
    arrive_after: str | None = None
    arrive_before: str | None = None
    max_duration_min: int | None = None
    segments: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchQuery:
    origin: str
    destination: str
    date: date
    return_date: date | None
    trip: TripType
    seat: SeatType
    max_stops: int | None
    airline: tuple[str, ...]
    adults: int
    children: int
    infants_in_seat: int
    infants_on_lap: int
    currency: str
    timeout_sec: int
    retries: int
    sort: SortType
    max_price: int | None
    depart_after_min: int | None
    depart_before_min: int | None
    arrive_after_min: int | None
    arrive_before_min: int | None
    max_duration_min: int | None
    segments: tuple[SegmentSpec, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "date": self.date.isoformat(),
            "return_date": self.return_date.isoformat() if self.return_date else None,
            "trip": self.trip,
            "seat": self.seat,
            "max_stops": self.max_stops,
            "airline": list(self.airline),
            "adults": self.adults,
            "children": self.children,
            "infants_in_seat": self.infants_in_seat,
            "infants_on_lap": self.infants_on_lap,
            "currency": self.currency,
            "timeout_sec": self.timeout_sec,
            "retries": self.retries,
            "sort": self.sort,
            "max_price": self.max_price,
            "depart_after_min": self.depart_after_min,
            "depart_before_min": self.depart_before_min,
            "arrive_after_min": self.arrive_after_min,
            "arrive_before_min": self.arrive_before_min,
            "max_duration_min": self.max_duration_min,
            "segments": [segment.to_payload() for segment in self.segments],
        }


@dataclass(frozen=True)
class CalendarQueryInput:
    origin: str
    destination: str
    start_date: str
    end_date: str
    trip_duration: int | None
    is_round_trip: bool
    seat: str
    max_stops: int | None
    airline: tuple[str, ...]
    currency: str | None
    timeout_sec: int
    retries: int
    view: str = "date-grid"


@dataclass(frozen=True)
class CalendarQuery:
    origin: str
    destination: str
    start_date: date
    end_date: date
    trip_duration: int | None
    is_round_trip: bool
    seat: SeatType
    max_stops: int | None
    airline: tuple[str, ...]
    currency: str
    timeout_sec: int
    retries: int
    view: CalendarViewType

    def to_payload(self) -> dict[str, object]:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "trip_duration": self.trip_duration,
            "is_round_trip": self.is_round_trip,
            "seat": self.seat,
            "max_stops": self.max_stops,
            "airline": list(self.airline),
            "currency": self.currency,
            "timeout_sec": self.timeout_sec,
            "retries": self.retries,
            "view": self.view,
        }
