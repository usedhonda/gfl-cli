"""Search command wiring."""

from __future__ import annotations

from typing import Annotated

import typer

from gfl.cli.commands._common import (
    DEFAULT_CURRENCY,
    DEFAULT_LANG,
    emit_payload,
    resolve_output_format,
)
from gfl.core.models import SearchQueryInput
from gfl.core.service import run_search


def _render_human(payload: dict[str, object]) -> str:
    if payload["status"] == "failed":
        error = payload["error"]
        return f"search failed: {error['code']} - {error['message']}"

    result_block = payload["results"][0]
    header = [
        "search success",
        f"trip: {result_block['trip']}",
        f"current_price_band: {result_block['current_price_band']}",
        f"flight_count: {result_block['flight_count']}",
    ]

    top_lines = []
    for flight in result_block["flights"][:5]:
        segment = (
            f"{flight['airline']}: {flight['departure']} -> {flight['arrival']} "
            f"({flight['price']['text']})"
        )
        top_lines.append(f"- {segment}")

    return "\n".join(header + top_lines)


def register(app: typer.Typer) -> None:
    @app.command("search")
    def search_command(
        origin: Annotated[
            str | None,
            typer.Option("--origin", help="Origin IATA code (required unless trip=multi-city)"),
        ] = None,
        destination: Annotated[
            str | None,
            typer.Option("--destination", help="Destination IATA code (required unless trip=multi-city)"),
        ] = None,
        date: Annotated[
            str | None,
            typer.Option("--date", help="Departure date YYYY-MM-DD (required unless trip=multi-city)"),
        ] = None,
        return_date: Annotated[
            str | None,
            typer.Option("--return-date", help="Return date YYYY-MM-DD for round-trip"),
        ] = None,
        trip: Annotated[
            str,
            typer.Option("--trip", help="one-way|round-trip|multi-city"),
        ] = "one-way",
        seat: Annotated[
            str,
            typer.Option("--seat", help="economy|premium-economy|business|first"),
        ] = "economy",
        max_stops: Annotated[int | None, typer.Option("--max-stops")] = None,
        airline: Annotated[list[str], typer.Option("--airline")] = [],
        adults: Annotated[int, typer.Option("--adults")] = 1,
        children: Annotated[int, typer.Option("--children")] = 0,
        infants_in_seat: Annotated[int, typer.Option("--infants-in-seat")] = 0,
        infants_on_lap: Annotated[int, typer.Option("--infants-on-lap")] = 0,
        lang: Annotated[str | None, typer.Option("--lang")] = DEFAULT_LANG,
        currency: Annotated[str | None, typer.Option("--currency")] = DEFAULT_CURRENCY,
        timeout_sec: Annotated[int, typer.Option("--timeout-sec")] = 30,
        retries: Annotated[int, typer.Option("--retries")] = 2,
        sort: Annotated[str, typer.Option("--sort", help="best|cheapest")] = "best",
        max_price: Annotated[int | None, typer.Option("--max-price")] = None,
        depart_after: Annotated[str | None, typer.Option("--depart-after")] = None,
        depart_before: Annotated[str | None, typer.Option("--depart-before")] = None,
        arrive_after: Annotated[str | None, typer.Option("--arrive-after")] = None,
        arrive_before: Annotated[str | None, typer.Option("--arrive-before")] = None,
        max_duration_min: Annotated[int | None, typer.Option("--max-duration-min")] = None,
        segment: Annotated[
            list[str],
            typer.Option(
                "--segment",
                help="Repeat for multi-city: FROM:TO:YYYY-MM-DD",
            ),
        ] = [],
        output_format: Annotated[str, typer.Option("--format")] = "json",
        human: Annotated[bool, typer.Option("--human")] = False,
    ) -> None:
        payload = run_search(
            SearchQueryInput(
                origin=origin,
                destination=destination,
                date=date,
                return_date=return_date,
                trip=trip,
                seat=seat,
                max_stops=max_stops,
                airline=tuple(airline),
                adults=adults,
                children=children,
                infants_in_seat=infants_in_seat,
                infants_on_lap=infants_on_lap,
                lang=lang,
                currency=currency,
                timeout_sec=timeout_sec,
                retries=retries,
                sort=sort,
                max_price=max_price,
                depart_after=depart_after,
                depart_before=depart_before,
                arrive_after=arrive_after,
                arrive_before=arrive_before,
                max_duration_min=max_duration_min,
                segments=tuple(segment),
            )
        )
        emit_payload(
            payload,
            output_format=resolve_output_format(output_format, human),
            human_renderer=_render_human,
        )
