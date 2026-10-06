"""Pull worker (Pattern B): claim a queued job, grade it, write the inference cache.

The worker role has no grant on study/result. It never sets app.facility_id. Two workers
claiming at once cannot grade the same image because the claim uses FOR UPDATE SKIP LOCKED.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from service.cache import _store_artefacts
from service.engine import Engine, EngineUnavailable, build_engine
from service.schemas import EngineResult
from service.settings import Settings, load_settings
from service.storage import S3Storage, Storage

log = logging.getLogger("netrasetu.worker")

CLAIM = """
UPDATE clinical.job SET
    status = 'running',
    claimed_at = now(),
    worker = %(w)s,
    updated_at = now(),
    attempts = attempts + 1
WHERE id = (
    SELECT id FROM clinical.job
    WHERE status = 'queued'
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING id, object_key, img_sha256, model_ver, cfg_hash, filename, content_type
"""

REAP = """
UPDATE clinical.job
   SET status = 'queued', worker = NULL, claimed_at = NULL, updated_at = now()
 WHERE status = 'running'
   AND claimed_at < now() - interval '10 minutes'
"""


def connect(url: str) -> psycopg.Connection[dict]:
    return psycopg.connect(url, autocommit=True, row_factory=dict_row)


def reap(conn: psycopg.Connection) -> int:
    result = conn.execute(REAP)
    return result.rowcount or 0


def claim(conn: psycopg.Connection, worker_id: str) -> dict[str, Any] | None:
    return conn.execute(CLAIM, {"w": worker_id}).fetchone()


def fail(conn: psycopg.Connection, job_id: UUID, message: str) -> None:
    conn.execute(
        """UPDATE clinical.job
              SET status = 'failed', error = %s, updated_at = now()
            WHERE id = %s""",
        (message[:500], job_id),
    )


def complete(conn: psycopg.Connection, job_id: UUID) -> None:
    conn.execute(
        """UPDATE clinical.job
              SET status = 'done', error = NULL, updated_at = now()
            WHERE id = %s""",
        (job_id,),
    )


def process_job(
    conn: psycopg.Connection,
    job: dict[str, Any],
    engine: Engine,
    storage: Storage,
    work_dir: Path,
) -> None:
    job_id: UUID = job["id"]
    work_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work_dir, prefix="job-") as tmp:
        work = Path(tmp)
        name = job["filename"] or "in.png"
        src = work / Path(name).name
        src.write_bytes(storage.get(job["object_key"]))
        out_dir = work / "out"
        try:
            txt = engine.analyze_json(src, out_dir)
            result = EngineResult.model_validate_json(txt)
        except (EngineUnavailable, ValidationError) as exc:
            fail(conn, job_id, str(exc))
            return
        sha_hex = bytes(job["img_sha256"]).hex() if job["img_sha256"] is not None else src.stem
        payload = _store_artefacts(storage, result, out_dir, sha_hex)
        conn.execute(
            """INSERT INTO clinical.inference_cache
                   (img_sha256, model_ver, cfg_hash, payload)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (img_sha256, model_ver, cfg_hash)
               DO UPDATE SET payload = EXCLUDED.payload""",
            (job["img_sha256"], payload["modelVer"], payload["cfgHash"], Jsonb(payload)),
        )
        complete(conn, job_id)


def tick(
    conn: psycopg.Connection,
    worker_id: str,
    engine: Engine,
    storage: Storage,
    work_dir: Path,
) -> bool:
    """Reap stale claims, then try to process one job. Returns True if a job was claimed."""
    reaped = reap(conn)
    if reaped:
        log.info("reaped %s stale job(s)", reaped)
    job = claim(conn, worker_id)
    if job is None:
        return False
    try:
        process_job(conn, job, engine, storage, work_dir)
    except Exception:
        log.exception("job %s failed", job["id"])
        fail(conn, job["id"], "worker crashed while grading")
    return True


def run_forever(settings: Settings, engine: Engine, storage: Storage) -> None:
    worker_id = os.environ.get("WORKER_ID", "").strip() or "worker"
    log.info("worker %s pulling jobs", worker_id)
    while True:
        with connect(settings.database_url) as conn:
            did = tick(conn, worker_id, engine, storage, settings.work_dir)
        if not did:
            time.sleep(2)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = load_settings()
    engine = build_engine(settings)
    storage = S3Storage(settings.s3, settings.presign_ttl_seconds)
    run_forever(settings, engine, storage)


if __name__ == "__main__":
    main()
