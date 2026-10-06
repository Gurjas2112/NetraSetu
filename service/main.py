"""NetraSetu gateway: OIDC, consent, audit, inference cache and presigned storage URLs.

Run with `uvicorn service.main:create_app --factory`; configuration comes from the environment.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from service import audit, cache, consent, review, tiles, tokens
from service.auth import (
    JwksCache,
    JwksFetcher,
    Principal,
    TokenVerifier,
    http_jwks_fetcher,
    require_role,
)
from service.db import Database
from service.engine import Engine, build_engine
from service.metrics import CONTENT_TYPE_LATEST, Metrics
from service.schemas import (
    CONTRACT_VERSION,
    ConsentRequest,
    ConsentResponse,
    ErrorBody,
    HealthStatus,
    PatientLinkRequest,
    PatientLinkResponse,
    PatientView,
    QueuedBody,
    ReviewQueueItem,
    ReviewRequest,
    ReviewResponse,
    StudyResponse,
)
from service.settings import Settings, load_settings
from service.storage import S3Storage, Storage

log = logging.getLogger("netrasetu.gateway")

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg"}
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]")
_TILE_PATH = re.compile(r"^image(\.dzi|_files/\d{1,2}/\d{1,4}_\d{1,4}\.jpeg)$")
QUEUED = QueuedBody(status="queued", reason="grading node unavailable")

Screener = Annotated[Principal, Depends(require_role("screener"))]
Clinician = Annotated[Principal, Depends(require_role("screener", "grader"))]
Grader = Annotated[Principal, Depends(require_role("grader"))]
SigningGrader = Annotated[Principal, Depends(require_role("grader", totp=True))]

_ERRORS = {
    401: {"model": ErrorBody},
    403: {"model": ErrorBody},
    404: {"model": ErrorBody},
}


class NoStoreMiddleware(BaseHTTPMiddleware):
    """Every response is clinical or operational; none may be cached anywhere."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response


def _safe_filename(name: str | None, content_type: str) -> str:
    fallback = "upload.png" if content_type == "image/png" else "upload.jpg"
    if not name:
        return fallback
    cleaned = _SAFE_NAME.sub("_", Path(name).name).lstrip(".")
    return cleaned[:120] or fallback


