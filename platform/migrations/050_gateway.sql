-- Gateway support (M3).
--
-- SECURITY DEFINER functions run as the migration owner. Under FORCE ROW LEVEL SECURITY that
-- owner must bypass RLS (a superuser locally, the BYPASSRLS `postgres` role on Supabase), so
-- each function answers one narrow question and never returns rows from another facility.

ALTER TABLE clinical.study ADD COLUMN IF NOT EXISTS image_key text;

-- The chain is global, so the previous hash must be read past the caller's facility policy.
-- sha256() is built in, which keeps the function independent of where pgcrypto is installed.
CREATE OR REPLACE FUNCTION clinical.audit_hash_chain() RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, clinical
AS $$
DECLARE
    prev bytea;
    material text;
BEGIN
    IF NEW.hash IS NOT NULL OR NEW.prev_hash IS NOT NULL THEN
        RAISE EXCEPTION 'audit hash columns are computed by the chain trigger';
    END IF;
    PERFORM pg_advisory_xact_lock(26038);
    SELECT a.hash INTO prev FROM clinical.audit AS a ORDER BY a.seq DESC LIMIT 1;
    NEW.prev_hash := prev;
    material := coalesce(encode(prev, 'hex'), '')
        || '|' || NEW.actor
        || '|' || NEW.action
        || '|' || coalesce(NEW.entity, '')
        || '|' || coalesce(NEW.entity_id::text, '')
        || '|' || coalesce(NEW.facility_id::text, '')
        || '|' || coalesce(NEW.payload::text, '');
    NEW.hash := sha256(convert_to(material, 'UTF8'));
    RETURN NEW;
END;
$$;

-- Same pixels under a different patient anywhere in the programme. Returns a boolean only.
CREATE OR REPLACE FUNCTION clinical.image_seen_for_other_patient(p_sha bytea, p_patient uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, clinical
AS $$
    SELECT EXISTS (
        SELECT 1 FROM clinical.study AS s WHERE s.sha256 = p_sha AND s.patient_id <> p_patient
    );
$$;

CREATE TABLE IF NOT EXISTS clinical.patient_token (
    jti uuid PRIMARY KEY,
    study_id uuid NOT NULL REFERENCES clinical.study (id),
    facility_id uuid NOT NULL,
    phone_hash bytea NOT NULL,
    expires_at timestamptz NOT NULL,
    used_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE clinical.patient_token ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinical.patient_token FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS facility_isolation ON clinical.patient_token;
CREATE POLICY facility_isolation ON clinical.patient_token
    USING (facility_id = current_setting('app.facility_id')::uuid)
    WITH CHECK (facility_id = current_setting('app.facility_id')::uuid);

GRANT SELECT, INSERT ON clinical.patient_token TO gateway;

-- The patient has no facility claim, so redemption cannot run under the facility policy.
-- Marks the token used and returns where the study lives; 'gone' for used or expired tokens.
CREATE OR REPLACE FUNCTION clinical.redeem_patient_token(p_jti uuid, p_phone_hash bytea)
RETURNS TABLE (status text, study_id uuid, facility_id uuid)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, clinical
AS $$
DECLARE
    t clinical.patient_token%ROWTYPE;
BEGIN
    SELECT * INTO t FROM clinical.patient_token AS pt WHERE pt.jti = p_jti FOR UPDATE;
    IF NOT FOUND OR t.phone_hash <> p_phone_hash THEN
        RETURN QUERY SELECT 'unknown'::text, NULL::uuid, NULL::uuid;
        RETURN;
    END IF;
    IF t.used_at IS NOT NULL OR t.expires_at <= now() THEN
        RETURN QUERY SELECT 'gone'::text, t.study_id, t.facility_id;
        RETURN;
    END IF;
    UPDATE clinical.patient_token AS pt SET used_at = now() WHERE pt.jti = p_jti;
    RETURN QUERY SELECT 'ok'::text, t.study_id, t.facility_id;
END;
$$;

REVOKE ALL ON FUNCTION clinical.image_seen_for_other_patient(bytea, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION clinical.redeem_patient_token(uuid, bytea) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION clinical.image_seen_for_other_patient(bytea, uuid) TO gateway;
GRANT EXECUTE ON FUNCTION clinical.redeem_patient_token(uuid, bytea) TO gateway;
