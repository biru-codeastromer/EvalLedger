from __future__ import annotations

import typer
from rich.console import Console
from rich.prompt import Prompt

from evalledger.client import EvalLedgerClient, EvalLedgerClientError
from evalledger.config import CLIConfig, save_config

console = Console()
error_console = Console(stderr=True)


def login_command(
    endpoint: str = typer.Option("http://localhost:8000", help="EvalLedger API endpoint"),
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
) -> None:
    client = EvalLedgerClient(CLIConfig(endpoint=endpoint))
    try:
        login_payload = client.login(email, password)
        token = login_payload["access_token"]
        key_client = EvalLedgerClient(CLIConfig(endpoint=endpoint, access_token=token))
        key_name = Prompt.ask("API key name", default="evalledger-cli")
        key_payload = key_client.create_api_key(key_name)
        config = CLIConfig(
            endpoint=endpoint,
            email=email,
            access_token=token,
            api_key=key_payload["api_key"],
        )
        save_config(config)
        console.print("[#b5813a]Saved EvalLedger credentials to ~/.evalledger/config.toml[/#b5813a]")
    except EvalLedgerClientError as exc:
        error_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    finally:
        client.close()