def create_app(
    settings: Settings | None = None,
    *,
    engine: Engine | None = None,
    storage: Storage | None = None,
    jwks_fetch: JwksFetcher | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    svc = cache.Services(
        settings=settings,
        db=Database(settings.database_url),
        engine=engine or build_engine(settings),
        storage=storage or S3Storage(settings.s3, settings.presign_ttl_seconds),
        metrics=Metrics(),
    )

    app = FastAPI(
        title="NetraSetu gateway",
        version=CONTRACT_VERSION,
        description="Explainable DR screening gateway. Contract: docs/CONTRACT.md",
    )
    app.state.settings = settings
    app.state.services = svc
    app.state.verifier = TokenVerifier(
        JwksCache(jwks_fetch or http_jwks_fetcher(settings.jwks_url), settings.jwks_cache_seconds),
        issuer=settings.oidc_issuer,
        audience=settings.oidc_audience,
    )

    app.add_middleware(NoStoreMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )

    @app.post(
        "/analyze",
        response_model=StudyResponse,
        responses={
            **_ERRORS,
            400: {"model": ErrorBody},
            409: {"model": ErrorBody},
            502: {"model": ErrorBody},
            503: {"model": QueuedBody | ErrorBody},
        },
    )
    def analyze(
        principal: Screener,
        background: BackgroundTasks,
        file: Annotated[UploadFile, File(description="Fundus image, PNG or JPEG")],
        patientRef: Annotated[uuid.UUID, Form()],
        consentId: Annotated[uuid.UUID, Form()],
        idempotency_key: Annotated[uuid.UUID, Header(alias="Idempotency-Key")],
    ) -> StudyResponse | JSONResponse:
        content_type = (file.content_type or "").lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(400, "file must be a PNG or JPEG image")
        payload = file.file.read(settings.max_upload_bytes + 1)
        if not payload:
            raise HTTPException(400, "file is empty")
        if len(payload) > settings.max_upload_bytes:
            raise HTTPException(400, "file is too large")

        inp = cache.AnalyzeInput(
            image=payload,
            filename=_safe_filename(file.filename, content_type),
            content_type=content_type,
            patient_id=patientRef,
            consent_id=consentId,
            client_key=idempotency_key,
        )
        try:
            result = cache.analyze(svc, principal, inp)
        except cache.Queued:
            return JSONResponse(QUEUED.model_dump(), status_code=503)
        if result.created:
            background.add_task(tiles.ensure_tiles, svc.storage, result.sha_hex, payload)
        return result.response

    @app.get("/study/{study_id}", response_model=StudyResponse, responses=_ERRORS)
    def get_study(study_id: uuid.UUID, principal: Clinician) -> StudyResponse:
        with svc.db.transaction(principal.facility_id) as conn:
            study = cache.load_study(conn, svc.storage, study_id)
        if study is None:
            raise HTTPException(404, "study not found")
        return study

    @app.get(
        "/study/{study_id}/tiles/{tile_path:path}",
        responses={**_ERRORS, 307: {"description": "Redirect to a presigned tile URL"}},
        response_class=Response,
    )
    def get_tile(study_id: uuid.UUID, tile_path: str, principal: Clinician) -> Response:
        if not _TILE_PATH.match(tile_path):
            raise HTTPException(404, "not found")
        with svc.db.transaction(principal.facility_id) as conn:
            row = conn.execute(
                "SELECT sha256 FROM clinical.study WHERE id = %s", (study_id,)
            ).fetchone()
        if row is None:
            raise HTTPException(404, "study not found")
        key = tiles.tiles_prefix(bytes(row["sha256"]).hex()) + tile_path
        if tile_path == tiles.DZI_NAME:
            if not svc.storage.exists(key):
                raise HTTPException(404, "tiles are not ready")
            return Response(svc.storage.get(key), media_type="application/xml")
        return RedirectResponse(svc.storage.presign(key), status_code=307)

    @app.post(
        "/study/{study_id}/patient-link",
        response_model=PatientLinkResponse,
        responses={**_ERRORS, 409: {"model": ErrorBody}},
    )
    def patient_link(
        study_id: uuid.UUID, body: PatientLinkRequest, principal: Screener
    ) -> PatientLinkResponse:
        phash = consent.phone_hash(settings.patient_token_secret, body.phone)
        with svc.db.transaction(principal.facility_id) as conn:
            row = conn.execute(
                """SELECT p.phone_hash FROM clinical.study AS s
                   JOIN clinical.patient AS p ON p.id = s.patient_id WHERE s.id = %s""",
                (study_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "study not found")
            if row["phone_hash"] is None or bytes(row["phone_hash"]) != phash:
                raise HTTPException(409, "phone does not match the number recorded at consent")
            token, tok = tokens.mint(
                settings.patient_token_secret,
                study_id,
                phash,
                settings.patient_token_hours * 3600,
            )
            conn.execute(
                """INSERT INTO clinical.patient_token
                       (jti, study_id, facility_id, phone_hash, expires_at)
                   VALUES (%s, %s, %s, %s, to_timestamp(%s))""",
                (tok.jti, study_id, principal.facility_id, phash, tok.expires_at),
            )
            audit.append(
                conn,
                actor=principal.actor,
                action="patient_link.issue",
                entity="study",
                entity_id=study_id,
                facility_id=principal.facility_id,
                payload={"jti": str(tok.jti)},
            )
        return PatientLinkResponse(
            token=token, expiresAt=datetime.fromtimestamp(tok.expires_at, UTC)
        )

    @app.get(
        "/r/{token}",
        response_model=PatientView,
        responses={404: {"model": ErrorBody}, 410: {"model": ErrorBody}},
    )
    def patient_view(token: str) -> PatientView:
        try:
            tok = tokens.verify(settings.patient_token_secret, token)
        except tokens.TokenExpired as exc:
            raise HTTPException(410, "this link has expired") from exc
        except tokens.TokenInvalid as exc:
            raise HTTPException(404, "not found") from exc
        with svc.db.unscoped() as conn:
            redeemed = conn.execute(
                "SELECT * FROM clinical.redeem_patient_token(%s, %s)", (tok.jti, tok.phone_hash)
            ).fetchone()
        if redeemed["status"] == "unknown" or redeemed["study_id"] != tok.study_id:
            raise HTTPException(404, "not found")
        if redeemed["status"] == "gone":
            raise HTTPException(410, "this link has already been used")
        with svc.db.transaction(redeemed["facility_id"]) as conn:
            row = conn.execute(
                """SELECT s.laterality, s.created_at, s.flag, r.decision, r.payload,
                          (SELECT v.decision FROM clinical.review AS v WHERE v.study_id = s.id
                           ORDER BY v.created_at DESC LIMIT 1) AS reviewed_decision
                   FROM clinical.study AS s JOIN clinical.result AS r ON r.study_id = s.id
                   WHERE s.id = %s""",
                (tok.study_id,),
            ).fetchone()
            audit.append(
                conn,
                actor="patient",
                action="patient_link.redeem",
                entity="study",
                entity_id=tok.study_id,
                facility_id=redeemed["facility_id"],
                payload={"jti": str(tok.jti)},
            )
        decision = row["reviewed_decision"] or row["decision"]
        guidance = None
        if decision == "RETAKE" and row["reviewed_decision"] is None:
            guidance = row["payload"].get("retakeGuidanceKey")
        return PatientView(
            decision=decision,
            reviewed=row["reviewed_decision"] is not None,
            laterality=row["laterality"],
            screenedAt=row["created_at"],
            retakeGuidanceKey=guidance,
        )

    @app.get("/review/queue", response_model=list[ReviewQueueItem], responses=_ERRORS)
    def review_queue(principal: Grader) -> list[ReviewQueueItem]:
        threshold = review.read_threshold(settings.threshold_path)
        with svc.db.transaction(principal.facility_id) as conn:
            return review.queue(conn, threshold)

    @app.post(
        "/review/{study_id}",
        response_model=ReviewResponse,
        responses={**_ERRORS, 409: {"model": ErrorBody}, 422: {"model": ErrorBody}},
    )
    def sign_review(
        study_id: uuid.UUID, body: ReviewRequest, principal: SigningGrader
    ) -> ReviewResponse:
        with svc.db.transaction(principal.facility_id) as conn:
            return review.sign(conn, principal, study_id, body, svc.metrics)

    @app.post("/consent", response_model=ConsentResponse, responses=_ERRORS)
    def give_consent(body: ConsentRequest, principal: Screener) -> ConsentResponse:
        with svc.db.transaction(principal.facility_id) as conn:
            return consent.grant(conn, principal, body, settings.patient_token_secret)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(svc.metrics.render(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/healthz", response_model=HealthStatus)
    def healthz() -> HealthStatus:
        engine_ready = svc.engine.ready()
        db_ready = svc.db.ready()
        storage_ready = svc.storage.ready()
        ok = engine_ready and db_ready and storage_ready
        return HealthStatus(
            status="ok" if ok else "degraded",
            engine=svc.engine.name,
            engineReady=engine_ready,
            databaseReady=db_ready,
            storageReady=storage_ready,
        )

    return app
