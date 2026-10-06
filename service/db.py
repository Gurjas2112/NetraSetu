"""Database access for the gateway role. Every clinical transaction is scoped to one facility.

Row-level security reads `app.facility_id`; it is set with `set_config(..., true)`, the
function form of `SET LOCAL`, so it can never outlive the transaction that set it.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

import psycopg
from psycopg.rows import dict_row


class Database:
    def __init__(self, url: str, connect_timeout: int = 5) -> None:
        self._url = url
        self._connect_timeout = connect_timeout

    def _connect(self) -> psycopg.Connection[dict]:
        return psycopg.connect(
            self._url, row_factory=dict_row, connect_timeout=self._connect_timeout
        )

    @contextmanager
    def transaction(self, facility_id: UUID) -> Iterator[psycopg.Connection[dict]]:
        with self._connect() as conn, conn.transaction():
            conn.execute("SELECT set_config('app.facility_id', %s, true)", (str(facility_id),))
            yield conn

    @contextmanager
    def unscoped(self) -> Iterator[psycopg.Connection[dict]]:
        """For SECURITY DEFINER calls and health checks only; RLS still denies table reads."""
        with self._connect() as conn, conn.transaction():
            yield conn

    def ready(self) -> bool:
        try:
            with self.unscoped() as conn:
                conn.execute("SELECT 1")
        except psycopg.Error:
            return False
        return True
