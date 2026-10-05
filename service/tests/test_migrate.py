"""SQL splitting used by scripts/migrate.py. No database required."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("migrate", ROOT / "scripts" / "migrate.py")
assert spec and spec.loader
migrate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migrate)


def test_split_keeps_function_body() -> None:
    script = (ROOT / "platform" / "migrations" / "002_audit.sql").read_text(encoding="utf-8")
    statements = migrate.split_sql(script)
    functions = [s for s in statements if "CREATE OR REPLACE FUNCTION" in s]
    assert len(functions) == 2
    assert all(s.count("$$") == 2 for s in functions)
    assert any("RAISE EXCEPTION 'clinical.audit is append-only'" in s for s in functions)


def test_split_does_not_drop_statements_that_start_with_a_comment() -> None:
    statements = migrate.split_sql("-- header\nCREATE EXTENSION IF NOT EXISTS pgcrypto;\n")
    assert len(statements) == 1
    assert "CREATE EXTENSION" in statements[0]


def test_semicolons_inside_comments_stay_in_the_statement() -> None:
    statements = migrate.split_sql(
        (ROOT / "platform" / "migrations" / "001_schema.sql").read_text(encoding="utf-8")
    )
    assert any("storage; only metadata" in statement for statement in statements)
    assert any("CREATE EXTENSION" in statement for statement in statements)
