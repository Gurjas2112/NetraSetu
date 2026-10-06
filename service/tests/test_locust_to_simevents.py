"""Locust CSV → SimEvents params copies percentiles; it does not invent them."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_params_from_csv_use_analyze_row_and_convert_ms_to_seconds(tmp_path: Path) -> None:
    csv_path = tmp_path / "load_stats.csv"
    header = ",".join(
        [
            "Type",
            "Name",
            "Request Count",
            "Failure Count",
            "Median Response Time",
            "Average Response Time",
            "Min Response Time",
            "Max Response Time",
            "Average Content Size",
            "Requests/s",
            "Failures/s",
            "50%",
            "66%",
            "75%",
            "80%",
            "90%",
            "95%",
            "98%",
            "99%",
            "99.9%",
            "99.99%",
            "100%",
        ]
    )
    csv_path.write_text(
        "\n".join(
            [
                header,
                "POST,/consent,4,0,20,20,10,30,100,0.1,0.0,20,20,20,20,20,25,25,25,30,30,30",
                "POST,/analyze,8,0,1000,1100,800,2000,200,0.2,0.0,"
                "1000,1100,1200,1300,1500,2000,2100,2200,2300,2400,2500",
                "None,Aggregated,12,0,500,600,10,2500,150,0.3,0.0,"
                "500,600,700,800,900,1500,1800,1900,2000,2400,2500",
                "",
            ]
        ),
        encoding="utf-8",
    )
    mod = _load("locust_to_simevents", ROOT / "scripts" / "locust_to_simevents.py")
    params = mod.params_from_csv(csv_path)
    assert params["name"] == "/analyze"
    assert params["requestCount"] == 8
    assert params["failureCount"] == 0
    times = params["inferenceServiceTimeSeconds"]
    assert times["p50"] == 1.0
    assert times["p95"] == 2.0


def test_resolve_csv_accepts_locust_prefix(tmp_path: Path) -> None:
    stats = tmp_path / "load_stats.csv"
    stats.write_text("Type,Name\n", encoding="utf-8")
    mod = _load("locust_to_simevents", ROOT / "scripts" / "locust_to_simevents.py")
    assert mod.resolve_csv(tmp_path / "load") == stats


def test_unique_png_changes_the_digest() -> None:
    images = _load("load_images", ROOT / "tests" / "load" / "images.py")
    fixture = ROOT / "tests" / "fixtures" / "grade2_haem.png"
    assert fixture.is_file()
    base = fixture.read_bytes()
    a = images.unique_png(base, 0)
    b = images.unique_png(base, 1)
    assert hashlib.sha256(a).digest() != hashlib.sha256(base).digest()
    assert hashlib.sha256(a).digest() != hashlib.sha256(b).digest()
