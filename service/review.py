"""Grader queue and sign-off. Every overturn needs a reason chip: the active-learning label."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import psycopg
from fastapi import HTTPException

from service import audit
from service.auth import Principal
from service.metrics import Metrics
from service.schemas import ReviewQueueItem, ReviewRequest, ReviewResponse

QUEUE_LIMIT = 50

_QUEUE_SQL = """
SELECT s.id, s.created_at, s.flag, r.decision, r.grade, r.p_referable
FROM clinical.study AS s
JOIN clinical.result AS r ON r.study_id = s.id
WHERE ((r.payload->>'reviewRequired')::boolean OR s.flag IS NOT NULL)
  AND NOT EXISTS (SELECT 1 FROM clinical.review AS v WHERE v.study_id = s.id)
ORDER BY (s.flag IS NOT NULL) DESC, {order}, s.created_at
LIMIT %(limit)s
"""

# Severity times closeness to the referral threshold; ungraded (flagged) cases rank as grade 4.
_ORDER_WITH_THRESHOLD = (
    "coalesce(r.grade, 4) * (1 - abs(coalesce(r.p_referable, %(t)s) - %(t)s)) DESC"
)
# No validated threshold yet: most severe first, then most probable.
_ORDER_WITHOUT_THRESHOLD = "coalesce(r.grade, 4) DESC, r.p_referable DESC NULLS FIRST"


def read_threshold(path: Path) -> float | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get("threshold")
    except (OSError, ValueError):
        return None
    return float(value) if isinstance(value, int | float) else None


def queue(conn: psycopg.Connection, threshold: float | None) -> list[ReviewQueueItem]:
    order = _ORDER_WITHOUT_THRESHOLD if threshold is None else _ORDER_WITH_THRESHOLD
    rows = conn.execute(
        _QUEUE_SQL.format(order=order), {"t": threshold, "limit": QUEUE_LIMIT}
    ).fetchall()
    return [
        ReviewQueueItem(
            studyId=r["id"],
            createdAt=r["created_at"],
            decision=r["decision"],
            grade=r["grade"],
            pReferable=r["p_referable"],
            flag=r["flag"],
        )
        for r in rows
    ]


def sign(
    conn: psycopg.Connection,
    principal: Principal,
    study_id: UUID,
    req: ReviewRequest,
    metrics: Metrics,
) -> ReviewResponse:
    if not principal.hpr_id:
        raise HTTPException(403, "grader account has no HPR ID")
    row = conn.execute(
        """SELECT r.decision, r.grade FROM clinical.study AS s
           JOIN clinical.result AS r ON r.study_id = s.id WHERE s.id = %s""",
        (study_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "study not found")
    if conn.execute("SELECT 1 FROM clinical.review WHERE study_id = %s", (study_id,)).fetchone():
        raise HTTPException(409, "study has already been reviewed")
    if req.decision == "ROUTINE" and (req.grade is None or req.grade > 1):
        raise HTTPException(422, "ROUTINE requires a grade of 0 or 1")
    if req.decision == "RETAKE" and req.grade is not None:
        raise HTTPException(422, "an ungradeable image has no grade")

    overturn = req.decision != row["decision"] or (
        req.grade is not None and row["grade"] is not None and req.grade != row["grade"]
    )
    if overturn and req.reasonChip is None:
        raise HTTPException(422, "an overturn requires a reason chip")

    review_id = conn.execute(
        """INSERT INTO clinical.review
               (study_id, facility_id, grader_hpr, decision, grade, reason_chip, elapsed_ms)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (
            study_id,
            principal.facility_id,
            principal.hpr_id,
            req.decision,
            req.grade,
            req.reasonChip,
            req.elapsedMs,
        ),
    ).fetchone()["id"]
    audit.append(
        conn,
        actor=principal.actor,
        action="review.sign",
        entity="study",
        entity_id=study_id,
        facility_id=principal.facility_id,
        payload={
            "reviewId": str(review_id),
            "decision": req.decision,
            "grade": req.grade,
            "overturn": overturn,
            "reasonChip": req.reasonChip,
        },
    )
    if req.elapsedMs is not None:
        metrics.review_seconds.observe(req.elapsedMs / 1000)
    if overturn:
        metrics.override.labels(req.reasonChip).inc()
    return ReviewResponse(
        reviewId=review_id,
        studyId=study_id,
        decision=req.decision,
        grade=req.grade,
        overturn=overturn,
    )
