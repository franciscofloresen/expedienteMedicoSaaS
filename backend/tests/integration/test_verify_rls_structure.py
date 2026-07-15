"""In-prod-style structural RLS verifier, run against the REAL migrated schema.

Only meaningful in migration mode: create_all builds a simplified, partial RLS
setup, so the check is skipped there and runs in the CI migration job
(TEST_SCHEMA_MODE=migrations), the same path the production ops-verify workflow
exercises.
"""

import pytest

from scripts.verify_registry import verify_rls
from tests.conftest import use_migrations

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.migration_schema,
    pytest.mark.skipif(
        not use_migrations(),
        reason="structural RLS check requires the migrated schema",
    ),
]


async def test_verify_rls_passes_on_migrated_schema(setup_database) -> None:
    result = await verify_rls()

    # Every tenant-scoped table has RLS enabled with a policy → the gate passes.
    failed = [c for c in result["checks"] if not c["ok"]]
    assert result["ok"] is True, f"failing checks: {failed}"
    assert result["action"] == "rls"

    # Documents the known §1.2 FORCE drift: consentimientos and recetas are
    # clinical tables whose FORCE ROW LEVEL SECURITY was lost when a later
    # migration recreated them. These are warnings (not failures) because RLS
    # still applies to the non-owner app role. When the drift is fixed, this
    # assertion flips and this test becomes the regression guard.
    warned_tables = " ".join(result["warnings"])
    assert "consentimientos" in warned_tables
    assert "recetas" in warned_tables
