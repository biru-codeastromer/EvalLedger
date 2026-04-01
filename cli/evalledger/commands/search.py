from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from evalledger.client import EvalLedgerClient, EvalLedgerClientError
from evalledger.config import load_config

console = Console()
error_console = Console(stderr=True)


def search_command(query: str) -> None:
    client = EvalLedgerClient(load_config())
    try:
        payload = client.search(query)
        table = Table(title="EvalLedger Search")
        table.add_column("Benchmark")
        table.add_column("Slug")
        table.add_column("Latest")
        table.add_column("Status")
        for item in payload["items"]:
            table.add_row(
                item["name"],
                item["slug"],
                item.get("latest_version") or "—",
                item.get("latest_contamination_status") or "—",
            )
        console.print(table)
    except EvalLedgerClientError as exc:
        error_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    finally:
        client.close()

