from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel

from evalledger.client import EvalLedgerClient, EvalLedgerClientError
from evalledger.config import load_config

console = Console()
error_console = Console(stderr=True)


def info_command(slug: str, version: str | None = None) -> None:
    client = EvalLedgerClient(load_config())
    try:
        if version:
            payload = client.get_version(slug, version)
            console.print(
                Panel.fit(
                    "\n".join(
                        [
                            f"[bold]{payload['version']}[/bold]",
                            f"SHA-256: {payload.get('artifact_sha256') or 'unavailable'}",
                            f"Contamination: {payload['contamination_status']}",
                            f"Canonical ID: {payload['citations']['evalledger_id']}",
                        ]
                    ),
                    title=slug,
                )
            )
        else:
            payload = client.get_benchmark(slug)
            console.print(
                Panel.fit(
                    "\n".join(
                        [
                            f"[bold]{payload['name']}[/bold]",
                            payload.get("description") or "",
                            f"Task type: {payload.get('task_type') or 'unknown'}",
                            f"Versions: {payload['total_versions']}",
                        ]
                    ),
                    title=payload["slug"],
                )
            )
    except EvalLedgerClientError as exc:
        error_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    finally:
        client.close()


def cite_command(
    slug: str,
    version: str,
    format: str = typer.Option("bibtex", "--format", help="bibtex|apa|mla|cff"),
) -> None:
    client = EvalLedgerClient(load_config())
    try:
        console.print(client.get_citation(slug, version, format))
    except EvalLedgerClientError as exc:
        error_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    finally:
        client.close()

