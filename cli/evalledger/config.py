from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

import tomli_w

CONFIG_DIR = Path.home() / ".evalledger"
CONFIG_PATH = CONFIG_DIR / "config.toml"


@dataclass(slots=True)
class CLIConfig:
    endpoint: str = "http://localhost:8000"
    api_key: str | None = None


def load_config() -> CLIConfig:
    if not CONFIG_PATH.exists():
        return CLIConfig()
    with CONFIG_PATH.open("rb") as handle:
        payload = tomllib.load(handle)
    # Filter to only known fields so old configs with email/access_token don't crash.
    known = {f.name for f in fields(CLIConfig)}
    return CLIConfig(**{k: v for k, v in payload.items() if k in known})


def save_config(config: CLIConfig) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {k: v for k, v in {"endpoint": config.endpoint, "api_key": config.api_key}.items() if v is not None}
    with CONFIG_PATH.open("wb") as handle:
        tomli_w.dump(data, handle)
