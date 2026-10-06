-- Queue-mode jobs (M6). The worker claims across facilities and never reads study/result.
-- study_id stays null until the gateway materialises a study from the inference cache.

ALTER TABLE clinical.job
    ALTER COLUMN study_id DROP NOT NULL;

ALTER TABLE clinical.job
    ADD COLUMN IF NOT EXISTS claimed_at timestamptz,
    ADD COLUMN IF NOT EXISTS error text,
    ADD COLUMN IF NOT EXISTS attempts integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS img_sha256 bytea,
    ADD COLUMN IF NOT EXISTS model_ver text,
    ADD COLUMN IF NOT EXISTS cfg_hash text,
    ADD COLUMN IF NOT EXISTS filename text,
    ADD COLUMN IF NOT EXISTS content_type text,
    ADD COLUMN IF NOT EXISTS client_key uuid;

CREATE UNIQUE INDEX IF NOT EXISTS job_client_key
    ON clinical.job (client_key)
    WHERE client_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS job_queued_created
    ON clinical.job (created_at)
    WHERE status = 'queued';
