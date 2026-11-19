import os
import secrets
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import URL, create_engine, inspect, insert, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError, OperationalError

from app.db.models import Account, Base, ExchangeOrder, Member, Product, RedemptionCredential

BACKEND = Path(__file__).resolve().parents[1]
FROZEN_SQL = BACKEND.parent / "sql" / "database-v1.sql"
REVISION = "0001_frozen_schema"
SNAPSHOT = BACKEND / "alembic" / "versions" / f"{REVISION}.sql"


def test_frozen_revision_snapshot() -> None:
    assert SNAPSHOT.read_text(encoding="utf-8") == FROZEN_SQL.read_text(encoding="utf-8")
    assert len(Base.metadata.tables) == 18
    assert sum(len(table.columns) for table in Base.metadata.tables.values()) == 186


@pytest.fixture
def isolated_postgres() -> Iterator[tuple[Engine, Engine, Engine]]:
    if os.environ.get("SUNSHINE_TEST_POSTGRES") != "1":
        pytest.skip("Set SUNSHINE_TEST_POSTGRES=1 to start a disposable PostgreSQL 16 container")

    password = secrets.token_urlsafe(24)
    container = subprocess.check_output(
        [
            "docker", "run", "--rm", "-d", "-p", "127.0.0.1::5432",
            "-e", "POSTGRES_PASSWORD", "-e", "POSTGRES_DB=sunshine_migration_test", "postgres:16",
        ],
        env={**os.environ, "POSTGRES_PASSWORD": password},
        text=True,
        timeout=120,
    ).strip()

    engines: list[Engine] = []
    try:
        port = int(subprocess.check_output(
            ["docker", "port", container, "5432/tcp"], text=True, timeout=15,
        ).strip().rsplit(":", 1)[1])
        url = URL.create(
            "postgresql+psycopg", username="postgres", password=password,
            host="127.0.0.1", port=port, database="sunshine_migration_test",
        )
        engine = create_engine(url, connect_args={"connect_timeout": 2})
        engines.append(engine)
        deadline = time.monotonic() + 45
        while True:
            try:
                with engine.connect() as connection:
                    version = int(connection.exec_driver_sql("SHOW server_version_num").scalar_one())
                break
            except OperationalError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.5)
        assert 160000 <= version < 170000
        print(f"Isolated PostgreSQL server_version_num={version}")

        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.exec_driver_sql("CREATE DATABASE sunshine_ddl_reference")
            connection.exec_driver_sql("CREATE DATABASE sunshine_orm_reference")
        reference = create_engine(url.set(database="sunshine_ddl_reference"))
        orm = create_engine(url.set(database="sunshine_orm_reference"))
        engines.extend((reference, orm))
        yield engine, reference, orm
    finally:
        for engine in engines:
            engine.dispose()
        subprocess.run(["docker", "stop", container], check=True, capture_output=True, timeout=30)


def run_alembic(engine: Engine, *arguments: str) -> str:
    url = engine.url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BACKEND,
        env={
            **os.environ,
            "POSTGRES_HOST": str(url.host),
            "POSTGRES_PORT": str(url.port),
            "POSTGRES_DB": str(url.database),
            "POSTGRES_USER": str(url.username),
            "POSTGRES_PASSWORD": str(url.password),
            "BUSINESS_TIMEZONE": "Asia/Shanghai",
            "PYTHONIOENCODING": "utf-8",
        },
        capture_output=True, encoding="utf-8", timeout=45,
    )
    assert result.returncode == 0, result.stderr.replace(str(url.password), "[redacted]")
    return result.stdout


def read_schema(connection: Connection) -> dict[str, list[tuple]]:
    # Use PostgreSQL's canonical definitions, including index predicates, INCLUDE,
    # column order, server defaults, FK actions, and trigger/function bodies.
    queries = {
        "tables": """
            SELECT c.relname FROM pg_class c
            WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'r'
              AND c.relname <> 'alembic_version' ORDER BY 1
        """,
        "columns": """
            SELECT c.relname, a.attnum, a.attname, format_type(a.atttypid, a.atttypmod),
                   a.attnotnull, pg_get_expr(d.adbin, d.adrelid)
            FROM pg_class c JOIN pg_attribute a ON a.attrelid = c.oid
            LEFT JOIN pg_attrdef d ON d.adrelid = c.oid AND d.adnum = a.attnum
            WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'r'
              AND c.relname <> 'alembic_version' AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY 1, 2
        """,
        "constraints": """
            SELECT c.relname, p.conname, p.contype, pg_get_constraintdef(p.oid)
            FROM pg_constraint p JOIN pg_class c ON c.oid = p.conrelid
            WHERE c.relnamespace = 'public'::regnamespace AND c.relname <> 'alembic_version'
            ORDER BY 1, 2
        """,
        "indexes": """
            SELECT c.relname, i.relname, pg_get_indexdef(x.indexrelid)
            FROM pg_index x JOIN pg_class c ON c.oid = x.indrelid
            JOIN pg_class i ON i.oid = x.indexrelid
            WHERE c.relnamespace = 'public'::regnamespace AND c.relname <> 'alembic_version'
              AND NOT EXISTS (SELECT FROM pg_constraint p
                              WHERE p.conindid = x.indexrelid AND p.contype IN ('p', 'u'))
            ORDER BY 1, 2
        """,
        "triggers": """
            SELECT c.relname, t.tgname, pg_get_triggerdef(t.oid), t.tgenabled
            FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
            WHERE c.relnamespace = 'public'::regnamespace AND NOT t.tgisinternal
            ORDER BY 1, 2
        """,
        "functions": """
            SELECT p.proname, pg_get_functiondef(p.oid) FROM pg_proc p
            WHERE p.pronamespace = 'public'::regnamespace ORDER BY 1, 2
        """,
    }
    return {
        name: [tuple(row) for row in connection.exec_driver_sql(query)]
        for name, query in queries.items()
    }


