from __future__ import annotations

from typer.testing import CliRunner

from evalledger.main import app

runner = CliRunner()


def test_search_command(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def search(self, _query: str):
            return {
                "items": [
                    {
                        "name": "MMLU",
                        "slug": "mmlu",
                        "latest_version": "0.0.0",
                        "latest_contamination_status": "unchecked",
                    }
                ]
            }

        def close(self) -> None:
            return None

    monkeypatch.setattr("evalledger.commands.search.EvalLedgerClient", FakeClient)
    result = runner.invoke(app, ["search", "mmlu"])
    assert result.exit_code == 0
    assert "MMLU" in result.stdout


def test_verify_command(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def get_version(self, _slug: str, _version: str):
            return {"artifact_sha256": "abc123"}

        def close(self) -> None:
            return None

    monkeypatch.setattr("evalledger.commands.verify.EvalLedgerClient", FakeClient)
    result = runner.invoke(app, ["verify", "mmlu", "1.0.0"])
    assert result.exit_code == 0
    assert "VERIFIED" in result.stdout

