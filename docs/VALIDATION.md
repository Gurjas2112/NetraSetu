# Validation report

> **Template only.** Every value in this document is filled exclusively from
> `results/validation.json`, which is produced by `eval/run_validation.m` on the evaluation
> machine. Never type a number into this file by hand.

## 1. Data and splits

- Training sources:
- Validation sources:
- Held-out test source (never touched during development):
- Split level: patient (from `data/splits.json`)
- `splits.json` hash:

## 2. Operating point

- Rule: threshold chosen on the validation set for sensitivity >= 0.90, then frozen.
- `threshold.json` hash (`cfgHash`):
- Threshold value:

## 3. Referable DR (ICDR grade 2+) on the test set

| Metric | Value | 95% CI (2,000-sample bootstrap) |
|---|---|---|
| Sensitivity | | |
| Specificity | | |

## 4. Five-grade performance

- Quadratic weighted kappa:
- Per-grade recall:
- 5x5 confusion matrix:

## 5. Calibration

| | ECE |
|---|---|
| Before temperature scaling | |
| After temperature scaling | |

## 6. Lesion localisation (IDRiD masks)

- Lesion localisation precision (LLP):

## 7. Ablation

| Configuration | Sensitivity | Specificity | QWK |
|---|---|---|---|
| Stream A only (CNN) | | | |
| Stream B only (lesion features) | | | |
| Stream A + B | | | |
| Stream A + B + C (quality), calibrated | | | |

## 8. Provenance

- `results/validation.json` hash:
- `modelVer`:
- Run date:
