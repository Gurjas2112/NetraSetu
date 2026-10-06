"""Seed 30 days of synthetic programme data across four facilities for Grafana and Admin.

Every inserted study carries payload.seedDemo = true. Re-run with --force to replace that data.
Uses ADMIN_DATABASE_URL (never the gateway or worker roles).

Usage: python scripts/seed_demo.py [--force]
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from random import Random

import psycopg
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
THRESHOLD = ROOT / "matlab" / "config" / "threshold.json"
CONTRACT = "1.1"
MODEL_VER = "netrasetu_v1"
NOTICE = hashlib.sha256(b"screening notice v1").hexdigest()

FACILITIES: tuple[tuple[uuid.UUID, str], ...] = (
    (uuid.UUID("10000000-0000-4000-8000-000000000001"), "ambegaon-phc"),
    (uuid.UUID("10000000-0000-4000-8000-000000000002"), "khed-phc"),
    (uuid.UUID("10000000-0000-4000-8000-000000000003"), "junnar-phc"),
    (uuid.UUID("10000000-0000-4000-8000-000000000004"), "manchar-phc"),
)

DAYS = 30
SCREENINGS_PER_DAY = 10
SEED = 26038


def cfg_hash() -> str:
    return "sha256:" + hashlib.sha256(THRESHOLD.read_bytes()).hexdigest()


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.is_file():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _posterior(grade: int) -> list[float]:
    if grade == 0:
        return [0.90, 0.07, 0.02, 0.007, 0.003]
    if grade == 2:
        return [0.02, 0.07, 0.61, 0.24, 0.06]
    return [0.01, 0.02, 0.07, 0.20, 0.70]


def _payload(*, decision: str, grade: int | None, review: bool, retake_key: str | None) -> dict:
    quality = (
        {"verdict": "reject", "score": 0.2, "failureMode": "defocus", "phash": "0000000000000000"}
        if decision == "RETAKE"
        else {"verdict": "accept", "score": 0.9, "failureMode": "none", "phash": "0000000000000000"}
    )
    posterior = None if grade is None else _posterior(grade)
    p_ref = None if posterior is None else posterior[2] + posterior[3] + posterior[4]
    return {
        "contractVersion": CONTRACT,
        "modelVer": MODEL_VER,
        "cfgHash": cfg_hash(),
        "decision": decision,
        "reviewRequired": review,
        "quality": quality,
        "retakeGuidanceKey": retake_key,
        "grade": grade,
        "posterior": posterior,
        "pReferable": p_ref,
        "laterality": "unknown",
        "criteria": [],
        "evidence": [],
        "gradcamPath": None,
        "llp": None,
        "reportPath": None,
        "fhirBundle": {"resourceType": "Bundle", "type": "collection", "entry": []},
        "seedDemo": True,
    }


def _clear_synthetic(conn: psycopg.Connection) -> None:
    rows = conn.execute(
        """SELECT r.study_id, s.patient_id
             FROM clinical.result AS r
             JOIN clinical.study AS s ON s.id = r.study_id
            WHERE r.payload->>'seedDemo' = 'true'"""
    ).fetchall()
    if not rows:
        return
    study_ids = [row[0] for row in rows]
    patient_ids = list({row[1] for row in rows})
    conn.execute(
        "DELETE FROM clinical.review WHERE study_id = ANY(%s::uuid[])",
        (study_ids,),
    )
    conn.execute(
        "DELETE FROM clinical.fhir_bundle WHERE study_id = ANY(%s::uuid[])",
        (study_ids,),
    )
    conn.execute("DELETE FROM clinical.result WHERE study_id = ANY(%s::uuid[])", (study_ids,))
    conn.execute("DELETE FROM clinical.study WHERE id = ANY(%s::uuid[])", (study_ids,))
    conn.execute(
        """DELETE FROM clinical.consent AS c
            WHERE c.patient_id = ANY(%s::uuid[])
              AND NOT EXISTS (
                  SELECT 1 FROM clinical.study AS s WHERE s.patient_id = c.patient_id
              )""",
        (patient_ids,),
    )
    conn.execute(
        """DELETE FROM clinical.patient AS p
            WHERE p.id = ANY(%s::uuid[])
              AND NOT EXISTS (SELECT 1 FROM clinical.study AS s WHERE s.patient_id = p.id)""",
        (patient_ids,),
    )


def _has_synthetic(conn: psycopg.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM clinical.result WHERE payload->>'seedDemo' = 'true' LIMIT 1"
    ).fetchone()
    return row is not None


def seed(conn: psycopg.Connection, *, force: bool = False) -> int:
    if _has_synthetic(conn) and not force:
        print("seed_demo: synthetic programme data already present (use --force to replace)")
        return 0
    if force:
        _clear_synthetic(conn)

    rng = Random(SEED)
    cfg = cfg_hash()
    created = 0
    anchor = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)

    for day in range(DAYS):
        day_start = anchor - timedelta(days=DAYS - day)
        for _ in range(SCREENINGS_PER_DAY):
            facility_id, facility_name = FACILITIES[rng.randrange(len(FACILITIES))]
            roll = rng.random()
            if roll < 0.15:
                decision, grade, retake = "RETAKE", None, "retake.defocus.hold_steady"
                review = False
            elif roll < 0.40:
                decision, grade, retake = "REFER", 2 if rng.random() < 0.7 else 4, None
                review = True
            else:
                decision, grade, retake = "ROUTINE", 0, None
                review = False

            patient_id = uuid.uuid4()
            consent_id = uuid.uuid4()
            study_id = uuid.uuid4()
            client_key = uuid.uuid4()
            offset_min = rng.randint(0, 23 * 60 + 59)
            screened_at = day_start + timedelta(minutes=offset_min)
            sha = hashlib.sha256(f"{facility_id}:{study_id}".encode()).digest()
            payload = _payload(decision=decision, grade=grade, review=review, retake_key=retake)

            conn.execute(
                """INSERT INTO clinical.patient (id, facility_id) VALUES (%s, %s)""",
                (patient_id, facility_id),
            )
            conn.execute(
                """INSERT INTO clinical.consent
                       (id, patient_id, facility_id, purpose, notice_hash, language, granted_at)
                   VALUES (%s, %s, %s, 'screening', %s, 'hi', %s)""",
                (consent_id, patient_id, facility_id, bytes.fromhex(NOTICE), screened_at),
            )
            conn.execute(
                """INSERT INTO clinical.study
                       (id, patient_id, facility_id, sha256, phash, client_key, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    study_id,
                    patient_id,
                    facility_id,
                    sha,
                    bytes.fromhex(payload["quality"]["phash"]),
                    client_key,
                    screened_at,
                ),
            )
            conn.execute(
                """INSERT INTO clinical.result
                       (study_id, facility_id, grade, posterior, p_referable, model_ver,
                        decision, source, payload, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'matlab', %s, %s)""",
                (
                    study_id,
                    facility_id,
                    grade,
                    payload["posterior"],
                    payload["pReferable"],
                    MODEL_VER,
                    decision,
                    Jsonb(payload),
                    screened_at,
                ),
            )
            conn.execute(
                """INSERT INTO clinical.fhir_bundle (study_id, facility_id, bundle, created_at)
                   VALUES (%s, %s, %s, %s)""",
                (study_id, facility_id, Jsonb(payload["fhirBundle"]), screened_at),
            )
            conn.execute(
                """INSERT INTO clinical.audit
                       (actor, action, entity, entity_id, facility_id, payload, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    "seed_demo",
                    "study.create",
                    "study",
                    study_id,
                    facility_id,
                    Jsonb(
                        {
                            "source": "matlab",
                            "synthetic": True,
                            "seedDemo": True,
                            "facilityName": facility_name,
                        }
                    ),
                    screened_at,
                ),
            )
            if review and rng.random() < 0.55:
                conn.execute(
                    """INSERT INTO clinical.review
                           (study_id, facility_id, grader_hpr, decision, grade,
                            elapsed_ms, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        study_id,
                        facility_id,
                        "demo-grader-hpr",
                        decision,
                        grade,
                        rng.randint(12_000, 28_000),
                        screened_at + timedelta(minutes=rng.randint(30, 240)),
                    ),
                )
            created += 1

    conn.execute(
        """INSERT INTO clinical.audit (actor, action, entity, facility_id, payload)
           VALUES ('seed_demo', 'programme.seed_complete', 'programme', NULL, %s)""",
        (
            Jsonb(
                {
                    "synthetic": True,
                    "days": DAYS,
                    "studies": created,
                    "facilities": [name for _, name in FACILITIES],
                    "cfgHash": cfg,
                }
            ),
        ),
    )
    return created


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing synthetic programme data",
    )
    args = parser.parse_args(argv)
    url = os.environ.get("ADMIN_DATABASE_URL")
    if not url:
        print("ADMIN_DATABASE_URL is not set; run scripts/dev_platform.py first", file=sys.stderr)
        return 1
    if not THRESHOLD.is_file():
        print("matlab/config/threshold.json is missing", file=sys.stderr)
        return 1

    with psycopg.connect(url, autocommit=True) as conn:
        n = seed(conn, force=args.force)
    if n:
        print(
            f"seed_demo: inserted {n} synthetic studies across "
            f"{len(FACILITIES)} facilities ({DAYS} days)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
