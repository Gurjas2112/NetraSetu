-- Clinical tables. Pixels stay in object storage; only metadata lives here.
-- Idempotent: a failed run can be repeated before schema_migrations records the file.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS clinical;

CREATE TABLE IF NOT EXISTS clinical.patient (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    abha_hash bytea,
    facility_id uuid NOT NULL,
    phone_hash bytea,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS clinical.study (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id uuid NOT NULL REFERENCES clinical.patient (id),
    facility_id uuid NOT NULL,
    laterality text NOT NULL DEFAULT 'unknown' CHECK (laterality IN ('OD', 'OS', 'unknown')),
    sha256 bytea NOT NULL,
    -- 8-byte perceptual hash. The ER diagram's bigint cannot hold every unsigned
    -- 16-hex pHash, so the bytes are stored as-is.
    phash bytea,
    client_key uuid UNIQUE,
    device_id uuid,
    flag text CHECK (flag IS NULL OR flag IN ('same_image_other_patient', 'repeat_screening')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS study_sha256_idx ON clinical.study (sha256);
CREATE INDEX IF NOT EXISTS study_facility_idx ON clinical.study (facility_id);

CREATE TABLE IF NOT EXISTS clinical.result (
    study_id uuid PRIMARY KEY REFERENCES clinical.study (id),
    facility_id uuid NOT NULL,
    grade int CHECK (grade IS NULL OR grade BETWEEN 0 AND 4),
    posterior double precision[] CHECK (posterior IS NULL OR cardinality(posterior) = 5),
    p_referable double precision,
    llp double precision,
    model_ver text NOT NULL,
    decision text NOT NULL CHECK (decision IN ('REFER', 'ROUTINE', 'RETAKE')),
    source text NOT NULL CHECK (source IN ('matlab', 'cache')),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS clinical.review (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id uuid NOT NULL REFERENCES clinical.study (id),
    facility_id uuid NOT NULL,
    grader_hpr text NOT NULL,
    decision text NOT NULL CHECK (decision IN ('REFER', 'ROUTINE', 'RETAKE')),
    grade int CHECK (grade IS NULL OR grade BETWEEN 0 AND 4),
    reason_chip text,
    elapsed_ms int CHECK (elapsed_ms IS NULL OR elapsed_ms >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS clinical.consent (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id uuid NOT NULL REFERENCES clinical.patient (id),
    facility_id uuid NOT NULL,
    purpose text NOT NULL,
    notice_hash bytea NOT NULL,
    language text NOT NULL CHECK (language IN ('en', 'hi', 'mr')),
    granted_at timestamptz NOT NULL DEFAULT now(),
    withdrawn_at timestamptz
);

CREATE TABLE IF NOT EXISTS clinical.fhir_bundle (
    study_id uuid PRIMARY KEY REFERENCES clinical.study (id),
    facility_id uuid NOT NULL,
    bundle jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Computation cache. No patient id: a hit still creates a new study (see spec Section 26).
CREATE TABLE IF NOT EXISTS clinical.inference_cache (
    img_sha256 bytea NOT NULL,
    model_ver text NOT NULL,
    cfg_hash text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    hit_count integer NOT NULL DEFAULT 0,
    PRIMARY KEY (img_sha256, model_ver, cfg_hash)
);

CREATE TABLE IF NOT EXISTS clinical.job (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id uuid NOT NULL REFERENCES clinical.study (id),
    facility_id uuid NOT NULL,
    object_key text NOT NULL,
    status text NOT NULL,
    worker text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
