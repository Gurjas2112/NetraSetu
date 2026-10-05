-- Hash-chained, append-only audit log. The trigger computes the chain;
-- callers insert actor, action and payload only.

CREATE TABLE IF NOT EXISTS clinical.audit (
    seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor text NOT NULL,
    action text NOT NULL,
    entity text,
    entity_id uuid,
    facility_id uuid,
    payload jsonb,
    prev_hash bytea,
    hash bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION clinical.audit_hash_chain() RETURNS trigger
LANGUAGE plpgsql AS $$
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
    NEW.hash := digest(convert_to(material, 'UTF8'), 'sha256');
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS audit_hash_chain ON clinical.audit;
CREATE TRIGGER audit_hash_chain
BEFORE INSERT ON clinical.audit
FOR EACH ROW EXECUTE FUNCTION clinical.audit_hash_chain();

CREATE OR REPLACE FUNCTION clinical.audit_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'clinical.audit is append-only';
END;
$$;

DROP TRIGGER IF EXISTS audit_no_update ON clinical.audit;
CREATE TRIGGER audit_no_update
BEFORE UPDATE OR DELETE ON clinical.audit
FOR EACH ROW EXECUTE FUNCTION clinical.audit_append_only();

DROP TRIGGER IF EXISTS audit_no_truncate ON clinical.audit;
CREATE TRIGGER audit_no_truncate
BEFORE TRUNCATE ON clinical.audit
FOR EACH STATEMENT EXECUTE FUNCTION clinical.audit_append_only();
