"""NetraSetu gateway (M1: contract end to end, no auth, no persistence).

Auth, persistence, the inference cache and presigned storage URLs arrive in M2/M3. Until then
artefacts are served from the local work directory under /artifacts.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from service.engine import Engine, EngineUnavailable, build_engine
from service.schemas import (
    CONTRACT_VERSION,
    EngineResult,
    ErrorBody,
    HealthStatus,
    StudyEvidence,
    StudyResponse,
)
from service.settings import Settings, load_settings

log = logging.getLogger("netrasetu.gateway")

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg"}
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]")


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


def _artifact_url(path: str | None, study_dir: Path, study_id: str) -> str | None:
    if path is None:
        return None
    resolved = Path(path).resolve()
    try:
        rel = resolved.relative_to(study_dir.resolve())
    except ValueError as exc:
        raise HTTPException(502, "engine wrote an artefact outside the study directory") from exc
    return f"/artifacts/{study_id}/{rel.as_posix()}"


def to_study_response(
    result: EngineResult, *, study_id: str, patient_ref: str, study_dir: Path
) -> StudyResponse:
    data = result.model_dump(exclude={"evidence", "gradcamPath", "reportPath"})
    evidence = [
        StudyEvidence(
            **ev.model_dump(exclude={"cropPath"}),
            cropUrl=_artifact_url(ev.cropPath, study_dir, study_id) or "",
        )
        for ev in result.evidence
    ]
    return StudyResponse(
        **data,
        evidence=evidence,
        gradcamUrl=_artifact_url(result.gradcamPath, study_dir, study_id),
        reportUrl=_artifact_url(result.reportPath, study_dir, study_id),
        studyId=study_id,
        patientRef=patient_ref,
        source="matlab",
        flag=None,
        createdAt=datetime.now(UTC),
    )


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or load_settings()
    engine = engine or build_engine(settings)

    app = FastAPI(
        title="NetraSetu gateway",
        version=CONTRACT_VERSION,
        description="Explainable DR screening gateway. Contract: docs/CONTRACT.md",
    )
    app.state.settings = settings
    app.state.engine = engine

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
        responses={400: {"model": ErrorBody}, 502: {"model": ErrorBody}, 503: {"model": ErrorBody}},
    )
    def analyze(
        file: Annotated[UploadFile, File(description="Fundus image, PNG or JPEG")],
        patientRef: Annotated[str, Form(min_length=1, max_length=128)],
        consentId: Annotated[str, Form(min_length=1, max_length=128)],
        idempotency_key: Annotated[uuid.UUID, Header(alias="Idempotency-Key")],
    ) -> StudyResponse:
        content_type = (file.content_type or "").lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(400, "file must be a PNG or JPEG image")
        payload = file.file.read(settings.max_upload_bytes + 1)
        if not payload:
            raise HTTPException(400, "file is empty")
        if len(payload) > settings.max_upload_bytes:
            raise HTTPException(400, "file is too large")

        study_id = str(uuid.uuid4())
        study_dir = settings.work_dir / study_id
        study_dir.mkdir(parents=True, exist_ok=True)
        img_path = study_dir / _safe_filename(file.filename, content_type)
        img_path.write_bytes(payload)

        try:
            txt = engine.analyze_json(img_path, study_dir / "out")
        except EngineUnavailable as exc:
            log.warning("engine unavailable for study %s: %s", study_id, exc)
            raise HTTPException(503, "grading node unavailable") from exc

        try:
            result = EngineResult.model_validate_json(txt)
        except ValidationError as exc:
            log.error(
                "engine contract violation for study %s: %d errors", study_id, exc.error_count()
            )
            raise HTTPException(502, "engine returned a result that violates the contract") from exc

        return to_study_response(
            result, study_id=study_id, patient_ref=patientRef, study_dir=study_dir
        )

    @app.get("/artifacts/{study_id}/{rel_path:path}", include_in_schema=False)
    def artifact(study_id: uuid.UUID, rel_path: str) -> FileResponse:
        study_dir = (settings.work_dir / str(study_id)).resolve()
        target = (study_dir / rel_path).resolve()
        if not target.is_relative_to(study_dir) or not target.is_file():
            raise HTTPException(404, "not found")
        return FileResponse(target)

    @app.get("/healthz", response_model=HealthStatus)
    def healthz() -> HealthStatus:
        ready = engine.ready()
        return HealthStatus(
            status="ok" if ready else "degraded", engine=engine.name, engineReady=ready
        )

    return app


app = create_app()
