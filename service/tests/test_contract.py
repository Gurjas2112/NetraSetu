"""Contract 6.1/6.2: every FakeEngine output validates, and the validators reject bad results."""

from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from service.engine import FakeEngine
from service.main import create_app
from service.schemas import EngineResult, StudyResponse
from service.settings import REPO_ROOT, Settings

FIXTURES = REPO_ROOT / "tests" / "fixtures"
THRESHOLD = REPO_ROOT / "matlab" / "config" / "threshold.json"

EXPECTED = {
    "grade0_clean": ("ROUTINE", "none"),
    "grade2_haem": ("REFER", "none"),
    "grade4_nv": ("REFER", "none"),
    "blur_s8": ("RETAKE", "defocus"),
    "underexposed": ("RETAKE", "underexposed"),
    "partial_fov": ("RETAKE", "partial_fov"),
}


@pytest.fixture(scope="module", autouse=True)
def fixtures_exist() -> None:
    missing = [n for n in EXPECTED if not (FIXTURES / f"{n}.png").is_file()]
    if missing:
        pytest.fail(f"run `python scripts/make_fixtures.py` first; missing {missing}")


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = Settings(
        engine="fake",
        matlab_shared_engine="netrasetu",
        nx_root=REPO_ROOT / "matlab",
        work_dir=tmp_path / "work",
        cors_origins=["http://localhost:5173"],
    )
    return TestClient(create_app(settings))


def _engine_result(name: str, tmp_path: Path) -> dict[str, Any]:
    txt = FakeEngine(THRESHOLD).analyze_json(FIXTURES / f"{name}.png", tmp_path / name)
    return json.loads(txt)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_fake_engine_output_validates(name: str, tmp_path: Path) -> None:
    result = EngineResult.model_validate(_engine_result(name, tmp_path))
    decision, failure_mode = EXPECTED[name]
    assert result.decision == decision
    assert result.quality.failureMode == failure_mode
    if decision == "RETAKE":
        assert result.retakeGuidanceKey and result.retakeGuidanceKey.startswith("retake.")
        assert result.grade is None and result.posterior is None
    if decision == "REFER":
        assert result.reviewRequired


def test_fake_engine_is_deterministic(tmp_path: Path) -> None:
    assert _engine_result("grade2_haem", tmp_path / "a") == _engine_result(
        "grade2_haem", tmp_path / "b"
    )


def test_unknown_image_is_referred(tmp_path: Path) -> None:
    img = tmp_path / "camera_0001.png"
    img.write_bytes((FIXTURES / "grade0_clean.png").read_bytes())
    result = EngineResult.model_validate_json(FakeEngine(THRESHOLD).analyze_json(img, tmp_path))
    assert result.decision == "REFER" and result.reviewRequired


def test_cfg_hash_matches_threshold_file(tmp_path: Path) -> None:
    import hashlib

    expected = "sha256:" + hashlib.sha256(THRESHOLD.read_bytes()).hexdigest()
    assert _engine_result("grade0_clean", tmp_path)["cfgHash"] == expected


# --- negative cases ---------------------------------------------------------------------------


def _refer(tmp_path: Path) -> dict[str, Any]:
    return _engine_result("grade2_haem", tmp_path)


def _retake(tmp_path: Path) -> dict[str, Any]:
    return _engine_result("blur_s8", tmp_path)


def _evidence() -> dict[str, Any]:
    return {
        "type": "HE",
        "x": 1532.4,
        "y": 988.7,
        "quadrant": "ST",
        "distanceToFoveaDD": 1.4,
        "cropPath": "/tmp/out/ev/03.png",
        "criterionKey": "icdr.l2.haemorrhages_multi_quadrant",
    }


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda r: r.update(posterior=[0.2, 0.2, 0.2, 0.2]), id="posterior-length-4"),
        pytest.param(
            lambda r: r.update(posterior=[0.1, 0.1, 0.6, 0.2, 0.1], pReferable=0.9),
            id="posterior-sum-1.1",
        ),
        pytest.param(lambda r: r.update(pReferable=0.5), id="preferable-inconsistent"),
        pytest.param(lambda r: r.update(pReferable=None), id="preferable-missing"),
        pytest.param(lambda r: r.update(reviewRequired=False), id="refer-without-review"),
        pytest.param(lambda r: r.update(decision="MAYBE"), id="fourth-decision"),
        pytest.param(lambda r: r.update(grade=5), id="grade-out-of-range"),
        pytest.param(lambda r: r.update(retakeGuidanceKey="retake.x"), id="guidance-on-refer"),
        pytest.param(lambda r: r.update(contractVersion="0.9"), id="wrong-contract"),
        pytest.param(lambda r: r.update(cfgHash="sha256:abc"), id="bad-cfg-hash"),
        pytest.param(lambda r: r["quality"].update(phash="xyz"), id="bad-phash"),
        pytest.param(lambda r: r.update(unexpected=1), id="extra-field"),
        pytest.param(lambda r: r.update(evidence=[{**_evidence(), "type": "XX"}]), id="bad-lesion"),
        pytest.param(lambda r: r.update(evidence=None), id="engine-evidence-null"),
    ],
)
def test_refer_rejects(mutate, tmp_path: Path) -> None:
    result = copy.deepcopy(_refer(tmp_path))
    mutate(result)
    with pytest.raises(ValidationError):
        EngineResult.model_validate(result)


