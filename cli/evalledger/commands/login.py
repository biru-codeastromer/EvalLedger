"""Configure the CLI with an API key from your EvalLedger account.

Auth flow:
  1. Sign in at https://evalledger-frontend.vercel.app/login using GitHub or Google.
  2. Go to your account page (/account) and create an API key.
  3. Run:  evalledger login --api-key <your-key>

The key is validated against the API, then stored in ~/.evalledger/config.toml.
"""

from __future__ import annotations

import typer
from rich.console import Console

from evalledger.client import EvalLedgerClient, EvalLedgerClientError
from evalledger.config import CLIConfig, save_config

console = Console()
error_console = Console(stderr=True)

_ACCOUNT_URL = "https://evalledger-frontend.vercel.app/account"
_LOGIN_URL = "https://evalledger-frontend.vercel.app/login"


def login_command(
    endpoint: str = typer.Option(
        "https://evalledger-api.onrender.com",
        help="EvalLedger API endpoint (override for local dev: http://localhost:8000)",
    ),
    api_key: str = typer.Option(
        ...,
        prompt=f"Paste your API key (create one at {_ACCOUNT_URL})",
        hide_input=True,
        help="API key created from your EvalLedger account page",
    ),
) -> None:
    """Authenticate the CLI using an API key from your EvalLedger account.

    Sign in at the web app with GitHub or Google, create an API key on your
    account page, then paste it here. Credentials are stored in
    ~/.evalledger/config.toml.
    """
    if not api_key.startswith("el_"):
        error_console.print(
            "[red]That does not look like a valid EvalLedger API key "
            "(expected it to start with 'el_'). "
            f"Create one at {_ACCOUNT_URL}[/red]"
        )
        raise typer.Exit(code=1)

    client = EvalLedgerClient(CLIConfig(endpoint=endpoint, api_key=api_key))
    try:
        me = client.whoami()
        user = me.get("user", {})
        username = user.get("username", "unknown")
        email = user.get("email", "")
        config = CLIConfig(endpoint=endpoint, api_key=api_key)
        save_config(config)
        console.print(f"[#b5813a]Authenticated as {username}[/#b5813a] ({email})")
        console.print("[#b5813a]Credentials saved to ~/.evalledger/config.toml[/#b5813a]")
    except EvalLedgerClientError as exc:
        error_console.print(f"[red]API key validation failed: {exc}[/red]")
        error_console.print(f"[dim]Sign in at {_LOGIN_URL} to create an account and generate a key.[/dim]")
        raise typer.Exit(code=1) from exc
    finally:
        client.close()
