"""Calendar command wiring."""

from __future__ import annotations

from typing import Annotated

import typer

from gfl.cli.commands._common import (
    DEFAULT_CURRENCY,
    emit_payload,
    resolve_output_format,
)
from gfl.core.models import CalendarQueryInput
from gfl.core.service import run_calendar


def _render_human(payload: dict[str, object]) -> str:
    if payload["status"] == "failed":
        error = payload["error"]
        return f"calendar failed: {error['code']} - {error['message']}"

    lines = ["calendar success"]
    for row in payload["results"]:
        lowest = row["lowest_price"]["amount"]
        lines.append(
            f"- {row['date']} (return={row['return_date']}): "
            f"lowest={lowest} {row['lowest_price']['currency']} flights={row['flight_count']}"
        )
    return "\n".join(lines)


def register(app: typer.Typer) -> None:
    @app.command("calendar")
    def calendar_command(
        origin: Annotated[str, typer.Option("--origin", help="Origin IATA code")],
        destination: Annotated[str, typer.Option("--destination", help="Destination IATA code")],
        start_date: Annotated[str, typer.Option("--start-date", help="Start date YYYY-MM-DD")],
        end_date: Annotated[str, typer.Option("--end-date", help="End date YYYY-MM-DD")],
        trip_duration: Annotated[int | None, typer.Option("--trip-duration")] = None,
        is_round_trip: Annotated[bool, typer.Option("--is-round-trip")] = False,
        seat: Annotated[
            str,
            typer.Option("--seat", help="economy|premium-economy|business|first"),
        ] = "economy",
        max_stops: Annotated[int | None, typer.Option("--max-stops")] = None,
        airline: Annotated[list[str], typer.Option("--airline")] = [],
        currency: Annotated[str | None, typer.Option("--currency")] = DEFAULT_CURRENCY,
        timeout_sec: Annotated[int, typer.Option("--timeout-sec")] = 30,
        retries: Annotated[int, typer.Option("--retries")] = 2,
        view: Annotated[str, typer.Option("--view", help="date-grid|price-graph")] = "date-grid",
        output_format: Annotated[str, typer.Option("--format")] = "json",
        human: Annotated[bool, typer.Option("--human")] = False,
    ) -> None:
        payload = run_calendar(
            CalendarQueryInput(
                origin=origin,
                destination=destination,
                start_date=start_date,
                end_date=end_date,
                trip_duration=trip_duration,
                is_round_trip=is_round_trip,
                seat=seat,
                max_stops=max_stops,
                airline=tuple(airline),
                currency=currency,
                timeout_sec=timeout_sec,
                retries=retries,
                view=view,
            )
        )
        emit_payload(
            payload,
            output_format=resolve_output_format(output_format, human),
            human_renderer=_render_human,
        )
