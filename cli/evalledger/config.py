from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

import tomli_w

CONFIG_DIR = Path.home() / ".evalledger"
CONFIG_PATH = CONFIG_DIR / "config.toml"


@dataclass(slots=True)
class CLIConfig:
    endpoint: str = "http://localhost:8000"
    api_key: str | None = None
    access_token: str | None = None
    email: str | None = None


def load_config() -> CLIConfig:
    if not CONFIG_PATH.exists():
        return CLIConfig()
    with CONFIG_PATH.open("rb") as handle:
        payload = tomllib.load(handle)
    return CLIConfig(**payload)


def save_config(config: CLIConfig) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("wb") as handle:
        tomli_w.dump(asdict(config), handle)

