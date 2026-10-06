"""Prometheus metrics. Names must match AGENTS.md 6.4 exactly; Grafana dashboards depend on them.

Each app owns its registry, so test apps never collide on duplicate registration.
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST

__all__ = ["CONTENT_TYPE_LATEST", "Metrics"]


class Metrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.quality_reject = Counter(
            "netrasetu_quality_reject_total",
            "Images rejected by the quality gate",
            ["reason"],
            registry=self.registry,
        )
        self.grade = Counter(
            "netrasetu_grade_total",
            "Grades issued",
            ["grade", "decision"],
            registry=self.registry,
        )
        self.analyze_seconds = Histogram(
            "netrasetu_analyze_seconds",
            "Engine pipeline time per image",
            buckets=(0.25, 0.5, 1, 2, 4, 8, 16, 32, 64),
            registry=self.registry,
        )
        self.cache_requests = Counter(
            "netrasetu_cache_requests_total",
            "Idempotency and inference cache lookups",
            ["layer", "result"],
            registry=self.registry,
        )
        self.review_seconds = Histogram(
            "netrasetu_review_seconds",
            "Time a grader spent on one case",
            buckets=(5, 10, 15, 21, 30, 45, 60, 120, 300),
            registry=self.registry,
        )
        self.override = Counter(
            "netrasetu_override_total",
            "Grader overturns of the engine decision",
            ["reason"],
            registry=self.registry,
        )

    def render(self) -> bytes:
        return generate_latest(self.registry)
