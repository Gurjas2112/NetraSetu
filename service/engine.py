"""Engine adapters. Every engine returns contract 6.1 as JSON text, never a struct.

`FakeEngine` is deterministic and keyed by the fixture name (file stem) so that every test and
demo runs without MATLAB. `MatlabEngine` connects to a shared MATLAB session started with
`matlab.engine.shareEngine("netrasetu")`.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any, Protocol

from service.schemas import CONTRACT_VERSION
from service.settings import Settings

MODEL_VER = "netrasetu_v1"


class EngineUnavailable(RuntimeError):
    """The grading engine cannot be reached or failed to run."""


class Engine(Protocol):
    name: str

    def ready(self) -> bool: ...

    def analyze_json(self, img_path: Path, out_dir: Path) -> str: ...


def cfg_hash(threshold_path: Path) -> str:
    return "sha256:" + hashlib.sha256(threshold_path.read_bytes()).hexdigest()


_FAKE_EMPTY_FHIR: dict[str, Any] = {"resourceType": "Bundle", "type": "collection", "entry": []}

_RETAKE_BY_PREFIX: tuple[tuple[str, str, str], ...] = (
    ("blur_", "defocus", "retake.defocus.hold_steady"),
    ("underexposed", "underexposed", "retake.underexposed.nasal"),
    ("partial_fov", "partial_fov", "retake.partial_fov.centre"),
)

# Fake, fixed posteriors. These are stand-ins for the contract shape, not model outputs.
_GRADED_BY_PREFIX: tuple[tuple[str, int, list[float], list[dict[str, Any]]], ...] = (
    ("grade0_", 0, [0.90, 0.07, 0.02, 0.007, 0.003], []),
    (
        "grade2_",
        2,
        [0.02, 0.07, 0.61, 0.24, 0.06],
        [
            {
                "key": "icdr.l2.haemorrhages_multi_quadrant",
                "grade": 2,
                "detail": {"count": 12, "quadrants": 3},
            }
        ],
    ),
    (
        "grade4_",
        4,
        [0.01, 0.02, 0.07, 0.20, 0.70],
        [
            {"key": "icdr.l3.haemorrhages_four_quadrants", "grade": 3, "detail": {"quadrants": 4}},
            {"key": "icdr.l4.nv_proxy", "grade": 4, "detail": {"proxy": True}},
        ],
    ),
)

# Anything unrecognised is treated as uncertain and referred.
_UNKNOWN_POSTERIOR = [0.15, 0.20, 0.35, 0.20, 0.10]


class FakeEngine:
    name = "fake"

    def __init__(self, threshold_path: Path) -> None:
        self._threshold_path = threshold_path

    def ready(self) -> bool:
        return self._threshold_path.is_file()

    def analyze_json(self, img_path: Path, out_dir: Path) -> str:
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = img_path.stem.lower()
        digest = hashlib.sha256(img_path.read_bytes()).hexdigest()
        base: dict[str, Any] = {
            "contractVersion": CONTRACT_VERSION,
            "modelVer": MODEL_VER,
            "cfgHash": cfg_hash(self._threshold_path),
        }
        quality = {"verdict": "accept", "score": 0.92, "failureMode": "none", "phash": digest[:16]}

        for prefix, failure_mode, guidance_key in _RETAKE_BY_PREFIX:
            if stem.startswith(prefix):
                result = {
                    **base,
                    "decision": "RETAKE",
                    "reviewRequired": False,
                    "quality": {
                        **quality,
                        "verdict": "reject",
                        "score": 0.21,
                        "failureMode": failure_mode,
                    },
                    "retakeGuidanceKey": guidance_key,
                    "grade": None,
                    "posterior": None,
                    "pReferable": None,
                    "laterality": "unknown",
                    "criteria": [],
                    "evidence": [],
                    "gradcamPath": None,
                    "llp": None,
                    "reportPath": None,
                    "fhirBundle": _FAKE_EMPTY_FHIR,
                }
                return json.dumps(result)

        grade, posterior, criteria = 2, _UNKNOWN_POSTERIOR, []
        for prefix, g, p, c in _GRADED_BY_PREFIX:
            if stem.startswith(prefix):
                grade, posterior, criteria = g, p, c
                break

        decision = "ROUTINE" if grade <= 1 else "REFER"
        result = {
            **base,
            "decision": decision,
            "reviewRequired": decision == "REFER",
            "quality": quality,
            "retakeGuidanceKey": None,
            "grade": grade,
            "posterior": posterior,
            "pReferable": posterior[2] + posterior[3] + posterior[4],
            "laterality": "unknown",
            "criteria": criteria,
            "evidence": [],
            "gradcamPath": None,
            "llp": None,
            "reportPath": None,
            "fhirBundle": _FAKE_EMPTY_FHIR,
        }
        return json.dumps(result)


class MatlabEngine:
    """Adapter for a shared MATLAB session. One call at a time, guarded by a lock."""

    name = "matlab"

    def __init__(self, shared_name: str, nx_root: Path) -> None:
        self._shared_name = shared_name
        self._nx_root = nx_root
        self._lock = threading.Lock()
        self._eng: Any = None

    def _connect(self) -> Any:
        if self._eng is not None:
            return self._eng
        try:
            import matlab.engine  # type: ignore[import-not-found]
        except ImportError as exc:
            raise EngineUnavailable("matlabengine is not installed") from exc
        try:
            eng = matlab.engine.connect_matlab(self._shared_name)
            eng.addpath(str(self._nx_root), nargout=0)
            eng.addpath(str(self._nx_root / "nx"), nargout=0)
            eng.eval("jsonencode(nx_version());", nargout=0)
        except Exception as exc:  # the engine raises several unrelated error types
            raise EngineUnavailable(
                f"cannot connect to shared MATLAB {self._shared_name!r}"
            ) from exc
        self._eng = eng
        return eng

    def warm_up(self) -> None:
        with self._lock:
            self._connect()

    def ready(self) -> bool:
        try:
            self.warm_up()
        except EngineUnavailable:
            return False
        return True

    def analyze_json(self, img_path: Path, out_dir: Path) -> str:
        out_dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            eng = self._connect()
            try:
                txt = eng.netrasetu_analyze_json(str(img_path), str(out_dir), nargout=1)
            except Exception as exc:
                self._eng = None
                raise EngineUnavailable("MATLAB analysis failed") from exc
        return str(txt)


def build_engine(settings: Settings) -> Engine:
    if settings.engine == "matlab":
        return MatlabEngine(settings.matlab_shared_engine, settings.nx_root)
    return FakeEngine(settings.threshold_path)
