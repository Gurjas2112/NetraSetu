-- Grants and forced row-level security.
-- The gateway and worker roles are created by scripts/migrate.py, which checks
-- pg_roles first. PostgreSQL rejects CREATE ROLE inside a DO block (it cannot
-- run in a transaction), so the idempotent creation lives next to the password
-- assignment, still never in a committed SQL file.

GRANT USAGE ON SCHEMA clinical TO gateway, worker;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA clinical TO gateway;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA clinical TO gateway;

GRANT SELECT, UPDATE ON clinical.job TO worker;
GRANT SELECT, INSERT, UPDATE ON clinical.inference_cache TO worker;

REVOKE UPDATE, DELETE, TRUNCATE ON clinical.audit FROM gateway, worker;
GRANT INSERT, SELECT ON clinical.audit TO gateway;

ALTER TABLE clinical.patient ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinical.patient FORCE ROW LEVEL SECURITY;
ALTER TABLE clinical.study ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinical.study FORCE ROW LEVEL SECURITY;
ALTER TABLE clinical.result ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinical.result FORCE ROW LEVEL SECURITY;
ALTER TABLE clinical.review ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinical.review FORCE ROW LEVEL SECURITY;
ALTER TABLE clinical.consent ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinical.consent FORCE ROW LEVEL SECURITY;
ALTER TABLE clinical.audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinical.audit FORCE ROW LEVEL SECURITY;
ALTER TABLE clinical.fhir_bundle ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinical.fhir_bundle FORCE ROW LEVEL SECURITY;

-- clinical.job has no facility policy. The worker claims jobs for every facility
-- and has no grant on patient, study, result, review or consent.

DROP POLICY IF EXISTS facility_isolation ON clinical.patient;
CREATE POLICY facility_isolation ON clinical.patient
    USING (facility_id = current_setting('app.facility_id')::uuid)
    WITH CHECK (facility_id = current_setting('app.facility_id')::uuid);

DROP POLICY IF EXISTS facility_isolation ON clinical.study;
CREATE POLICY facility_isolation ON clinical.study
    USING (facility_id = current_setting('app.facility_id')::uuid)
    WITH CHECK (facility_id = current_setting('app.facility_id')::uuid);

DROP POLICY IF EXISTS facility_isolation ON clinical.result;
CREATE POLICY facility_isolation ON clinical.result
    USING (facility_id = current_setting('app.facility_id')::uuid)
    WITH CHECK (facility_id = current_setting('app.facility_id')::uuid);

DROP POLICY IF EXISTS facility_isolation ON clinical.review;
CREATE POLICY facility_isolation ON clinical.review
    USING (facility_id = current_setting('app.facility_id')::uuid)
    WITH CHECK (facility_id = current_setting('app.facility_id')::uuid);

DROP POLICY IF EXISTS facility_isolation ON clinical.consent;
CREATE POLICY facility_isolation ON clinical.consent
    USING (facility_id = current_setting('app.facility_id')::uuid)
    WITH CHECK (facility_id = current_setting('app.facility_id')::uuid);

DROP POLICY IF EXISTS facility_isolation ON clinical.audit;
CREATE POLICY facility_isolation ON clinical.audit
    USING (facility_id = current_setting('app.facility_id')::uuid)
    WITH CHECK (facility_id = current_setting('app.facility_id')::uuid);

DROP POLICY IF EXISTS facility_isolation ON clinical.fhir_bundle;
CREATE POLICY facility_isolation ON clinical.fhir_bundle
    USING (facility_id = current_setting('app.facility_id')::uuid)
    WITH CHECK (facility_id = current_setting('app.facility_id')::uuid);
