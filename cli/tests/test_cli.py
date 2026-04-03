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


def test_login_command_saves_api_key(monkeypatch) -> None:
    """login validates the key against /auth/me and saves it to config."""
    saved = {}

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def whoami(self):
            return {"user": {"username": "alice", "email": "alice@example.com"}}

        def close(self) -> None:
            return None

    monkeypatch.setattr("evalledger.commands.login.EvalLedgerClient", FakeClient)
    monkeypatch.setattr(
        "evalledger.commands.login.save_config",
        lambda config: saved.update({"endpoint": config.endpoint, "api_key": config.api_key}),
    )

    result = runner.invoke(app, ["login", "--api-key", "el_test_key_abc123"])

    assert result.exit_code == 0
    assert saved["api_key"] == "el_test_key_abc123"
    assert "alice" in result.stdout


def test_login_command_rejects_bad_key_format(monkeypatch) -> None:
    """login rejects keys that don't start with 'el_' before hitting the network."""
    result = runner.invoke(app, ["login", "--api-key", "not-a-real-key"])
    assert result.exit_code == 1
    assert "el_" in result.output


def test_login_command_handles_invalid_key(monkeypatch) -> None:
    """login shows a helpful error when the API rejects the key."""
    from evalledger.client import EvalLedgerClientError

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def whoami(self):
            raise EvalLedgerClientError("API key is invalid")

        def close(self) -> None:
            return None

    monkeypatch.setattr("evalledger.commands.login.EvalLedgerClient", FakeClient)

    result = runner.invoke(app, ["login", "--api-key", "el_bad_key_000"])

    assert result.exit_code == 1
    assert "validation failed" in result.output.lower()
