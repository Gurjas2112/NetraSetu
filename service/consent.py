"""DPDP consent records. Screening without a live consent for the patient is refused."""

from __future__ import annotations

import hashlib
import hmac
import re
from uuid import UUID

import psycopg
from fastapi import HTTPException

from service import audit
from service.auth import Principal
from service.schemas import ConsentRequest, ConsentResponse

_NON_DIGITS = re.compile(r"\D")


def phone_hash(secret: str, phone: str) -> bytes:
    """Keyed hash of an Indian mobile number, so the database never holds the number."""
    digits = _NON_DIGITS.sub("", phone)
    if len(digits) == 10:
        digits = "91" + digits
    if len(digits) < 10:
        raise HTTPException(422, "phone number is too short")
    return hmac.new(secret.encode(), b"phone:" + digits.encode(), hashlib.sha256).digest()


def grant(
    conn: psycopg.Connection, principal: Principal, req: ConsentRequest, secret: str
) -> ConsentResponse:
    phash = phone_hash(secret, req.phone) if req.phone else None
    if req.patientRef is None:
        row = conn.execute(
            """INSERT INTO clinical.patient (facility_id, phone_hash) VALUES (%s, %s)
               RETURNING id""",
            (principal.facility_id, phash),
        ).fetchone()
        patient_id = row["id"]
        audit.append(
            conn,
            actor=principal.actor,
            action="patient.register",
            entity="patient",
            entity_id=patient_id,
            facility_id=principal.facility_id,
        )
    else:
        row = conn.execute(
            "SELECT id FROM clinical.patient WHERE id = %s", (req.patientRef,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, "patient not found")
        patient_id = row["id"]
        if phash is not None:
            conn.execute(
                "UPDATE clinical.patient SET phone_hash = %s WHERE id = %s", (phash, patient_id)
            )

    consent_id = conn.execute(
        """INSERT INTO clinical.consent (patient_id, facility_id, purpose, notice_hash, language)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (
            patient_id,
            principal.facility_id,
            req.purpose,
            bytes.fromhex(req.noticeHash),
            req.language,
        ),
    ).fetchone()["id"]
    audit.append(
        conn,
        actor=principal.actor,
        action="consent.grant",
        entity="consent",
        entity_id=consent_id,
        facility_id=principal.facility_id,
        payload={"purpose": req.purpose, "language": req.language, "noticeHash": req.noticeHash},
    )
    return ConsentResponse(consentId=consent_id, patientRef=patient_id)


def require_screening_consent(conn: psycopg.Connection, patient_id: UUID, consent_id: UUID) -> None:
    patient = conn.execute("SELECT 1 FROM clinical.patient WHERE id = %s", (patient_id,)).fetchone()
    if patient is None:
        raise HTTPException(404, "patient not found")
    row = conn.execute(
        """SELECT 1 FROM clinical.consent
           WHERE id = %s AND patient_id = %s AND purpose = 'screening' AND withdrawn_at IS NULL""",
        (consent_id, patient_id),
    ).fetchone()
    if row is None:
        raise HTTPException(409, "no live screening consent for this patient")
