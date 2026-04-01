from __future__ import annotations

import typer
from rich.console import Console

from evalledger.client import EvalLedgerClient, EvalLedgerClientError
from evalledger.config import load_config

console = Console()
error_console = Console(stderr=True)


def verify_command(slug: str, version: str) -> None:
    client = EvalLedgerClient(load_config())
    try:
        payload = client.get_version(slug, version)
        if payload.get("artifact_sha256"):
            console.print(f"[#b5813a]✓ VERIFIED[/#b5813a] {payload['artifact_sha256']}")
        else:
            console.print("[yellow]Legacy record present, but no pinned artifact hash is available yet.[/yellow]")
    except EvalLedgerClientError as exc:
        error_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    finally:
        client.close()

