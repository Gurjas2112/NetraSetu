"""Gateway behaviour (M3): auth, idempotency, inference cache, cross-patient flag, RLS-scoped
reads, consent, review, patient links, tiles, metrics and cached mode."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import psycopg
import pytest

from service import audit, tokens
from service.engine import FakeEngine
from service.schemas import StudyResponse
from service.tests.conftest import (
    THRESHOLD,
    Gateway,
    GatewayFactory,
    Mint,
    unique_png,
)

NOTICE = hashlib.sha256(b"screening notice v1").hexdigest()
PHONE = "+91 98765 43210"


def _patient(gw: Gateway, auth: dict[str, str], phone: str | None = PHONE) -> dict[str, str]:
    body: dict[str, Any] = {"purpose": "screening", "noticeHash": NOTICE, "language": "hi"}
    if phone:
        body["phone"] = phone
    r = gw.client.post("/consent", json=body, headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


def _analyze(
    gw: Gateway,
    auth: dict[str, str],
    patient: dict[str, str],
    image: bytes,
    name: str = "grade2_haem",
    key: uuid.UUID | None = None,
):
    return gw.client.post(
        "/analyze",
        files={"file": (f"{name}.png", image, "image/png")},
        data={"patientRef": patient["patientRef"], "consentId": patient["consentId"]},
        headers={"Idempotency-Key": str(key or uuid.uuid4()), **auth},
    )


def _audit_payload(admin_db: psycopg.Connection, study_id: str) -> dict[str, Any]:
    row = admin_db.execute(
        """SELECT payload FROM clinical.audit
           WHERE entity_id = %s AND action = 'study.create'""",
        (study_id,),
    ).fetchone()
    assert row is not None
    return row["payload"]


@pytest.fixture
def facility() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def screener(mint: Mint, facility: uuid.UUID) -> dict[str, str]:
    return mint("screener", facility)


# --- analyze ------------------------------------------------------------------------------------

EXPECTED = {
    "grade0_clean": "ROUTINE",
    "grade2_haem": "REFER",
    "grade4_nv": "REFER",
    "blur_s8": "RETAKE",
    "underexposed": "RETAKE",
    "partial_fov": "RETAKE",
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_analyze_returns_study(gateway: Gateway, screener: dict[str, str], name: str) -> None:
    patient = _patient(gateway, screener)
    r = _analyze(gateway, screener, patient, unique_png(), name)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    study = StudyResponse.model_validate(r.json())
    assert study.decision == EXPECTED[name]
    assert study.patientRef == patient["patientRef"]
    assert study.source == "matlab" and study.flag is None
    assert "gradcamPath" not in r.json()
    raw = [k for k in gateway.storage.objects if k.startswith("raw/")]
    assert raw and all(k.endswith(".png") for k in raw)


def test_retry_returns_same_study(gateway: Gateway, screener: dict[str, str]) -> None:
    patient = _patient(gateway, screener)
    image, key = unique_png(), uuid.uuid4()
    a = _analyze(gateway, screener, patient, image, key=key).json()
    b = _analyze(gateway, screener, patient, image, key=key).json()
    assert a["studyId"] == b["studyId"]
    assert gateway.engine.calls == 1


def test_idempotency_key_reused_for_other_patient_conflicts(
    gateway: Gateway, screener: dict[str, str]
) -> None:
    key = uuid.uuid4()
    first = _analyze(gateway, screener, _patient(gateway, screener), unique_png(), key=key)
    assert first.status_code == 200
    other = _analyze(gateway, screener, _patient(gateway, screener), unique_png(), key=key)
    assert other.status_code == 409


def test_cache_hit_creates_new_study_with_source_cache(
    gateway: Gateway, screener: dict[str, str], admin_db: psycopg.Connection
) -> None:
    patient = _patient(gateway, screener)
    image = unique_png()
    a = _analyze(gateway, screener, patient, image).json()
    b = _analyze(gateway, screener, patient, image).json()
    assert a["studyId"] != b["studyId"]
    assert a["source"] == "matlab" and b["source"] == "cache"
    assert _audit_payload(admin_db, b["studyId"])["source"] == "cache"
    assert _audit_payload(admin_db, a["studyId"])["source"] == "matlab"
    assert gateway.engine.calls == 1


def test_same_pixels_on_other_patient_is_flagged_with_null_grade(
    gateway: Gateway, screener: dict[str, str], admin_db: psycopg.Connection
) -> None:
    image = unique_png()
    first = _analyze(gateway, screener, _patient(gateway, screener), image, "grade4_nv").json()
    assert first["grade"] == 4
    r = _analyze(gateway, screener, _patient(gateway, screener), image, "grade4_nv")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["flag"] == "same_image_other_patient"
    assert body["grade"] is None and body["posterior"] is None and body["evidence"] is None
    assert body["decision"] == "REFER" and body["reviewRequired"] is True
    row = admin_db.execute(
        "SELECT grade, posterior, decision FROM clinical.result WHERE study_id = %s",
        (body["studyId"],),
    ).fetchone()
    assert row == {"grade": None, "posterior": None, "decision": "REFER"}


def test_same_pixels_across_facilities_is_flagged(gateway: Gateway, mint: Mint) -> None:
    image = unique_png()
    a = mint("screener", uuid.uuid4())
    b = mint("screener", uuid.uuid4())
    _analyze(gateway, a, _patient(gateway, a), image)
    flagged = _analyze(gateway, b, _patient(gateway, b), image).json()
    assert flagged["flag"] == "same_image_other_patient"


def test_flagged_rejected_image_is_still_a_retake(
    gateway: Gateway, screener: dict[str, str]
) -> None:
    image = unique_png()
    _analyze(gateway, screener, _patient(gateway, screener), image, "blur_s8")
    body = _analyze(gateway, screener, _patient(gateway, screener), image, "blur_s8").json()
    assert body["flag"] == "same_image_other_patient"
    assert body["decision"] == "RETAKE" and body["reviewRequired"] is True
    assert body["retakeGuidanceKey"] == "retake.defocus.hold_steady"


def test_model_version_change_misses_cache(
    gateway_factory: GatewayFactory, screener: dict[str, str]
) -> None:
    v1 = gateway_factory()
    patient = _patient(v1, screener)
    image = unique_png()
    assert _analyze(v1, screener, patient, image).json()["source"] == "matlab"
    assert _analyze(v1, screener, patient, image).json()["source"] == "cache"
    v2 = gateway_factory(engine=FakeEngine(THRESHOLD, model_ver="netrasetu_v2"))
    again = _analyze(v2, screener, patient, image).json()
    assert again["source"] == "matlab" and again["modelVer"] == "netrasetu_v2"


def test_cache_disabled_always_runs_engine(
    gateway_factory: GatewayFactory, screener: dict[str, str]
) -> None:
    gw = gateway_factory(cache_enabled=False)
    patient = _patient(gw, screener)
    image = unique_png()
    _analyze(gw, screener, patient, image)
    assert _analyze(gw, screener, patient, image).json()["source"] == "matlab"
    assert gw.engine.calls == 2


def test_cached_mode_serves_hits_and_queues_misses(
    gateway_factory: GatewayFactory, screener: dict[str, str]
) -> None:
    warm = gateway_factory()
    patient = _patient(warm, screener)
    image = unique_png()
    _analyze(warm, screener, patient, image)

    cached = gateway_factory(cached_mode=True)
    hit = _analyze(cached, screener, patient, image)
    assert hit.status_code == 200 and hit.json()["source"] == "cache"
    miss = _analyze(cached, screener, patient, unique_png())
    assert miss.status_code == 503
    assert miss.json() == {"status": "queued", "reason": "grading node unavailable"}
    assert cached.engine.calls == 0


def test_analyze_requires_live_consent_for_that_patient(
    gateway: Gateway, screener: dict[str, str], admin_db: psycopg.Connection
) -> None:
    p1, p2 = _patient(gateway, screener), _patient(gateway, screener)
    crossed = {"patientRef": p1["patientRef"], "consentId": p2["consentId"]}
    assert _analyze(gateway, screener, crossed, unique_png()).status_code == 409
    admin_db.execute(
        "UPDATE clinical.consent SET withdrawn_at = now() WHERE id = %s", (p1["consentId"],)
    )
    assert _analyze(gateway, screener, p1, unique_png()).status_code == 409


def test_analyze_rejects_non_image(gateway: Gateway, screener: dict[str, str]) -> None:
    patient = _patient(gateway, screener)
    r = gateway.client.post(
        "/analyze",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={"patientRef": patient["patientRef"], "consentId": patient["consentId"]},
        headers={"Idempotency-Key": str(uuid.uuid4()), **screener},
    )
    assert r.status_code == 400
    assert r.headers["cache-control"] == "no-store"


def test_analyze_requires_idempotency_key(gateway: Gateway, screener: dict[str, str]) -> None:
    patient = _patient(gateway, screener)
    r = gateway.client.post(
        "/analyze",
        files={"file": ("grade0_clean.png", unique_png(), "image/png")},
        data={"patientRef": patient["patientRef"], "consentId": patient["consentId"]},
        headers=screener,
    )
    assert r.status_code == 422


class _BrokenEngine(FakeEngine):
    def analyze_json(self, img_path: Path, out_dir: Path) -> str:
        return json.dumps({"decision": "MAYBE"})


def test_engine_contract_violation_is_502(
    gateway_factory: GatewayFactory, screener: dict[str, str]
) -> None:
    gw = gateway_factory(engine=_BrokenEngine(THRESHOLD))
    assert _analyze(gw, screener, _patient(gw, screener), unique_png()).status_code == 502


# --- reads across facilities --------------------------------------------------------------------


def test_screener_gets_404_across_facilities(gateway: Gateway, mint: Mint) -> None:
    a = mint("screener", uuid.uuid4())
    study = _analyze(gateway, a, _patient(gateway, a), unique_png()).json()
    assert gateway.client.get(f"/study/{study['studyId']}", headers=a).status_code == 200
    other = mint("screener", uuid.uuid4())
    r = gateway.client.get(f"/study/{study['studyId']}", headers=other)
    assert r.status_code == 404
    assert r.headers["cache-control"] == "no-store"


def test_grader_reads_study_in_own_facility(
    gateway: Gateway, mint: Mint, facility: uuid.UUID, screener: dict[str, str]
) -> None:
    study = _analyze(gateway, screener, _patient(gateway, screener), unique_png()).json()
    grader = mint("grader", facility, otp=True, hpr="HPR-1")
    assert gateway.client.get(f"/study/{study['studyId']}", headers=grader).status_code == 200


# --- auth ---------------------------------------------------------------------------------------


def test_missing_or_bad_tokens_are_401(gateway: Gateway, mint: Mint, facility: uuid.UUID) -> None:
    sid = uuid.uuid4()
    assert gateway.client.get(f"/study/{sid}").status_code == 401
    bad = {"Authorization": "Bearer not-a-jwt"}
    assert gateway.client.get(f"/study/{sid}", headers=bad).status_code == 401
    wrong_aud = mint("screener", facility, aud="someone-else")
    assert gateway.client.get(f"/study/{sid}", headers=wrong_aud).status_code == 401
    wrong_iss = mint("screener", facility, iss="https://evil.test/realms/netrasetu")
    assert gateway.client.get(f"/study/{sid}", headers=wrong_iss).status_code == 401
    expired = mint("screener", facility, exp=1_000_000, iat=999_000)
    assert gateway.client.get(f"/study/{sid}", headers=expired).status_code == 401
    unknown_kid = mint("screener", facility, kid="rotated-away")
    assert gateway.client.get(f"/study/{sid}", headers=unknown_kid).status_code == 401


def test_role_guards(gateway: Gateway, mint: Mint, facility: uuid.UUID) -> None:
    assert (
        gateway.client.get("/review/queue", headers=mint("screener", facility)).status_code == 403
    )
    both = mint(["grader", "admin"], facility, otp=True, hpr="HPR-1")
    assert gateway.client.get("/review/queue", headers=both).status_code == 403
    no_facility = mint("grader", None, otp=True, hpr="HPR-1")
    assert gateway.client.get("/review/queue", headers=no_facility).status_code == 403
    grader = mint("grader", facility, otp=True, hpr="HPR-1")
    body = {"purpose": "screening", "noticeHash": NOTICE, "language": "en"}
    assert gateway.client.post("/consent", json=body, headers=grader).status_code == 403


def test_jwks_refetched_on_unknown_kid(jwks: dict[str, Any]) -> None:
    from service.auth import UNKNOWN_KID_REFETCH_SECONDS, JwksCache

    calls = []

    def fetch() -> dict[str, Any]:
        calls.append(1)
        return jwks

    cache = JwksCache(fetch, ttl_seconds=3600)
    kid = jwks["keys"][0]["kid"]
    assert cache.get(kid) is not None and cache.get(kid) is not None
    assert len(calls) == 1
    cache._fetched_at -= UNKNOWN_KID_REFETCH_SECONDS + 1
    assert cache.get("new-kid") is None
    assert len(calls) == 2
    assert cache.get("new-kid") is None
    assert len(calls) == 2, "unknown kids must not refetch more than once per interval"


# --- review -------------------------------------------------------------------------------------


def test_review_requires_totp_and_reason_for_overturn(
    gateway: Gateway, mint: Mint, facility: uuid.UUID, screener: dict[str, str]
) -> None:
    study = _analyze(
        gateway, screener, _patient(gateway, screener), unique_png(), "grade2_haem"
    ).json()
    sid = study["studyId"]
    no_otp = mint("grader", facility, hpr="HPR-1")
    grader = mint("grader", facility, otp=True, hpr="HPR-1")

    queue = gateway.client.get("/review/queue", headers=grader).json()
    assert sid in [item["studyId"] for item in queue]

    agree = {"decision": "REFER", "grade": 2, "elapsedMs": 21000}
    assert gateway.client.post(f"/review/{sid}", json=agree, headers=no_otp).status_code == 403

    overturn = {"decision": "ROUTINE", "grade": 1, "elapsedMs": 30000}
    assert gateway.client.post(f"/review/{sid}", json=overturn, headers=grader).status_code == 422
    r = gateway.client.post(
        f"/review/{sid}", json={**overturn, "reasonChip": "lesion_miscount"}, headers=grader
    )
    assert r.status_code == 200, r.text
    assert r.json()["overturn"] is True
    assert gateway.client.post(f"/review/{sid}", json=agree, headers=grader).status_code == 409

    queue = gateway.client.get("/review/queue", headers=grader).json()
    assert sid not in [item["studyId"] for item in queue]
    metrics = gateway.client.get("/metrics").text
    assert 'netrasetu_override_total{reason="lesion_miscount"} 1.0' in metrics


def test_review_queue_puts_flagged_cases_first(
    gateway: Gateway, mint: Mint, facility: uuid.UUID, screener: dict[str, str]
) -> None:
    image = unique_png()
    _analyze(gateway, screener, _patient(gateway, screener), image, "grade2_haem")
    flagged = _analyze(gateway, screener, _patient(gateway, screener), image).json()
    queue = gateway.client.get(
        "/review/queue", headers=mint("grader", facility, otp=True, hpr="HPR-1")
    ).json()
    assert queue[0]["studyId"] == flagged["studyId"]
    assert queue[0]["flag"] == "same_image_other_patient"


# --- patient link -------------------------------------------------------------------------------


def test_patient_link_is_single_use(gateway: Gateway, screener: dict[str, str]) -> None:
    study = _analyze(
        gateway, screener, _patient(gateway, screener), unique_png(), "grade0_clean"
    ).json()
    sid = study["studyId"]
    wrong = gateway.client.post(
        f"/study/{sid}/patient-link", json={"phone": "+91 90000 00000"}, headers=screener
    )
    assert wrong.status_code == 409
    link = gateway.client.post(
        f"/study/{sid}/patient-link", json={"phone": PHONE}, headers=screener
    )
    assert link.status_code == 200, link.text
    token = link.json()["token"]

    first = gateway.client.get(f"/r/{token}")
    assert first.status_code == 200, first.text
    assert first.headers["cache-control"] == "no-store"
    assert first.json()["decision"] == "ROUTINE" and first.json()["reviewed"] is False
    assert "grade" not in first.json()
    assert gateway.client.get(f"/r/{token}").status_code == 410

    body, sig = token.split(".")
    forged = f"{body}.{sig[:-2]}AA"
    assert gateway.client.get(f"/r/{forged}").status_code == 404


def test_patient_token_expiry() -> None:
    token, tok = tokens.mint("s" * 40, uuid.uuid4(), b"\x01" * 32, lifetime_seconds=72 * 3600)
    assert tokens.verify("s" * 40, token).jti == tok.jti
    with pytest.raises(tokens.TokenExpired):
        tokens.verify("s" * 40, token, now=tok.expires_at)
    with pytest.raises(tokens.TokenInvalid):
        tokens.verify("t" * 40, token)


# --- audit --------------------------------------------------------------------------------------


def test_audit_tamper_detected_at_the_right_sequence(
    gateway: Gateway, screener: dict[str, str], admin_db: psycopg.Connection
) -> None:
    start = admin_db.execute(
        "SELECT coalesce(max(seq), 0) + 1 AS s FROM clinical.audit"
    ).fetchone()["s"]
    for _ in range(3):
        _patient(gateway, screener)
    seqs = [
        r["seq"]
        for r in admin_db.execute(
            "SELECT seq FROM clinical.audit WHERE seq >= %s ORDER BY seq", (start,)
        ).fetchall()
    ]
    assert len(seqs) >= 6
    assert audit.verify_chain(admin_db, start) is None

    target = seqs[3]
    original = admin_db.execute(
        "SELECT action FROM clinical.audit WHERE seq = %s", (target,)
    ).fetchone()["action"]
    admin_db.execute("ALTER TABLE clinical.audit DISABLE TRIGGER audit_no_update")
    try:
        admin_db.execute(
            "UPDATE clinical.audit SET action = 'consent.revoked' WHERE seq = %s", (target,)
        )
        assert audit.verify_chain(admin_db, start) == target
    finally:
        admin_db.execute("UPDATE clinical.audit SET action = %s WHERE seq = %s", (original, target))
        admin_db.execute("ALTER TABLE clinical.audit ENABLE TRIGGER audit_no_update")
    assert audit.verify_chain(admin_db, start) is None


def test_gateway_audit_rows_chain_globally(
    gateway: Gateway, mint: Mint, admin_db: psycopg.Connection
) -> None:
    start = admin_db.execute(
        "SELECT coalesce(max(seq), 0) + 1 AS s FROM clinical.audit"
    ).fetchone()["s"]
    a, b = mint("screener", uuid.uuid4()), mint("screener", uuid.uuid4())
    _patient(gateway, a)
    _patient(gateway, b)
    _patient(gateway, a)
    assert audit.verify_chain(admin_db, start) is None


# --- tiles, metrics, health, CORS, OpenAPI ------------------------------------------------------


def test_tiles_are_built_and_served(gateway: Gateway, screener: dict[str, str], mint: Mint) -> None:
    study = _analyze(gateway, screener, _patient(gateway, screener), unique_png(300)).json()
    sid = study["studyId"]
    dzi = gateway.client.get(f"/study/{sid}/tiles/image.dzi", headers=screener)
    assert dzi.status_code == 200 and b"<Image" in dzi.content
    tile = gateway.client.get(
        f"/study/{sid}/tiles/image_files/0/0_0.jpeg", headers=screener, follow_redirects=False
    )
    assert tile.status_code == 307 and tile.headers["location"].startswith("memory://tiles/")
    assert gateway.client.get(f"/study/{sid}/tiles/../secret", headers=screener).status_code == 404
    other = mint("screener", uuid.uuid4())
    assert gateway.client.get(f"/study/{sid}/tiles/image.dzi", headers=other).status_code == 404


def test_metrics_use_exact_names(gateway: Gateway, screener: dict[str, str]) -> None:
    patient = _patient(gateway, screener)
    _analyze(gateway, screener, patient, unique_png(), "underexposed")
    text = gateway.client.get("/metrics").text
    for name in (
        "netrasetu_quality_reject_total",
        "netrasetu_grade_total",
        "netrasetu_analyze_seconds",
        "netrasetu_cache_requests_total",
        "netrasetu_review_seconds",
        "netrasetu_override_total",
    ):
        assert f"# TYPE {name.removesuffix('_total')}" in text, name
    assert 'netrasetu_quality_reject_total{reason="underexposed"} 1.0' in text
    assert 'netrasetu_cache_requests_total{layer="inference",result="miss"} 1.0' in text


def test_healthz(gateway: Gateway) -> None:
    r = gateway.client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {
        "status": "ok",
        "engine": "fake",
        "engineReady": True,
        "databaseReady": True,
        "storageReady": True,
        "contractVersion": "1.1",
    }


def test_cors_allows_configured_origin(gateway: Gateway) -> None:
    r = gateway.client.options(
        "/analyze",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Idempotency-Key",
        },
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    blocked = gateway.client.options(
        "/analyze",
        headers={"Origin": "https://evil.test", "Access-Control-Request-Method": "POST"},
    )
    assert blocked.headers.get("access-control-allow-origin") is None
