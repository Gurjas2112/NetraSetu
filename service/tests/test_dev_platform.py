"""scripts/dev_platform.py completes a .env without changing values that are already set."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import dev_platform


def test_ensure_env_fills_gaps_and_is_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    env = tmp_path / ".env"
    env.write_text("POSTGRES_PASSWORD=keep-me\nOIDC_ISSUER=\n", encoding="utf-8")
    monkeypatch.setattr(dev_platform, "ENV", env)

    first = dev_platform.ensure_env()
    assert first["POSTGRES_PASSWORD"] == "keep-me"
    assert first["OIDC_ISSUER"] == dev_platform.DEFAULTS["OIDC_ISSUER"]
    for key in set(dev_platform.SECRETS) - {"POSTGRES_PASSWORD"}:
        assert len(first[key]) >= 32, key
    assert first["DATABASE_URL"].startswith("postgresql://gateway:")
    assert ":keep-me@" in first["ADMIN_DATABASE_URL"]
    assert first["PATIENT_TOKEN_SECRET"] not in capsys.readouterr().out

    assert dev_platform.ensure_env() == first
    assert env.read_text(encoding="utf-8").count("OIDC_ISSUER=") == 1
