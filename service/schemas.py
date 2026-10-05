"""Pydantic models for the NetraSetu contract (docs/CONTRACT.md).

`EngineResult` is contract 6.1: the JSON text returned by `netrasetu_analyze_json`.
`StudyResponse` is contract 6.2: what the gateway returns to clients.

Keep this file, docs/CONTRACT.md and the MATLAB output in exact agreement.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "1.0"
POSTERIOR_TOLERANCE = 1e-6

Decision = Literal["REFER", "ROUTINE", "RETAKE"]
Verdict = Literal["accept", "enhance", "reject"]
FailureMode = Literal[
    "none", "defocus", "underexposed", "overexposed", "partial_fov", "media_opacity"
]
Laterality = Literal["OD", "OS", "unknown"]
LesionType = Literal["MA", "HE", "EX", "SE", "NV_PROXY"]
Quadrant = Literal["ST", "SN", "IT", "IN"]
Source = Literal["matlab", "cache"]
Flag = Literal["same_image_other_patient", "repeat_screening"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Quality(_Strict):
    verdict: Verdict
    score: float = Field(ge=0.0, le=1.0)
    failureMode: FailureMode
    phash: str = Field(pattern=r"^[0-9a-f]{16}$")


class Criterion(_Strict):
    key: str = Field(pattern=r"^icdr\.[a-z0-9_.]+$")
    grade: int = Field(ge=0, le=4)
    detail: dict[str, int | float | str | bool] = Field(default_factory=dict)


class _EvidenceBase(_Strict):
    type: LesionType
    x: float = Field(ge=0.0)
    y: float = Field(ge=0.0)
    quadrant: Quadrant
    distanceToFoveaDD: float | None = Field(ge=0.0)
    criterionKey: str | None


class EngineEvidence(_EvidenceBase):
    cropPath: str


class StudyEvidence(_EvidenceBase):
    cropUrl: str


class _ResultBase(_Strict):
    contractVersion: Literal["1.0"]
    modelVer: str = Field(min_length=1)
    cfgHash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    decision: Decision
    reviewRequired: bool
    quality: Quality
    retakeGuidanceKey: str | None = Field(
        default=None, pattern=r"^retake\.[a-z0-9_]+(\.[a-z0-9_]+)*$"
    )
    grade: int | None = Field(ge=0, le=4)
    posterior: list[float] | None
    pReferable: float | None = Field(ge=0.0, le=1.0)
    laterality: Laterality
    criteria: list[Criterion]
    llp: float | None = Field(default=None, ge=0.0, le=1.0)
    fhirBundle: dict[str, Any]

    def _check_common(self) -> None:
        if self.posterior is not None:
            if len(self.posterior) != 5:
                raise ValueError("posterior must have length 5")
            if any(p < 0.0 or p > 1.0 for p in self.posterior):
                raise ValueError("posterior entries must lie in [0, 1]")
            if abs(sum(self.posterior) - 1.0) > POSTERIOR_TOLERANCE:
                raise ValueError("posterior must sum to 1 within 1e-6")
            if self.pReferable is None:
                raise ValueError("pReferable is required when posterior is present")
            expected = self.posterior[2] + self.posterior[3] + self.posterior[4]
            if abs(self.pReferable - expected) > POSTERIOR_TOLERANCE:
                raise ValueError("pReferable must equal posterior[2] + posterior[3] + posterior[4]")
        elif self.pReferable is not None:
            raise ValueError("pReferable must be null when posterior is null")

        if self.decision == "RETAKE":
            if self.grade is not None or self.posterior is not None:
                raise ValueError("grade and posterior must be null when decision is RETAKE")
            if not self.retakeGuidanceKey:
                raise ValueError("retakeGuidanceKey is required when decision is RETAKE")
            if self.quality.verdict != "reject" or self.quality.failureMode == "none":
                raise ValueError("RETAKE requires quality verdict 'reject' with a failure mode")
        else:
            if self.retakeGuidanceKey is not None:
                raise ValueError("retakeGuidanceKey is only allowed when decision is RETAKE")
            if self.quality.verdict == "reject":
                raise ValueError("a rejected image must produce decision RETAKE")

        if self.decision == "REFER" and not self.reviewRequired:
            raise ValueError("every REFER requires reviewRequired = true")

        if self.decision == "ROUTINE":
            if self.grade is None or self.grade > 1 or self.posterior is None:
                raise ValueError("ROUTINE requires a grade of 0 or 1 and a posterior")


class EngineResult(_ResultBase):
    """Contract 6.1 — returned by MATLAB (or the fake engine) as JSON text."""

    evidence: list[EngineEvidence]
    gradcamPath: str | None = None
    reportPath: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        self._check_common()
        if self.decision != "RETAKE" and (self.grade is None or self.posterior is None):
            raise ValueError("grade and posterior are required unless decision is RETAKE")
        return self


class StudyResponse(_ResultBase):
    """Contract 6.2 — the engine result as served by the gateway."""

    studyId: str
    patientRef: str
    source: Source
    flag: Flag | None
    createdAt: datetime
    evidence: list[StudyEvidence] | None
    gradcamUrl: str | None = None
    reportUrl: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        self._check_common()
        if self.flag == "same_image_other_patient":
            if self.grade is not None or self.posterior is not None or self.evidence is not None:
                raise ValueError(
                    "grade, posterior and evidence must be null for same_image_other_patient"
                )
            if not self.reviewRequired:
                raise ValueError("same_image_other_patient requires reviewRequired = true")
            if self.decision != "REFER":
                raise ValueError("same_image_other_patient is shown to the screener as REFER")
        else:
            if self.evidence is None:
                raise ValueError("evidence may only be null for same_image_other_patient")
            if self.decision != "RETAKE" and (self.grade is None or self.posterior is None):
                raise ValueError("grade and posterior are required unless decision is RETAKE")
        return self


class HealthStatus(_Strict):
    status: Literal["ok", "degraded"]
    engine: str
    engineReady: bool
    contractVersion: Literal["1.0"] = CONTRACT_VERSION


class ErrorBody(_Strict):
    detail: str
