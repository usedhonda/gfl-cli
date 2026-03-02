"""Shared CLI output helpers."""

from __future__ import annotations

import json
from typing import Any, Callable

import typer

DEFAULT_LANG: str | None = None
DEFAULT_CURRENCY: str | None = None


def resolve_output_format(output_format: str, human: bool) -> str:
    value = output_format.strip().lower()
    if human:
        value = "human"
    if value not in {"json", "human"}:
        raise typer.BadParameter("format must be json|human")
    return value


def emit_payload(
    payload: dict[str, Any],
    *,
    output_format: str,
    human_renderer: Callable[[dict[str, Any]], str],
) -> None:
    if output_format == "json":
        typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        typer.echo(human_renderer(payload))

    if payload.get("status") == "failed":
        raise typer.Exit(code=1)
