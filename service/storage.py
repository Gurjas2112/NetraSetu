"""Object storage for pixels and derived artefacts (Garage at Tier 0, Supabase Storage at Tier 1).

Presigned GET URLs are reused while they have at least a fifth of their lifetime left, so a
browser revisiting a study hits its own cache instead of downloading the image again.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Protocol

from service.settings import S3Settings

PRESIGN_CACHE_SIZE = 10_000


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def presign(self, key: str) -> str: ...

    def ready(self) -> bool: ...


class _PresignCache:
    def __init__(self, ttl_seconds: int, clock=time.monotonic) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._urls: OrderedDict[str, tuple[str, float]] = OrderedDict()

    def get_or_create(self, key: str, create) -> str:
        now = self._clock()
        with self._lock:
            hit = self._urls.get(key)
            if hit and now - hit[1] < self._ttl * 0.8:
                self._urls.move_to_end(key)
                return hit[0]
        url = create(key, self._ttl)
        with self._lock:
            self._urls[key] = (url, now)
            self._urls.move_to_end(key)
            while len(self._urls) > PRESIGN_CACHE_SIZE:
                self._urls.popitem(last=False)
        return url


class S3Storage:
    def __init__(self, cfg: S3Settings, presign_ttl_seconds: int) -> None:
        import boto3
        from botocore.config import Config

        self._bucket = cfg.bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=cfg.endpoint,
            region_name=cfg.region,
            aws_access_key_id=cfg.access_key,
            aws_secret_access_key=cfg.secret_key,
            config=Config(
                s3={"addressing_style": "path"},
                signature_version="s3v4",
                connect_timeout=5,
                read_timeout=30,
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
        self._presigned = _PresignCache(presign_ttl_seconds)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return False
            raise
        return True

    def _sign(self, key: str, ttl: int) -> str:
        return self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=ttl
        )

    def presign(self, key: str) -> str:
        return self._presigned.get_or_create(key, self._sign)

    def ready(self) -> bool:
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            self._client.head_bucket(Bucket=self._bucket)
        except (BotoCoreError, ClientError):
            return False
        return True


class MemoryStorage:
    """In-process storage for tests and offline demos. URLs are not fetchable."""

    def __init__(self, presign_ttl_seconds: int = 3600) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self._presigned = _PresignCache(presign_ttl_seconds)
        self._counter = 0

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    def get(self, key: str) -> bytes:
        return self.objects[key][0]

    def exists(self, key: str) -> bool:
        return key in self.objects

    def _sign(self, key: str, ttl: int) -> str:
        self._counter += 1
        return f"memory://{key}?sig={self._counter}&ttl={ttl}"

    def presign(self, key: str) -> str:
        return self._presigned.get_or_create(key, self._sign)

    def ready(self) -> bool:
        return True