def assert_ledger_triggers(connection: Connection) -> None:
    for table in ("points_records", "product_stock_records"):
        for sql in (
            f"UPDATE {table} SET reason = NULL WHERE false",
            f"DELETE FROM {table} WHERE false",
            f"TRUNCATE {table}",
        ):
            with pytest.raises(DBAPIError) as caught, connection.begin_nested():
                connection.exec_driver_sql(sql)
            assert getattr(caught.value.orig, "sqlstate", None) == "55000"
            assert f"Ledger {table} is append-only" in str(caught.value.orig)


def assert_redemption_constraints(connection: Connection) -> None:
    issued_at = datetime(2026, 11, 19, 4, tzinfo=UTC)
    expires_at = issued_at + timedelta(minutes=2)
    account_id = connection.execute(insert(Account).returning(Account.id)).scalar_one()
    member_id = connection.execute(insert(Member).values(
        account_id=account_id, member_no="test-member", name="Test Member",
        birthday=date(2000, 1, 1), phone_ciphertext=b"test", phone_search_hash=b"test",
        register_source="direct",
    ).returning(Member.id)).scalar_one()
    product_id = connection.execute(insert(Product).values(
        name="Test Product", points_price=1,
    ).returning(Product.id)).scalar_one()
    order_id = connection.execute(insert(ExchangeOrder).values(
        order_no="test-order", member_id=member_id, product_id=product_id,
        product_snapshot={}, points_cost_total=1, idempotency_key="test-request",
        request_fingerprint=bytes(32), created_at=issued_at,
    ).returning(ExchangeOrder.id)).scalar_one()
    issue = insert(RedemptionCredential).values(
        exchange_order_id=order_id, issued_at=issued_at, expires_at=expires_at,
    ).returning(RedemptionCredential.id)
    first = connection.execute(issue.values(token_hash=b"a" * 32)).scalar_one()
    with pytest.raises(DBAPIError, match="uq_credentials_unclosed_order"), connection.begin_nested():
        connection.execute(issue.values(token_hash=b"b" * 32))

    consume = update(RedemptionCredential).values(
        consumed_at=issued_at + timedelta(seconds=1), consumed_by_account_id=account_id,
    )
    connection.execute(consume.where(RedemptionCredential.id == first))
    second = connection.execute(issue.values(token_hash=b"b" * 32)).scalar_one()
    with pytest.raises(DBAPIError, match="uq_credentials_consumed_order"), connection.begin_nested():
        connection.execute(consume.where(RedemptionCredential.id == second))


def test_upgrade_rollback_and_schema_parity(isolated_postgres: tuple[Engine, Engine, Engine]) -> None:
    migrated, reference, orm = isolated_postgres
    with reference.begin() as connection:
        connection.exec_driver_sql(FROZEN_SQL.read_text(encoding="utf-8"), execution_options={"no_parameters": True})
        expected = read_schema(connection)
    assert len(expected["tables"]) == 18
    assert len(expected["columns"]) == 186
    assert Counter(row[2] for row in expected["constraints"]) == {"p": 18, "f": 32, "c": 18, "u": 19}
    assert len(expected["indexes"]) == 23
    assert len(expected["triggers"]) == 2
    assert [row[0] for row in expected["functions"]] == ["reject_ledger_mutation"]

    with orm.begin() as connection:
        Base.metadata.create_all(connection)
        orm_schema = read_schema(connection)
    for section in ("tables", "columns", "constraints", "indexes"):
        assert orm_schema[section] == expected[section], section

    offline_sql = run_alembic(migrated, "upgrade", "head", "--sql")
    assert "RAISE EXCEPTION 'Ledger % is append-only'" in offline_sql
    assert "CREATE TRIGGER stock_records_append_only" in offline_sql

    run_alembic(migrated, "upgrade", "head")
    assert REVISION in run_alembic(migrated, "current")
    run_alembic(migrated, "check")
    run_alembic(migrated, "upgrade", "head")
    with migrated.connect() as connection:
        assert read_schema(connection) == expected
        assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalars().all() == [REVISION]
        assert_ledger_triggers(connection)
        assert_redemption_constraints(connection)

    run_alembic(migrated, "downgrade", "base")
    with migrated.connect() as connection:
        assert all(not objects for objects in read_schema(connection).values())
        assert inspect(connection).get_table_names(schema="public") == ["alembic_version"]
        assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").first() is None

    run_alembic(migrated, "upgrade", "head")
    assert REVISION in run_alembic(migrated, "current")
    with migrated.connect() as connection:
        assert read_schema(connection) == expected
