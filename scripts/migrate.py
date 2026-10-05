"""Apply platform/migrations in order, once each, on every tier.

Connects with ADMIN_DATABASE_URL. Role passwords come from GATEWAY_DB_PASSWORD and
WORKER_DB_PASSWORD and are applied with psycopg.sql, never written into SQL files.

Usage: python scripts/migrate.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "platform" / "migrations"
ROLES = ("gateway", "worker")


def _has_sql(text: str) -> bool:
    without_block = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    without_line = re.sub(r"--.*?$", "", without_block, flags=re.M)
    return bool(without_line.strip())


def split_sql(script: str) -> list[str]:
    """Split a SQL file on semicolons, keeping dollar-quoted function bodies intact."""
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(script)
    dollar: str | None = None
    in_single = False
    in_line = False
    in_block = False
    while i < n:
        ch = script[i]
        nxt = script[i + 1] if i + 1 < n else ""
        if in_line:
            buf.append(ch)
            if ch == "\n":
                in_line = False
            i += 1
            continue
        if in_block:
            buf.append(ch)
            if ch == "*" and nxt == "/":
                buf.append(nxt)
                i += 2
                in_block = False
                continue
            i += 1
            continue
        if dollar is not None:
            if script.startswith(dollar, i):
                buf.append(dollar)
                i += len(dollar)
                dollar = None
                continue
            buf.append(ch)
            i += 1
            continue
        if in_single:
            buf.append(ch)
            if ch == "'" and nxt == "'":
                buf.append(nxt)
                i += 2
                continue
            if ch == "'":
                in_single = False
            i += 1
            continue
        if ch == "-" and nxt == "-":
            buf.append(ch)
            in_line = True
            i += 1
            continue
        if ch == "/" and nxt == "*":
            buf.append(ch)
            in_block = True
            i += 1
            continue
        if ch == "'":
            buf.append(ch)
            in_single = True
            i += 1
            continue
        if ch == "$":
            match = re.match(r"\$[A-Za-z0-9_]*\$", script[i:])
            if match:
                dollar = match.group(0)
                buf.append(dollar)
                i += len(dollar)
                continue
        if ch == ";":
            text = "".join(buf).strip()
            if _has_sql(text):
                statements.append(text)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if _has_sql(tail):
        statements.append(tail)
    return statements


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is not set")
    return value


def ensure_roles(db: psycopg.Connection) -> None:
    for role in ROLES:
        exists = db.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
        if exists:
            db.execute(sql.SQL("ALTER ROLE {} LOGIN NOBYPASSRLS").format(sql.Identifier(role)))
        else:
            db.execute(sql.SQL("CREATE ROLE {} LOGIN NOBYPASSRLS").format(sql.Identifier(role)))


def set_passwords(db: psycopg.Connection) -> None:
    for role in ROLES:
        password = _require(f"{role.upper()}_DB_PASSWORD")
        db.execute(
            sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(role), sql.Literal(password))
        )


def apply(db: psycopg.Connection) -> int:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS public.schema_migrations (
            filename text PRIMARY KEY,
            applied_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    applied = {row[0] for row in db.execute("SELECT filename FROM public.schema_migrations")}
    count = 0
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.name in applied:
            continue
        for statement in split_sql(path.read_text(encoding="utf-8")):
            db.execute(statement)
        db.execute("INSERT INTO public.schema_migrations (filename) VALUES (%s)", (path.name,))
        print("applied", path.name)
        count += 1
    if count == 0:
        print("applied nothing")
    return count


def main() -> None:
    admin_url = _require("ADMIN_DATABASE_URL")
    with psycopg.connect(admin_url, autocommit=True) as db:
        ensure_roles(db)
        apply(db)
        set_passwords(db)


if __name__ == "__main__":
    try:
        main()
    except psycopg.Error as exc:
        print(f"migration failed: {exc}", file=sys.stderr)
        sys.exit(1)
