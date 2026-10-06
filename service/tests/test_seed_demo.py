"""Synthetic programme seed for Admin / Grafana demos."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]


def test_seed_demo_inserts_thirty_days_across_four_facilities(admin_url: str) -> None:
    run = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seed_demo.py"), "--force"],
        cwd=ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr + run.stdout

    with psycopg.connect(admin_url, row_factory=dict_row) as conn:
        facilities = conn.execute(
            """SELECT DISTINCT facility_id FROM clinical.result
               WHERE payload->>'seedDemo' = 'true'"""
        ).fetchall()
        assert len(facilities) == 4

        span = conn.execute(
            """SELECT min(s.created_at) AS lo, max(s.created_at) AS hi
               FROM clinical.study AS s
               JOIN clinical.result AS r ON r.study_id = s.id
               WHERE r.payload->>'seedDemo' = 'true'"""
        ).fetchone()
        assert span["lo"] is not None
        assert (span["hi"] - span["lo"]).days >= 29

        audit = conn.execute(
            """SELECT payload FROM clinical.audit
               WHERE action = 'programme.seed_complete'
               ORDER BY seq DESC LIMIT 1"""
        ).fetchone()
        assert audit is not None
        assert audit["payload"]["synthetic"] is True

        expected = {
            uuid.UUID("10000000-0000-4000-8000-000000000001"),
            uuid.UUID("10000000-0000-4000-8000-000000000002"),
            uuid.UUID("10000000-0000-4000-8000-000000000003"),
            uuid.UUID("10000000-0000-4000-8000-000000000004"),
        }
        assert {row["facility_id"] for row in facilities} == expected
