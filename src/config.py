"""Shared municipality configuration loading."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path("configs/municipalities/witzenhausen.json")
CONFIG_ENV_VAR = "KOMMUNALPOLITIK_CONFIG"


@dataclass(frozen=True)
class MunicipalityConfig:
    id: str
    name: str
    adapter: str
    base_url: str
    data_dir: Path
    database_path: Path


def default_config_path() -> Path:
    return Path(os.environ.get(CONFIG_ENV_VAR, DEFAULT_CONFIG_PATH))


def load_municipality_config(path: str | Path | None = None) -> MunicipalityConfig:
    config_path = Path(path) if path else default_config_path()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    _require_keys(payload, config_path)
    data_dir = Path(payload["data_dir"])
    database_path = Path(payload.get("database_path") or data_dir / f"{payload['id']}.sqlite")
    return MunicipalityConfig(
        id=payload["id"],
        name=payload["name"],
        adapter=payload["adapter"],
        base_url=payload["base_url"],
        data_dir=data_dir,
        database_path=database_path,
    )


def _require_keys(payload: dict[str, Any], config_path: Path) -> None:
    required = ["id", "name", "adapter", "base_url", "data_dir"]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        keys = ", ".join(missing)
        raise ValueError(f"Municipality config {config_path} is missing required keys: {keys}")
