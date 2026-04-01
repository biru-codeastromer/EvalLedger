from __future__ import annotations

import typer

from evalledger.commands.check import check_command
from evalledger.commands.info import cite_command, info_command
from evalledger.commands.login import login_command
from evalledger.commands.search import search_command
from evalledger.commands.submit import submit_command
from evalledger.commands.verify import verify_command

app = typer.Typer(help="EvalLedger command-line client")

app.command("login")(login_command)
app.command("submit")(submit_command)
app.command("check")(check_command)
app.command("verify")(verify_command)
app.command("search")(search_command)
app.command("info")(info_command)
app.command("cite")(cite_command)


if __name__ == "__main__":
    app()

