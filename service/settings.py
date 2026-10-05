"""Gateway configuration read from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[1]

EngineKind = Literal["fake", "matlab"]


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    engine: EngineKind
    matlab_shared_engine: str
    nx_root: Path
    work_dir: Path
    cors_origins: list[str] = field(default_factory=list)
    max_upload_bytes: int = 25 * 1024 * 1024

    @property
    def threshold_path(self) -> Path:
        return self.nx_root / "config" / "threshold.json"


def load_settings() -> Settings:
    engine = _env("GATEWAY_ENGINE", "fake")
    if engine not in ("fake", "matlab"):
        raise ValueError(f"GATEWAY_ENGINE must be 'fake' or 'matlab', got {engine!r}")
    return Settings(
        engine=engine,  # type: ignore[arg-type]
        matlab_shared_engine=_env("MATLAB_SHARED_ENGINE", "netrasetu"),
        nx_root=Path(_env("NX_ROOT", str(REPO_ROOT / "matlab"))),
        work_dir=REPO_ROOT / "results" / "work",
        cors_origins=_csv(_env("CORS_ORIGINS", "http://localhost:5173")),
    )
