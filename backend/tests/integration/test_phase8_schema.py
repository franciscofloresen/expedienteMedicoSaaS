"""Fase-8 additive performance schema against the real Alembic chain."""

import pytest
from sqlalchemy import text

from tests.conftest import _get_test_engine, use_migrations

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.migration_schema,
    pytest.mark.skipif(not use_migrations(), reason="requires the migrated schema"),
]


async def test_phase8_indexes_and_rollback_columns_exist(setup_database) -> None:
    expected = {
        "ix_notas_expediente_creado_id",
        "ix_consentimientos_expediente_creado_id",
        "ix_pacientes_nombre_trgm",
        "ix_pacientes_curp_trgm",
        "ix_pacientes_telefono_trgm",
    }
    async with _get_test_engine().connect() as connection:
        indexes = set(
            (
                await connection.execute(
                    text(
                        "SELECT indexname FROM pg_indexes "
                        "WHERE schemaname='public' AND indexname LIKE 'ix_%'"
                    )
                )
            ).scalars()
        )
        legacy_columns = set(
            (
                await connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name='tenants'"
                    )
                )
            ).scalars()
        )
    assert expected <= indexes
    assert {"nombre_medico", "cedula", "especialidad"} <= legacy_columns
