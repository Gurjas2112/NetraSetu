# Contract — version 1.1

This document, [`service/schemas.py`](../service/schemas.py) and the MATLAB output of
[`netrasetu_analyze_json`](../matlab/netrasetu_analyze_json.m) must agree exactly. A change to any
one requires changing all three in the same pull request, plus `contractVersion`.

**1.1 (M3):** a `same_image_other_patient` study whose image failed the quality gate is served
as `RETAKE` (with its guidance key) instead of being impossible to represent; 6.1 is unchanged
apart from the version string. Inference-cache entries from another contract version are
treated as misses.

## 6.1 Engine result

`netrasetu_analyze_json(imgPath, outDir)` returns **JSON text** (a MATLAB `char` row vector),
never a struct. Pydantic model: `EngineResult`.

```jsonc
{
  "contractVersion": "1.1",
  "modelVer": "netrasetu_v1",            // from nx_config
  "cfgHash": "sha256:<64 hex>",          // sha256 of the raw bytes of matlab/config/threshold.json
  "decision": "REFER | ROUTINE | RETAKE",
  "reviewRequired": true,                 // true for every REFER and every uncertain case
  "quality": {
    "verdict": "accept | enhance | reject",
    "score": 0.0,                         // 0–1
    "failureMode": "none | defocus | underexposed | overexposed | partial_fov | media_opacity",
    "phash": "16-hex-chars"               // lowercase
  },
  "retakeGuidanceKey": "retake.underexposed.nasal",   // RETAKE only; otherwise null
  "grade": 2,                             // 0–4; null when RETAKE
  "posterior": [0.02, 0.07, 0.61, 0.24, 0.06],        // length 5, sums to 1 ± 1e-6; null when RETAKE
  "pReferable": 0.91,                     // = posterior[2] + posterior[3] + posterior[4]; null when posterior is null
  "laterality": "OD | OS | unknown",
  "criteria": [
    { "key": "icdr.l2.haemorrhages_multi_quadrant", "grade": 2,
      "detail": { "count": 14, "quadrants": 3 } }
  ],
  "evidence": [
    { "type": "MA | HE | EX | SE | NV_PROXY",
      "x": 1532.4, "y": 988.7,            // sub-pixel centroid, original-image pixels
      "quadrant": "ST | SN | IT | IN",
      "distanceToFoveaDD": 1.4,           // disc diameters; null if fovea not found
      "cropPath": "<outDir>/ev/03.png",   // 200×200 native-resolution crop
      "criterionKey": "icdr.l2.haemorrhages_multi_quadrant" }   // or null
  ],
  "gradcamPath": "<outDir>/gradcam.png",  // or null when not produced (always null for RETAKE)
  "llp": 0.84,                            // lesion localisation precision; null if unknown
  "reportPath": "<outDir>/report.pdf",    // or null when not produced
  "fhirBundle": { }                       // FHIR R4 Bundle, NRCeS profiles
}
```

### Validation rules (enforced by `EngineResult`)

| Rule | Applies to |
|---|---|
| No fields other than those above (`extra = forbid`) | all |
| `posterior` has 5 entries in [0, 1] summing to 1 ± 1e-6 | when present |
| `pReferable` equals `posterior[2] + posterior[3] + posterior[4]` ± 1e-6; null iff `posterior` is null | all |
| `grade`, `posterior`, `pReferable` are null; `retakeGuidanceKey` is present and matches `retake.<mode>[.<detail>]` | `RETAKE` |
| `quality.verdict` is `reject` with a `failureMode` other than `none` | `RETAKE` |
| `retakeGuidanceKey` is null and `quality.verdict` is not `reject` | `REFER`, `ROUTINE` |
| `grade` and `posterior` are present | `REFER`, `ROUTINE` |
| `reviewRequired` is `true` | `REFER` |
| `grade` is 0 or 1 | `ROUTINE` |
| `evidence` is a list (possibly empty), never null | all |

### MATLAB encoding notes

- Null fields are set to `NaN` in MATLAB; `jsonencode` writes `NaN` as `null`.
- Empty lists use empty struct arrays (`struct("key", {}, ...)`), which encode as `[]`.
- A 1×1 struct encodes as an object, not a one-element array. When `criteria` or `evidence`
  has exactly one element, the pipeline must still emit a JSON array (M4 must handle this,
  for example by encoding the list as a cell array of structs).

## 6.2 API study

What the gateway returns from `POST /analyze` and `GET /study/{id}`. Pydantic model:
`StudyResponse`.

The engine result with these changes:

- Every `*Path` becomes a `*Url`: `gradcamPath` → `gradcamUrl`, `reportPath` → `reportUrl`,
  `evidence[].cropPath` → `evidence[].cropUrl`. These are presigned storage URLs, reused while
  at least a fifth of `PRESIGN_TTL_SECONDS` remains so browsers can cache the bytes.
- Added fields: `studyId`, `patientRef` (the patient UUID from `POST /consent`), `source`
  (`matlab | cache`), `flag` (`null | same_image_other_patient | repeat_screening`), `createdAt`
  (ISO 8601, UTC).
