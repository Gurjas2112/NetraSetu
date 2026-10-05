# Contract — version 1.0

This document, [`service/schemas.py`](../service/schemas.py) and the MATLAB output of
[`netrasetu_analyze_json`](../matlab/netrasetu_analyze_json.m) must agree exactly. A change to any
one requires changing all three in the same pull request, plus `contractVersion`.

## 6.1 Engine result

`netrasetu_analyze_json(imgPath, outDir)` returns **JSON text** (a MATLAB `char` row vector),
never a struct. Pydantic model: `EngineResult`.

```jsonc
{
  "contractVersion": "1.0",
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

What the gateway returns from `POST /analyze` (and, from M3, `GET /study/{id}`). Pydantic model:
`StudyResponse`.

The engine result with these changes:

- Every `*Path` becomes a `*Url`: `gradcamPath` → `gradcamUrl`, `reportPath` → `reportUrl`,
  `evidence[].cropPath` → `evidence[].cropUrl`. From M3 these are presigned storage URLs; in M1
  they are gateway-relative `/artifacts/<studyId>/…` paths.
- Added fields: `studyId`, `patientRef` (opaque), `source` (`matlab | cache`),
  `flag` (`null | same_image_other_patient | repeat_screening`), `createdAt` (ISO 8601, UTC).
- When `flag` is `same_image_other_patient`: `grade`, `posterior`, `pReferable` and `evidence`
  are `null`, `reviewRequired` is `true`, and `decision` is `REFER` (shown to the screener
  conservatively until a reviewer signs it).
- Otherwise `evidence` is a list, never null.

## 6.3 HTTP endpoints

| Method | Path | Role | Notes | Since |
|---|---|---|---|---|
| POST | `/analyze` | screener | multipart `file` (PNG/JPEG), `patientRef`, `consentId`; header `Idempotency-Key` (UUID, required) | M1 |
| GET | `/study/{id}` | screener (own facility) · grader | 404 across facilities | M3 |
| GET | `/review/queue` | grader | sorted by severity × closeness to threshold | M3 |
| POST | `/review/{id}` | grader (TOTP) | `decision`, `grade`, `reasonChip` | M3 |
| POST | `/consent` | screener | records purpose, notice hash, language | M3 |
| GET | `/r/{token}` | none | patient view; single use → `410` on reuse | M3 |
| GET | `/metrics` | internal | Prometheus | M3 |
| GET | `/healthz` | none | engine status in M1; DB and storage from M2 | M1 |

Every response carries `Cache-Control: no-store`.

Error statuses for `/analyze`: `400` bad upload, `422` missing field or `Idempotency-Key`,
`502` engine output violated this contract, `503` grading node unavailable.

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
