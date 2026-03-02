"""Version command wiring."""

from __future__ import annotations

from typing import Annotated

import typer

from gfl.cli.commands._common import emit_payload, resolve_output_format
from gfl.core.service import run_version


def _render_human(payload: dict[str, object]) -> str:
    if payload["status"] == "failed":
        error = payload["error"]
        return f"version failed: {error['code']} - {error['message']}"

    row = payload["results"][0]
    return (
        "version success\n"
        f"- cli_version: {row['cli_version']}\n"
        f"- backend: {row['backend']}\n"
        f"- backend_version: {row['backend_version']}"
    )


def register(app: typer.Typer) -> None:
    @app.command("version")
    def version_command(
        output_format: Annotated[str, typer.Option("--format")] = "json",
        human: Annotated[bool, typer.Option("--human")] = False,
    ) -> None:
        payload = run_version()
        emit_payload(
            payload,
            output_format=resolve_output_format(output_format, human),
            human_renderer=_render_human,
        )
