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

    # Regression guard for the §1.2 FORCE drift fixed in migration 45fd65e2a92f:
    # consentimientos and recetas are clinical tables that had lost FORCE ROW
    # LEVEL SECURITY when later migrations recreated them. They must now be forced,
    # so no FORCE warning should mention them (and, given every clinical table is
    # forced, there should be no FORCE warnings at all).
    warned_tables = " ".join(result["warnings"])
    assert "consentimientos" not in warned_tables, result["warnings"]
    assert "recetas" not in warned_tables, result["warnings"]
    assert result["warnings"] == [], result["warnings"]

    # Regression guard for NOM-004 §5.14 delete-protection (migration 5eb13dab23be):
    # recetas and consentimientos must be delete-protected like notas. If a future
    # migration re-grants DELETE, the corresponding check flips to ok=False.
    delete_checks = {
        c["name"]: c["ok"] for c in result["checks"] if "cannot DELETE" in c["name"]
    }
    assert any("recetas" in n for n in delete_checks)
    assert any("consentimientos" in n for n in delete_checks)
    assert all(delete_checks.values()), delete_checks
