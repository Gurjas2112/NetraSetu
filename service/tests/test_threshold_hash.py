"""Hash of matlab/config/threshold.json, matching nx_config.m."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "check_threshold_hash", ROOT / "eval" / "check_threshold_hash.py"
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_hash_is_stable() -> None:
    a = mod.cfg_hash()
    b = mod.cfg_hash()
    assert a == b
    assert a.startswith("sha256:")
    assert len(a) == len("sha256:") + 64


def test_hash_changes_when_bytes_change(tmp_path: Path) -> None:
    src = (ROOT / "matlab" / "config" / "threshold.json").read_bytes()
    other = tmp_path / "threshold.json"
    other.write_bytes(src + b"\n")
    assert mod.cfg_hash(other) != mod.cfg_hash()


def test_main_exits_zero_without_validation_json(capsys) -> None:
    assert not mod.VALIDATION.is_file()
    assert mod.main() == 0
    assert "sha256:" in capsys.readouterr().out