def test_refer_with_evidence_validates(tmp_path: Path) -> None:
    result = _refer(tmp_path)
    result["evidence"] = [_evidence()]
    EngineResult.model_validate(result)


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda r: r.update(grade=2), id="retake-with-grade"),
        pytest.param(
            lambda r: r.update(posterior=[0.2] * 5, pReferable=0.6), id="retake-with-posterior"
        ),
        pytest.param(lambda r: r.update(retakeGuidanceKey=None), id="retake-without-guidance"),
        pytest.param(lambda r: r.update(retakeGuidanceKey="ungradeable"), id="retake-bare-word"),
        pytest.param(lambda r: r["quality"].update(verdict="accept"), id="retake-accepted"),
    ],
)
def test_retake_rejects(mutate, tmp_path: Path) -> None:
    result = copy.deepcopy(_retake(tmp_path))
    mutate(result)
    with pytest.raises(ValidationError):
        EngineResult.model_validate(result)


def test_routine_requires_low_grade(tmp_path: Path) -> None:
    result = _engine_result("grade0_clean", tmp_path)
    result["grade"] = 2
    with pytest.raises(ValidationError):
        EngineResult.model_validate(result)


def _study(tmp_path: Path, **overrides: Any) -> dict[str, Any]:
    base = _refer(tmp_path)
    base.pop("gradcamPath")
    base.pop("reportPath")
    base.update(
        studyId=str(uuid.uuid4()),
        patientRef="p-opaque",
        source="cache",
        flag=None,
        createdAt="2026-10-05T12:00:00Z",
        gradcamUrl=None,
        reportUrl=None,
    )
    base.update(overrides)
    return base


def test_flagged_study_requires_nulls(tmp_path: Path) -> None:
    flagged = _study(
        tmp_path,
        flag="same_image_other_patient",
        grade=None,
        posterior=None,
        pReferable=None,
        evidence=None,
    )
    StudyResponse.model_validate(flagged)

    with pytest.raises(ValidationError):
        StudyResponse.model_validate({**flagged, "grade": 2})
    with pytest.raises(ValidationError):
        StudyResponse.model_validate({**flagged, "evidence": []})
    with pytest.raises(ValidationError):
        StudyResponse.model_validate({**flagged, "reviewRequired": False})


def test_flagged_study_is_refer_unless_rejected(tmp_path: Path) -> None:
    flagged_retake = {
        **_retake(tmp_path),
        "studyId": str(uuid.uuid4()),
        "patientRef": "p-opaque",
        "source": "cache",
        "flag": "same_image_other_patient",
        "createdAt": "2026-10-05T12:00:00Z",
        "evidence": None,
        "reviewRequired": True,
    }
    flagged_retake.pop("gradcamPath")
    flagged_retake.pop("reportPath")
    StudyResponse.model_validate(flagged_retake)

    accepted = _study(
        tmp_path,
        flag="same_image_other_patient",
        grade=None,
        posterior=None,
        pReferable=None,
        evidence=None,
        decision="RETAKE",
        retakeGuidanceKey="retake.defocus.hold_steady",
    )
    with pytest.raises(ValidationError):
        StudyResponse.model_validate(accepted)


def test_unflagged_study_requires_evidence(tmp_path: Path) -> None:
    StudyResponse.model_validate(_study(tmp_path))
    with pytest.raises(ValidationError):
        StudyResponse.model_validate(_study(tmp_path, evidence=None))


def test_openapi_generates(tmp_path: Path) -> None:
    from scripts.export_openapi import openapi_schema

    schema = openapi_schema()
    for path in (
        "/analyze",
        "/study/{study_id}",
        "/review/queue",
        "/review/{study_id}",
        "/consent",
        "/r/{token}",
        "/healthz",
    ):
        assert path in schema["paths"], path
    for name in ("StudyResponse", "QueuedBody", "PatientView", "ReviewRequest"):
        assert name in schema["components"]["schemas"], name