- When `flag` is `same_image_other_patient` (the same pixels already exist under a different
  patient, in any facility): `grade`, `posterior`, `pReferable`, `llp` and `evidence` are `null`,
  `criteria` is empty, `fhirBundle` is an empty collection, `reviewRequired` is `true`, and
  `decision` is `REFER`, or `RETAKE` when the image failed the quality gate. It is never
  `ROUTINE`.
- Otherwise `evidence` is a list, never null.
- `repeat_screening` is reserved; the gateway does not set it yet.

### Analyze order (spec Section 26)

1. **Idempotency.** The same `Idempotency-Key` within `IDEMPOTENCY_TTL_DAYS` returns the
   original study. The same key for a different patient, or after the TTL, is `409`.
2. **Consent.** The patient must have a live `screening` consent matching `consentId`, else `409`.
3. **Cross-patient check** (sets the flag above).
4. **Inference cache**, keyed by image sha256, `modelVer` and `cfgHash`. A hit still creates a new
   study, with `source = cache` in the response and in the audit trail.
5. **Engine** on a miss. With `NX_CACHED_MODE=true` a miss is `503`
   `{"status":"queued","reason":"grading node unavailable"}` and nothing is stored.
   With `GATEWAY_MODE=queue` a miss uploads the pixels under `inbox/`, inserts
   `clinical.job`, and returns the same `503`. A Pattern B worker (`python -m service.worker`)
   claims the job with `FOR UPDATE SKIP LOCKED`, writes `inference_cache` only (the worker
   role has no grant on study/result), and the client's retry materialises the study with
   `source = cache`.

## 6.3 HTTP endpoints

| Method | Path | Role | Notes | Since |
|---|---|---|---|---|
| POST | `/analyze` | screener | multipart `file` (PNG/JPEG), `patientRef`, `consentId`; header `Idempotency-Key` (UUID, required) | M1 |
| GET | `/study/{id}` | screener (own facility) · grader | 404 across facilities | M3 |
| GET | `/study/{id}/tiles/image.dzi` | screener · grader | Deep Zoom descriptor (XML); `404` until tiles are built | M3 |
| GET | `/study/{id}/tiles/image_files/{level}/{x}_{y}.jpeg` | screener · grader | `307` to a presigned tile URL | M3 |
| POST | `/study/{id}/patient-link` | screener | `phone` must match the number given at consent; returns a 72 h single-use `token` | M3 |
| GET | `/review/queue` | grader | unreviewed `reviewRequired` or flagged studies; flagged first, then severity × closeness to threshold | M3 |
| POST | `/review/{id}` | grader (TOTP) | `decision`, `grade`, `reasonChip`, `elapsedMs`; an overturn without `reasonChip` is `422` | M3 |
| POST | `/consent` | screener | `purpose`, `noticeHash` (sha256 hex of the notice shown), `language`, optional `phone`; omit `patientRef` to register a new patient | M3 |
| GET | `/r/{token}` | none | patient view (`PatientView`: decision, never a grade); single use → `410` on reuse or expiry | M3 |
| GET | `/metrics` | internal | Prometheus text format | M3 |
| GET | `/healthz` | none | engine, database and storage readiness | M1 |

Every response carries `Cache-Control: no-store`.

Authentication: `Authorization: Bearer <access token>` from the `netrasetu` Keycloak realm,
verified against the realm JWKS (`RS256`, issuer `OIDC_ISSUER`, audience `OIDC_AUDIENCE`).
Claims used: `realm_access.roles`, `facility_id` (required; scopes every query through row-level
security), `hpr_id` (required to sign a review) and `amr` (must contain `otp` to sign a review).
A token carrying both `grader` and `admin` is refused.

Error statuses for `/analyze`: `400` bad upload, `401` missing or invalid token, `403` wrong role
or no facility, `404` unknown patient, `409` consent or idempotency conflict, `422` missing field
or `Idempotency-Key`, `502` engine output violated this contract, `503` grading node unavailable.

## 6.4 Metric names

Must match exactly; Grafana dashboards depend on them.

`netrasetu_quality_reject_total{reason}` · `netrasetu_grade_total{grade,decision}` ·
`netrasetu_analyze_seconds` (histogram) · `netrasetu_cache_requests_total{layer,result}` ·
`netrasetu_review_seconds` (histogram) · `netrasetu_override_total{reason}`

## Fake engine (`GATEWAY_ENGINE=fake`)

Deterministic outcomes keyed by the uploaded file name (stem, case-insensitive):

| Stem | Decision | Failure mode | Guidance key |
|---|---|---|---|
| `blur_*` | RETAKE | `defocus` | `retake.defocus.hold_steady` |
| `underexposed*` | RETAKE | `underexposed` | `retake.underexposed.nasal` |
| `partial_fov*` | RETAKE | `partial_fov` | `retake.partial_fov.centre` |
| `grade0_*` | ROUTINE | `none` | — |
| `grade2_*`, `grade4_*` | REFER | `none` | — |
| anything else | REFER (uncertain, review required) | `none` | — |

Fake posteriors are fixed placeholders for the contract shape, not model outputs.
