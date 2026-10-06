"""Hash-chained audit log. The chain is computed by the database trigger (002/050 migrations).

`verify_chain` recomputes every hash in SQL, so it uses exactly the trigger's jsonb text
rendering. It must run on a connection that sees every row (the admin role), because the
chain is global and the gateway only sees its own facility.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb


def append(
    conn: psycopg.Connection,
    *,
    actor: str,
    action: str,
    entity: str,
    entity_id: UUID | None,
    facility_id: UUID,
    payload: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """INSERT INTO clinical.audit (actor, action, entity, entity_id, facility_id, payload)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (actor, action, entity, entity_id, facility_id, Jsonb(payload or {})),
    )


_VERIFY_SQL = """
WITH chain AS (
    SELECT seq, prev_hash, hash,
           lag(hash) OVER (ORDER BY seq) AS expected_prev,
           sha256(convert_to(
               coalesce(encode(prev_hash, 'hex'), '')
               || '|' || actor
               || '|' || action
               || '|' || coalesce(entity, '')
               || '|' || coalesce(entity_id::text, '')
               || '|' || coalesce(facility_id::text, '')
               || '|' || coalesce(payload::text, ''),
               'UTF8')) AS recomputed
    FROM clinical.audit
)
SELECT seq FROM chain
WHERE seq >= %s
  AND (hash IS DISTINCT FROM recomputed
       OR (seq > %s AND prev_hash IS DISTINCT FROM expected_prev))
ORDER BY seq
LIMIT 1
"""


def verify_chain(conn: psycopg.Connection, start_seq: int = 1) -> int | None:
    """Return the first sequence number at or after `start_seq` whose link is broken, or None.

    The row at `start_seq` is checked against its own content; its link to the row before it is
    trusted, so verification can begin after rows written by an older trigger version.
    """
    row = conn.execute(_VERIFY_SQL, (start_seq, start_seq)).fetchone()
    if row is None:
        return None
    return row["seq"] if isinstance(row, dict) else row[0]
