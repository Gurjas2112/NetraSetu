"""The analyze path, in the order of spec Section 26:

    idempotency -> consent -> cross-patient check -> inference cache -> engine -> new study

The cache stores computation, never decisions about a person: a hit still creates a new study,
and pixels already seen under another patient are routed to a reviewer with no grade shown.
The engine runs outside any database transaction; a concurrent retry with the same
Idempotency-Key loses the unique constraint race and returns the winner's study.
"""

from __future__ import annotations

import hashlib
import logging
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from service import audit
from service.auth import Principal
from service.consent import require_screening_consent
from service.db import Database
from service.engine import Engine, EngineUnavailable
from service.metrics import Metrics
from service.schemas import CONTRACT_VERSION, EngineResult, StudyEvidence, StudyResponse
from service.settings import Settings
from service.storage import Storage

log = logging.getLogger("netrasetu.cache")

SAME_IMAGE = "same_image_other_patient"
_EMPTY_BUNDLE: dict[str, Any] = {"resourceType": "Bundle", "type": "collection", "entry": []}
_EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg"}


class Queued(Exception):
    """NX_CACHED_MODE is on and the image is not in the inference cache."""


@dataclass(frozen=True)
class Services:
    settings: Settings
    db: Database
    engine: Engine
    storage: Storage
    metrics: Metrics


@dataclass(frozen=True)
class AnalyzeInput:
    image: bytes
    filename: str
    content_type: str
    patient_id: UUID
    consent_id: UUID
    client_key: UUID


@dataclass(frozen=True)
class Analyzed:
    response: StudyResponse
    sha_hex: str
    created: bool


