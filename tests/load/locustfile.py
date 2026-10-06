"""Screener load: POST /analyze with a unique image each time so the inference cache misses.

The engine serialises MATLAB (or FakeEngine) calls, so this measures single-server service
time. Feed the Locust CSV into scripts/locust_to_simevents.py — do not type the percentiles.

    locust -f tests/load/locustfile.py --headless -u 4 -r 1 -t 5m --csv results/load --host http://127.0.0.1:8000

Requires LOCUST_ACCESS_TOKEN (a screener bearer token) and tests/fixtures/grade2_haem.png.
Run against GATEWAY_MODE=inprocess; queue mode returns 503 and does not time the engine.
"""

from __future__ import annotations

import hashlib
import itertools
import os
import sys
import uuid
from pathlib import Path

from locust import HttpUser, between, task

_LOAD_DIR = Path(__file__).resolve().parent
if str(_LOAD_DIR) not in sys.path:
    sys.path.insert(0, str(_LOAD_DIR))
from images import unique_png  # noqa: E402

ROOT = _LOAD_DIR.parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "grade2_haem.png"
NOTICE = hashlib.sha256(b"screening notice v1").hexdigest()
_SEQ = itertools.count()


def _token() -> str:
    token = os.environ.get("LOCUST_ACCESS_TOKEN", "").strip()
    if not token:
        raise RuntimeError("set LOCUST_ACCESS_TOKEN to a screener bearer token")
    return token if token.lower().startswith("bearer ") else f"Bearer {token}"


class Screener(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        if not FIXTURE.is_file():
            raise RuntimeError("run python scripts/make_fixtures.py first")
        self._png = FIXTURE.read_bytes()
        self._auth = {"Authorization": _token()}
        r = self.client.post(
            "/consent",
            json={"purpose": "screening", "noticeHash": NOTICE, "language": "hi"},
            headers=self._auth,
            name="/consent",
        )
        if r.status_code != 200:
            raise RuntimeError(f"consent failed: {r.status_code} {r.text[:200]}")
        body = r.json()
        self._patient = body["patientRef"]
        self._consent = body["consentId"]

    @task
    def analyze(self) -> None:
        image = unique_png(self._png, next(_SEQ))
        self.client.post(
            "/analyze",
            files={"file": ("grade2_haem.png", image, "image/png")},
            data={"patientRef": self._patient, "consentId": self._consent},
            headers={"Idempotency-Key": str(uuid.uuid4()), **self._auth},
            name="/analyze",
        )
