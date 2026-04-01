from __future__ import annotations

import time
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from evalledger.client import EvalLedgerClient, EvalLedgerClientError
from evalledger.config import load_config

console = Console()
error_console = Console(stderr=True)


def check_command(file: Path) -> None:
    client = EvalLedgerClient(load_config())
    try:
        job = client.run_check(file)
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            task_id = progress.add_task("Running contamination check...", total=None)
            while True:
                status = client.get_job(job["job_id"])
                if status["status"] == "completed":
                    progress.update(task_id, description="Completed")
                    payload = status["result"]
                    break
                if status["status"] == "failed":
                    raise EvalLedgerClientError(status.get("error") or "Contamination job failed")
                time.sleep(1)
        table = Table(title=f"Contamination results for {file.name}")
        table.add_column("Corpus")
        table.add_column("Status")
        table.add_column("Overlap")
        table.add_column("Flagged")
        for corpus in payload["corpora"]:
            table.add_row(
                corpus["corpus_name"],
                corpus["status"].upper(),
                str(corpus["overlap_score"]),
                str(corpus["num_flagged_examples"]),
            )
        console.print(table)
    except EvalLedgerClientError as exc:
        error_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    finally:
        client.close()