def analyze(svc: Services, principal: Principal, inp: AnalyzeInput) -> Analyzed:
    sha = hashlib.sha256(inp.image).digest()
    fid = principal.facility_id

    with svc.db.transaction(fid) as conn:
        existing = _replay(svc, conn, inp)
        if existing is not None:
            return Analyzed(existing, sha.hex(), created=False)
        require_screening_consent(conn, inp.patient_id, inp.consent_id)
        other_patient = conn.execute(
            "SELECT clinical.image_seen_for_other_patient(%s, %s) AS seen",
            (sha, inp.patient_id),
        ).fetchone()["seen"]
        version = svc.engine.version()
        payload = _cache_lookup(svc, conn, sha, version.model_ver, version.cfg_hash)

    source = "cache" if payload is not None else "matlab"
    if payload is None:
        if svc.settings.cached_mode:
            raise Queued()
        payload = _run_engine(svc, inp, sha)

    flag = SAME_IMAGE if other_patient else None
    study_id = uuid4()
    image_key = f"raw/{fid}/{study_id}{_EXTENSIONS[inp.content_type]}"
    svc.storage.put(image_key, inp.image, inp.content_type)

    try:
        with svc.db.transaction(fid) as conn:
            if source == "matlab" and svc.settings.cache_enabled:
                conn.execute(
                    """INSERT INTO clinical.inference_cache
                           (img_sha256, model_ver, cfg_hash, payload)
                       VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                    (sha, payload["modelVer"], payload["cfgHash"], Jsonb(payload)),
                )
            _insert_study(conn, principal, inp, study_id, sha, image_key, payload, source, flag)
            response = load_study(conn, svc.storage, study_id)
    except psycopg.errors.UniqueViolation:
        with svc.db.transaction(fid) as conn:
            winner = _replay(svc, conn, inp)
        if winner is None:
            raise
        return Analyzed(winner, sha.hex(), created=False)

    assert response is not None
    _count(svc.metrics, response)
    return Analyzed(response, sha.hex(), created=True)


def _replay(svc: Services, conn: psycopg.Connection, inp: AnalyzeInput) -> StudyResponse | None:
    row = conn.execute(
        "SELECT id, patient_id, created_at FROM clinical.study WHERE client_key = %s",
        (inp.client_key,),
    ).fetchone()
    if row is None:
        svc.metrics.cache_requests.labels("idempotency", "miss").inc()
        return None
    if row["patient_id"] != inp.patient_id:
        raise HTTPException(409, "Idempotency-Key was already used for a different patient")
    ttl = timedelta(days=svc.settings.idempotency_ttl_days)
    if datetime.now(UTC) - row["created_at"] > ttl:
        raise HTTPException(409, "Idempotency-Key has expired; send a new key")
    svc.metrics.cache_requests.labels("idempotency", "hit").inc()
    return load_study(conn, svc.storage, row["id"])


def _cache_lookup(
    svc: Services, conn: psycopg.Connection, sha: bytes, model_ver: str, cfg: str
) -> dict[str, Any] | None:
    if not svc.settings.cache_enabled:
        return None
    row = conn.execute(
        """UPDATE clinical.inference_cache SET hit_count = hit_count + 1
           WHERE img_sha256 = %s AND model_ver = %s AND cfg_hash = %s
           RETURNING payload""",
        (sha, model_ver, cfg),
    ).fetchone()
    if row is None or row["payload"].get("contractVersion") != CONTRACT_VERSION:
        svc.metrics.cache_requests.labels("inference", "miss").inc()
        return None
    svc.metrics.cache_requests.labels("inference", "hit").inc()
    return row["payload"]


def _run_engine(svc: Services, inp: AnalyzeInput, sha: bytes) -> dict[str, Any]:
    svc.settings.work_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=svc.settings.work_dir, prefix="study-") as tmp:
        work = Path(tmp)
        img_path = work / inp.filename
        img_path.write_bytes(inp.image)
        out_dir = work / "out"
        started = time.perf_counter()
        try:
            txt = svc.engine.analyze_json(img_path, out_dir)
        except EngineUnavailable as exc:
            log.warning("engine unavailable: %s", exc)
            raise HTTPException(503, "grading node unavailable") from exc
        svc.metrics.analyze_seconds.observe(time.perf_counter() - started)
        try:
            result = EngineResult.model_validate_json(txt)
        except ValidationError as exc:
            log.error("engine contract violation: %d errors", exc.error_count())
            raise HTTPException(502, "engine returned a result that violates the contract") from exc
        return _store_artefacts(svc.storage, result, out_dir, sha.hex())


def _store_artefacts(
    storage: Storage, result: EngineResult, out_dir: Path, sha_hex: str
) -> dict[str, Any]:
    """Upload engine artefacts under a content-addressed prefix; paths become storage keys."""
    prefix = f"derived/{sha_hex}/{result.modelVer}/{result.cfgHash.removeprefix('sha256:')[:16]}/"
    root = out_dir.resolve()

    def upload(path: str | None) -> str | None:
        if path is None:
            return None
        target = Path(path).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise HTTPException(502, "engine artefact is missing or outside its output directory")
        key = prefix + target.relative_to(root).as_posix()
        content_type = {".png": "image/png", ".jpg": "image/jpeg", ".pdf": "application/pdf"}
        storage.put(
            key, target.read_bytes(), content_type.get(target.suffix.lower(), "binary/octet-stream")
        )
        return key

    payload = result.model_dump(mode="json")
    payload["gradcamPath"] = upload(result.gradcamPath)
    payload["reportPath"] = upload(result.reportPath)
    for ev in payload["evidence"]:
        ev["cropPath"] = upload(ev["cropPath"])
    return payload


def served_decision(payload: dict[str, Any], flag: str | None) -> str:
    if flag != SAME_IMAGE:
        return payload["decision"]
    return "RETAKE" if payload["quality"]["verdict"] == "reject" else "REFER"


def _insert_study(
    conn: psycopg.Connection,
    principal: Principal,
    inp: AnalyzeInput,
    study_id: UUID,
    sha: bytes,
    image_key: str,
    payload: dict[str, Any],
    source: str,
    flag: str | None,
) -> None:
    fid = principal.facility_id
    hidden = flag == SAME_IMAGE
    conn.execute(
        """INSERT INTO clinical.study
               (id, patient_id, facility_id, laterality, sha256, phash, client_key, flag, image_key)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            study_id,
            inp.patient_id,
            fid,
            payload["laterality"],
            sha,
            bytes.fromhex(payload["quality"]["phash"]),
            inp.client_key,
            flag,
            image_key,
        ),
    )
    conn.execute(
        """INSERT INTO clinical.result (study_id, facility_id, grade, posterior, p_referable, llp,
                                        model_ver, decision, source, payload)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            study_id,
            fid,
            None if hidden else payload["grade"],
            None if hidden else payload["posterior"],
            None if hidden else payload["pReferable"],
            None if hidden else payload["llp"],
            payload["modelVer"],
            served_decision(payload, flag),
            source,
            Jsonb(payload),
        ),
    )
    conn.execute(
        "INSERT INTO clinical.fhir_bundle (study_id, facility_id, bundle) VALUES (%s, %s, %s)",
        (study_id, fid, Jsonb(_EMPTY_BUNDLE if hidden else payload["fhirBundle"])),
    )
    audit.append(
        conn,
        actor=principal.actor,
        action="study.create",
        entity="study",
        entity_id=study_id,
        facility_id=fid,
        payload={
            "source": source,
            "flag": flag,
            "modelVer": payload["modelVer"],
            "cfgHash": payload["cfgHash"],
            "decision": served_decision(payload, flag),
        },
    )


def load_study(conn: psycopg.Connection, storage: Storage, study_id: UUID) -> StudyResponse | None:
    row = conn.execute(
        """SELECT s.id, s.patient_id, s.flag, s.created_at, r.source, r.payload
           FROM clinical.study AS s JOIN clinical.result AS r ON r.study_id = s.id
           WHERE s.id = %s""",
        (study_id,),
    ).fetchone()
    if row is None:
        return None
    return build_response(row, storage)


def build_response(row: dict[str, Any], storage: Storage) -> StudyResponse:
    data = dict(row["payload"])
    flag = row["flag"]
    raw_evidence = data.pop("evidence")
    gradcam_key = data.pop("gradcamPath", None)
    report_key = data.pop("reportPath", None)

    def url(key: str | None) -> str | None:
        return storage.presign(key) if key else None

    evidence: list[StudyEvidence] | None = [
        StudyEvidence(
            **{k: v for k, v in ev.items() if k != "cropPath"}, cropUrl=url(ev["cropPath"])
        )
        for ev in raw_evidence
    ]
    if flag == SAME_IMAGE:
        decision = served_decision(data, flag)
        data.update(
            decision=decision,
            reviewRequired=True,
            grade=None,
            posterior=None,
            pReferable=None,
            llp=None,
            criteria=[],
            fhirBundle=_EMPTY_BUNDLE,
        )
        if decision != "RETAKE":
            data["retakeGuidanceKey"] = None
        evidence, gradcam_key, report_key = None, None, None

    return StudyResponse(
        **data,
        evidence=evidence,
        gradcamUrl=url(gradcam_key),
        reportUrl=url(report_key),
        studyId=str(row["id"]),
        patientRef=str(row["patient_id"]),
        source=row["source"],
        flag=flag,
        createdAt=row["created_at"],
    )


def _count(metrics: Metrics, response: StudyResponse) -> None:
    if response.quality.verdict == "reject":
        metrics.quality_reject.labels(response.quality.failureMode).inc()
    grade = "none" if response.grade is None else str(response.grade)
    metrics.grade.labels(grade, response.decision).inc()
