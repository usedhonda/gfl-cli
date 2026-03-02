"""Typer app wiring."""

from __future__ import annotations

import typer

from gfl.cli.commands import calendar, search, version

app = typer.Typer(help="JSON-first Google Flights CLI")

search.register(app)
calendar.register(app)
version.register(app)
