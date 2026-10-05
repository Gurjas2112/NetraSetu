"""The gateway role cannot read another facility's rows and cannot bypass RLS."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg
import pytest
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    not os.environ.get("ADMIN_DATABASE_URL"),
    reason="ADMIN_DATABASE_URL is not set",
)


def _role_url(admin_url: str, user: str, password: str) -> str:
    parts = urlsplit(admin_url)
    host = parts.hostname or "localhost"
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, f"{quote(user)}:{quote(password)}@{host}", parts.path, "", ""))


def _migrate() -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "migrate.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_second_migrate_applies_nothing() -> None:
    first = _migrate()
    assert first.returncode == 0, first.stderr
    second = _migrate()
    assert second.returncode == 0, second.stderr
    assert "applied nothing" in second.stdout
    assert "applied 001_schema.sql" not in second.stdout
    assert "applied 040_roles.sql" not in second.stdout


def _facility(admin_url: str) -> uuid.UUID:
    facility = uuid.uuid4()
    with psycopg.connect(admin_url, autocommit=True) as db:
        db.execute("SELECT set_config('app.facility_id', %s, false)", (str(facility),))
        db.execute(
            """
            INSERT INTO clinical.patient (id, facility_id)
            VALUES (%s, %s)
            """,
            (facility, facility),
        )
        db.execute(
            """
            INSERT INTO clinical.study (id, patient_id, facility_id, sha256, client_key)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (facility, facility, facility, uuid.uuid4().bytes, uuid.uuid4()),
        )
    return facility


def test_gateway_cannot_read_another_facility_or_bypass_rls() -> None:
    admin_url = os.environ["ADMIN_DATABASE_URL"]
    gateway_url = _role_url(admin_url, "gateway", os.environ["GATEWAY_DB_PASSWORD"])
    _migrate()
    facility_a = _facility(admin_url)
    facility_b = _facility(admin_url)

    with psycopg.connect(gateway_url) as db:
        db.execute("SELECT set_config('app.facility_id', %s, true)", (str(facility_a),))
        visible = {row[0] for row in db.execute("SELECT id FROM clinical.study")}
        assert facility_a in visible
        assert facility_b not in visible

    with psycopg.connect(admin_url) as db:
        bypass = db.execute(
            "SELECT rolbypassrls FROM pg_roles WHERE rolname = 'gateway'"
        ).fetchone()
        assert bypass is not None and bypass[0] is False

    # SET row_security = off is accepted, but a role without BYPASSRLS still cannot
    # read through it: the query fails instead of returning other facilities' rows.
    with psycopg.connect(gateway_url) as db:
        db.execute("SET row_security = off")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("SELECT id FROM clinical.study")

    with psycopg.connect(gateway_url) as db:
        db.execute("SELECT set_config('app.facility_id', %s, true)", (str(facility_a),))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute(
                """
                INSERT INTO clinical.study (patient_id, facility_id, sha256)
                VALUES (%s, %s, %s)
                """,
                (facility_a, facility_b, uuid.uuid4().bytes),
            )

    # The worker has no grant on clinical.study. PostgreSQL evaluates the policy
    # expression first, so this surfaces as a missing app.facility_id rather than
    # a privilege error. Either way the worker receives no rows.
    worker_url = _role_url(admin_url, "worker", os.environ["WORKER_DB_PASSWORD"])
    with psycopg.connect(worker_url) as db, pytest.raises(psycopg.Error):
        db.execute("SELECT id FROM clinical.study")


def test_audit_chain_is_append_only() -> None:
    admin_url = os.environ["ADMIN_DATABASE_URL"]
    gateway_url = _role_url(admin_url, "gateway", os.environ["GATEWAY_DB_PASSWORD"])
    _migrate()
    facility = uuid.uuid4()
    with psycopg.connect(gateway_url, row_factory=dict_row) as db:
        db.execute("SELECT set_config('app.facility_id', %s, true)", (str(facility),))
        db.execute(
            "INSERT INTO clinical.audit (actor, action, facility_id) VALUES ('s', 'one', %s)",
            (facility,),
        )
        db.execute(
            "INSERT INTO clinical.audit (actor, action, facility_id) VALUES ('s', 'two', %s)",
            (facility,),
        )
        rows = db.execute(
            """
            SELECT seq, prev_hash, hash FROM clinical.audit
            WHERE facility_id = %s ORDER BY seq
            """,
            (facility,),
        ).fetchall()
        assert rows[0]["hash"] and rows[1]["prev_hash"] == rows[0]["hash"]
        assert rows[0]["hash"] != rows[1]["hash"]
        with pytest.raises(psycopg.Error):
            db.execute(
                "UPDATE clinical.audit SET action = 'edited' WHERE seq = %s", (rows[0]["seq"],)
            )
