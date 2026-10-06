"""Pattern B worker: SKIP LOCKED uniqueness, the ten-minute reaper, failure recording,
and the queue-mode round trip (503 → worker writes the cache → retry 200)."""

from __future__ import annotations

import hashlib
import threading
import uuid
from pathlib import Path

import psycopg
import pytest

from service.engine import EngineUnavailable, cfg_hash
from service.storage import MemoryStorage
from service.tests.conftest import THRESHOLD, GatewayFactory, Mint, unique_png
from service.tests.test_gateway import _analyze, _patient
from service.worker import claim, connect, process_job, reap, tick


@pytest.fixture
def facility() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def screener(mint: Mint, facility: uuid.UUID) -> dict[str, str]:
    return mint("screener", facility)


def _insert_queued(admin_db: psycopg.Connection, n: int = 1) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    for _ in range(n):
        row = admin_db.execute(
            """INSERT INTO clinical.job (facility_id, object_key, status)
               VALUES (%s, %s, 'queued') RETURNING id""",
            (uuid.uuid4(), f"inbox/{uuid.uuid4()}"),
        ).fetchone()
        ids.append(row["id"])
    return ids


def test_two_workers_never_claim_the_same_job(
    admin_db: psycopg.Connection, worker_url: str
) -> None:
    admin_db.execute(
        "UPDATE clinical.job SET status = 'done' WHERE status IN ('queued', 'running')"
    )
    ids = _insert_queued(admin_db, 16)
    barrier = threading.Barrier(2)
    claimed: list[uuid.UUID] = []
    lock = threading.Lock()

    def drain(worker_id: str) -> None:
        with connect(worker_url) as conn:
            barrier.wait()
            while True:
                job = claim(conn, worker_id)
                if job is None:
                    return
                with lock:
                    claimed.append(job["id"])

    threads = [
        threading.Thread(target=drain, args=("w1",)),
        threading.Thread(target=drain, args=("w2",)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(claimed) == len(set(claimed)) == len(ids)
    assert set(claimed) == set(ids)


def test_reaper_returns_stale_running_jobs_to_the_queue(
    admin_db: psycopg.Connection, worker_url: str
) -> None:
    stale = admin_db.execute(
        """INSERT INTO clinical.job (facility_id, object_key, status, worker, claimed_at)
           VALUES (%s, %s, 'running', 'dead', now() - interval '11 minutes')
           RETURNING id""",
        (uuid.uuid4(), f"inbox/{uuid.uuid4()}"),
    ).fetchone()["id"]
    fresh = admin_db.execute(
        """INSERT INTO clinical.job (facility_id, object_key, status, worker, claimed_at)
           VALUES (%s, %s, 'running', 'live', now() - interval '2 minutes')
           RETURNING id""",
        (uuid.uuid4(), f"inbox/{uuid.uuid4()}"),
    ).fetchone()["id"]
    with connect(worker_url) as conn:
        assert reap(conn) >= 1
    reset = admin_db.execute(
        "SELECT status, worker, claimed_at FROM clinical.job WHERE id = %s", (stale,)
    ).fetchone()
    assert reset["status"] == "queued" and reset["worker"] is None and reset["claimed_at"] is None
    still = admin_db.execute(
        "SELECT status, worker FROM clinical.job WHERE id = %s", (fresh,)
    ).fetchone()
    assert still == {"status": "running", "worker": "live"}


def test_engine_failure_is_recorded_and_does_not_write_the_cache(
    admin_db: psycopg.Connection, worker_url: str, tmp_path: Path
) -> None:
    admin_db.execute("UPDATE clinical.job SET status = 'done' WHERE status = 'queued'")
    storage = MemoryStorage()
    image = unique_png()
    job_id = uuid.uuid4()
    key = f"inbox/{job_id}.png"
    storage.put(key, image, "image/png")
    admin_db.execute(
        """INSERT INTO clinical.job
               (id, facility_id, object_key, status, img_sha256, model_ver, cfg_hash, filename)
           VALUES (%s, %s, %s, 'queued', %s, %s, %s, 'grade2_haem.png')""",
        (
            job_id,
            uuid.uuid4(),
            key,
            hashlib.sha256(image).digest(),
            "netrasetu_v1",
            cfg_hash(THRESHOLD),
        ),
    )

    class Boom:
        name = "boom"

        def ready(self) -> bool:
            return False

        def version(self):  # pragma: no cover - unused on this path
            raise EngineUnavailable("down")

        def analyze_json(self, img_path: Path, out_dir: Path) -> str:
            raise EngineUnavailable("grading node down")

    with connect(worker_url) as conn:
        job = claim(conn, "w-fail")
        assert job is not None and job["id"] == job_id
        process_job(conn, job, Boom(), storage, tmp_path / "work")  # type: ignore[arg-type]
    row = admin_db.execute(
        "SELECT status, error FROM clinical.job WHERE id = %s", (job_id,)
    ).fetchone()
    assert row["status"] == "failed"
    assert "grading node down" in row["error"]
    assert (
        admin_db.execute(
            "SELECT 1 FROM clinical.inference_cache WHERE img_sha256 = %s",
            (hashlib.sha256(image).digest(),),
        ).fetchone()
        is None
    )


def test_queue_mode_returns_503_until_the_worker_fills_the_cache(
    gateway_factory: GatewayFactory,
    screener: dict[str, str],
    worker_url: str,
    tmp_path: Path,
) -> None:
    gw = gateway_factory(gateway_mode="queue")
    patient = _patient(gw, screener)
    image = unique_png()
    key = uuid.uuid4()
    first = _analyze(gw, screener, patient, image, "grade2_haem", key=key)
    assert first.status_code == 503
    assert first.json() == {"status": "queued", "reason": "grading node unavailable"}
    pending = _analyze(gw, screener, patient, image, "grade2_haem", key=key)
    assert pending.status_code == 503
    assert gw.engine.calls == 0
    assert any(k.startswith("inbox/") for k in gw.storage.objects)

    with connect(worker_url) as conn:
        assert tick(conn, "laptop", gw.engine, gw.storage, tmp_path / "worker")
    assert gw.engine.calls == 1

    retry = _analyze(gw, screener, patient, image, "grade2_haem", key=key)
    assert retry.status_code == 200, retry.text
    body = retry.json()
    assert body["source"] == "cache" and body["decision"] == "REFER"
    assert gw.engine.calls == 1


def test_worker_role_cannot_insert_jobs_or_studies(worker_url: str) -> None:
    fid = uuid.uuid4()
    with connect(worker_url) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                """INSERT INTO clinical.job (facility_id, object_key, status)
                   VALUES (%s, %s, 'queued')""",
                (fid, f"inbox/{uuid.uuid4()}"),
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO clinical.study (patient_id, facility_id) VALUES (%s, %s)",
                (uuid.uuid4(), fid),
            )
