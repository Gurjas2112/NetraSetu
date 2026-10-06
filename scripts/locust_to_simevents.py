"""Copy Locust CSV p50/p95 into the SimEvents parameter file.

Locust reports milliseconds. The District Twin Entity Server wants seconds.
This script only copies; it never invents a service time. Run it after:

    locust -f tests/load/locustfile.py --headless -u 4 -r 1 -t 5m --csv results/load

Writes results/simevents_params.json and matlab/simevents/params.json (gitignored).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "results" / "load_stats.csv"
RESULTS_OUT = ROOT / "results" / "simevents_params.json"
MATLAB_OUT = ROOT / "matlab" / "simevents" / "params.json"


def resolve_csv(path: Path) -> Path:
    """Accept either the stats file or the Locust --csv prefix (`results/load`)."""
    if path.is_file():
        return path
    prefixed = path.parent / f"{path.name}_stats.csv"
    if prefixed.is_file():
        return prefixed
    return path


def _cell(row: dict[str, str], *names: str) -> str | None:
    lower = {k.strip().lower(): v for k, v in row.items() if k is not None}
    for name in names:
        value = lower.get(name.lower())
        if value not in (None, "", "N/A", "n/a"):
            return value
    return None


def _seconds(cell: str) -> float:
    return round(float(cell) / 1000.0, 6)


def pick_row(rows: list[dict[str, str]]) -> dict[str, str]:
    for row in rows:
        if (row.get("Name") or "").strip() == "/analyze":
            return row
    for row in rows:
        if (row.get("Name") or "").strip() == "Aggregated":
            return row
    if not rows:
        raise SystemExit("Locust stats CSV has no rows")
    return rows[0]


def params_from_csv(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SystemExit(f"{path} has a header but no data rows")
    row = pick_row(rows)
    p50 = _cell(row, "50%", "Median Response Time")
    p95 = _cell(row, "95%")
    if p50 is None or p95 is None:
        raise SystemExit(f"{path} has no 50%/95% columns for {row.get('Name')!r}")
    return {
        "source": path.as_posix(),
        "name": (row.get("Name") or "").strip(),
        "requestCount": int(float(_cell(row, "Request Count") or "0")),
        "failureCount": int(float(_cell(row, "Failure Count") or "0")),
        "inferenceServiceTimeSeconds": {
            "p50": _seconds(p50),
            "p95": _seconds(p95),
        },
    }


def write_params(params: dict[str, object], *destinations: Path) -> None:
    text = json.dumps(params, indent=2) + "\n"
    for dest in destinations:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv",
        nargs="?",
        type=Path,
        default=DEFAULT_CSV,
        help="Locust stats CSV, or the --csv prefix (default: results/load_stats.csv)",
    )
    args = parser.parse_args(argv)
    csv_path = resolve_csv(args.csv)
    if not csv_path.is_file():
        print(f"missing {csv_path}; run Locust with --csv first", file=sys.stderr)
        return 1
    params = params_from_csv(csv_path)
    write_params(params, RESULTS_OUT, MATLAB_OUT)
    print(f"wrote {RESULTS_OUT.relative_to(ROOT)} and {MATLAB_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
