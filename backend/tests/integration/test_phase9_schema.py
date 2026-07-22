"""Fase-9 audit identity schema against the real Alembic chain."""

import pytest
from sqlalchemy import text

from tests.conftest import _get_test_engine, use_migrations

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.migration_schema,
    pytest.mark.skipif(not use_migrations(), reason="requires the migrated schema"),
]


async def test_phase9_audit_identity_columns_and_index_exist(setup_database) -> None:
    expected_columns = {
        "identity_provider_id",
        "session_id",
        "factor_verification_age",
    }
    async with _get_test_engine().connect() as connection:
        columns = set(
            (
                await connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name='audit_log'"
                    )
                )
            ).scalars()
        )
        indexes = set(
            (
                await connection.execute(
                    text(
                        "SELECT indexname FROM pg_indexes "
                        "WHERE schemaname='public' AND tablename='audit_log'"
                    )
                )
            ).scalars()
        )

    assert expected_columns <= columns
    assert "ix_audit_log_tenant_identity_timestamp" in indexes


async def test_phase9_keeps_audit_rows_immutable(setup_database) -> None:
    async with _get_test_engine().connect() as connection:
        trigger_count = int(
            (
                await connection.execute(
                    text(
                        "SELECT count(*) FROM pg_trigger t "
                        "JOIN pg_class c ON c.oid=t.tgrelid "
                        "WHERE c.relname='audit_log' AND NOT t.tgisinternal"
                    )
                )
            ).scalar_one()
        )
    assert trigger_count >= 1
