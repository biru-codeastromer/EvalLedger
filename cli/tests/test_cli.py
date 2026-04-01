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


def test_login_command_saves_credentials(monkeypatch) -> None:
    saved = {}

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def login(self, _email: str, _password: str):
            return {"access_token": "token-123"}

        def create_api_key(self, _name: str):
            return {"api_key": "el_key_123"}

        def close(self) -> None:
            return None

    monkeypatch.setattr("evalledger.commands.login.EvalLedgerClient", FakeClient)
    monkeypatch.setattr("evalledger.commands.login.Prompt.ask", lambda *_args, **_kwargs: "evalledger-cli")
    monkeypatch.setattr(
        "evalledger.commands.login.save_config",
        lambda config: saved.update(
            {
                "endpoint": config.endpoint,
                "email": config.email,
                "access_token": config.access_token,
                "api_key": config.api_key,
            }
        ),
    )

    result = runner.invoke(
        app,
        ["login", "--email", "researcher@example.com", "--password", "password123"],
    )

    assert result.exit_code == 0
    assert saved["email"] == "researcher@example.com"
    assert saved["api_key"] == "el_key_123"
