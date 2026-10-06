"""Presigned URL reuse, and a round trip through the real S3 endpoint when one is configured."""

from __future__ import annotations

import os
import urllib.request
import uuid

import pytest

from service.settings import S3Settings
from service.storage import S3Storage, _PresignCache


def test_presigned_urls_are_reused_for_most_of_their_lifetime() -> None:
    now = [0.0]
    signed: list[str] = []

    def sign(key: str, ttl: int) -> str:
        signed.append(key)
        return f"{key}#{len(signed)}"

    cache = _PresignCache(3600, clock=lambda: now[0])
    first = cache.get_or_create("raw/a.png", sign)
    now[0] = 2000
    assert cache.get_or_create("raw/a.png", sign) == first
    now[0] = 3000
    assert cache.get_or_create("raw/a.png", sign) != first
    assert len(signed) == 2


@pytest.fixture
def s3() -> S3Storage:
    if not os.environ.get("S3_ACCESS_KEY") or not os.environ.get("S3_SECRET_KEY"):
        pytest.skip("S3 credentials are not set")
    cfg = S3Settings(
        endpoint=os.environ["S3_ENDPOINT"],
        region=os.environ.get("S3_REGION", "garage"),
        bucket=os.environ["S3_BUCKET"],
        access_key=os.environ["S3_ACCESS_KEY"],
        secret_key=os.environ["S3_SECRET_KEY"],
    )
    storage = S3Storage(cfg, presign_ttl_seconds=600)
    if not storage.ready():
        pytest.skip("S3 endpoint is not reachable")
    return storage


def test_s3_round_trip_and_presigned_get(s3: S3Storage) -> None:
    key = f"test/{uuid.uuid4()}.bin"
    data = os.urandom(1024)
    assert not s3.exists(key)
    s3.put(key, data, "application/octet-stream")
    assert s3.exists(key)
    assert s3.get(key) == data
    url = s3.presign(key)
    assert s3.presign(key) == url
    with urllib.request.urlopen(url, timeout=10) as resp:
        assert resp.read() == data
