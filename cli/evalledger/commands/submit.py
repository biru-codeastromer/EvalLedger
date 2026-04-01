from __future__ import annotations

import time
from hashlib import sha256
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from evalledger.client import EvalLedgerClient, EvalLedgerClientError
from evalledger.config import load_config

console = Console()
error_console = Console(stderr=True)


def _compute_sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def submit_command(
    name: Annotated[str, typer.Option("--name")],
    slug: Annotated[str, typer.Option("--slug")],
    version: Annotated[str, typer.Option("--version")],
    file: Annotated[Path, typer.Option("--file", exists=True, dir_okay=False)],
    task_type: Annotated[str, typer.Option("--task-type")],
    domain: Annotated[list[str] | None, typer.Option("--domain")] = None,
    description: Annotated[str | None, typer.Option("--description")] = None,
    paper: Annotated[str | None, typer.Option("--paper")] = None,
    license: Annotated[str | None, typer.Option("--license")] = None,
    github: Annotated[str | None, typer.Option("--github")] = None,
) -> None:
    config = load_config()
    client = EvalLedgerClient(config)
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            transient=True,
        ) as progress:
            task = progress.add_task("Hashing artifact...", total=100)
            artifact_sha = _compute_sha(file)
            progress.update(task, advance=100, description="Artifact hashed")

        try:
            client.get_benchmark(slug)
        except EvalLedgerClientError:
            payload = {
                "name": name,
                "slug": slug,
                "description": description or f"{name} benchmark submitted through the EvalLedger CLI.",
                "domain": domain or [],
                "task_type": task_type,
            }
            client.create_benchmark(payload)

        submit_payload = {
            "version": version,
            "license": license or "",
            "paper_url": paper or "",
            "github_url": github or "",
        }
        response = client.submit_version(slug, submit_payload, file)
        console.print(f"[#b5813a]SHA-256:[/#b5813a] {artifact_sha}")
        console.print(
            f"[#b5813a]Registered:[/#b5813a] {response['canonical_id']} "
            f"({config.endpoint.rstrip('/')}/registry/{slug}/{version})"
        )
        if response["contamination_job_ids"]:
            job_id = response["contamination_job_ids"][0]
            console.print(f"[#b5813a]Contamination check queued[/#b5813a] (job: {job_id})")
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
                task = progress.add_task("Waiting for contamination job...", total=None)
                while True:
                    status = client.get_job(job_id)
                    if status["status"] == "completed":
                        progress.update(task, description="Contamination check completed")
                        break
                    if status["status"] == "failed":
                        raise EvalLedgerClientError(status.get("error") or "Contamination job failed")
                    time.sleep(1)
    except EvalLedgerClientError as exc:
        error_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    finally:
        client.close()
