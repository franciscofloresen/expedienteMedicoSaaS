"""Unified in-production verification contract for the admin Lambda.

Each roadmap phase that adds a trigger, RLS policy, backfill or catalog import
registers a **read-only** verifier here. The deployed Lambda dispatches
``{"verify": "<action>"}`` to :func:`run_verify`, and the parametrized
``ops-verify.yml`` workflow invokes it after a deploy. This is the production
half of the safety net (the CI migration job is the pre-deploy half): the
migration ran, but did it produce the RLS/triggers/rows we intended?

Contract for every verifier:

* **Read-only.** It runs against production, so it must never write. (The
  write-based ``scripts/verify_rls.py`` deliberately refuses to run in prod;
  this module is what runs there.)
* Returns a uniform envelope via :func:`_envelope`::

      {"ok": bool, "action": str,
       "checks":   [{"name": str, "ok": bool, "detail": str}, ...],
       "warnings": [str, ...],   # deviations that don't fail the gate
       "counts":   {str: int}}   # e.g. row counts after an import

* **No PHI.** Only structural facts and aggregate counts — never patient data.

Adding a phase verifier = add an ``async def verify_<phase>()`` and one line in
``_VERIFIERS``.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import text

# Clinical tables that MUST carry FORCE ROW LEVEL SECURITY per §1.2 of the
# roadmap (they hold NOM-004 clinical documents). RLS still applies to the
# non-owner app role without FORCE, so a missing FORCE is a defense-in-depth
# warning, not an active isolation hole — hence a warning, not a failed check.
_FORCE_EXPECTED = {
    "pacientes",
    "expedientes",
    "notas",
    "consentimientos",
    "recetas",
    "citas",
    "clinical_files",
    "tenant_storage_usage",
    "medicos",
    "medico_credenciales",
}

# Records the app role must never hard-delete: the clinical record and its
# documents (NOM-004 §5.14 conservation) plus the verification tokens that anchor
# signed-document integrity (NOM-024). A granted DELETE here is a regression (it
# happened when later migrations did GRANT ALL). This is a hard check.
_DELETE_PROTECTED = {
    "pacientes",
    "expedientes",
    "notas",
    "consentimientos",
    "recetas",
    "verification_tokens",
    # Fase 1: a credential used in a signed document is deactivated, never deleted;
    # the médico identity behind signed documents must likewise survive (§5.1).
    "medicos",
    "medico_credenciales",
}


def _check(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail}


def _envelope(
    action: str,
    checks: list[dict[str, Any]],
    warnings: list[str] | None = None,
    counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "ok": all(c["ok"] for c in checks),
        "action": action,
        "checks": checks,
        "warnings": warnings or [],
        "counts": counts or {},
    }


async def verify_rls() -> dict[str, Any]:
    """Assert tenant isolation is actually active on every tenant-scoped table.

    Read-only structural check against pg_catalog. A table is tenant-scoped iff it
    has a ``tenant_id`` column; for each, RLS must be enabled and at least one
    policy must exist (that is what makes isolation real for the app role). Missing
    FORCE on a clinical table is reported as a warning.
    """
    from app.db.session import _get_session_factory

    factory = _get_session_factory()
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    async with factory() as session, session.begin():
        tenant_tables = [
            r[0]
            for r in (
                await session.execute(
                    text(
                        """
                        SELECT table_name
                        FROM information_schema.columns
                        WHERE column_name = 'tenant_id' AND table_schema = 'public'
                        ORDER BY table_name
                        """
                    )
                )
            ).all()
        ]

        checks.append(
            _check("tenant tables discovered", len(tenant_tables) > 0, f"{tenant_tables}")
        )

        for table in tenant_tables:
            rls_row = (
                await session.execute(
                    text(
                        """
                        SELECT relrowsecurity, relforcerowsecurity
                        FROM pg_class
                        WHERE relname = :t AND relnamespace = 'public'::regnamespace
                        """
                    ),
                    {"t": table},
                )
            ).first()
            policy_count = (
                await session.execute(
                    text(
                        "SELECT count(*) FROM pg_policies "
                        "WHERE schemaname = 'public' AND tablename = :t"
                    ),
                    {"t": table},
                )
            ).scalar_one()

            rls_enabled = bool(rls_row and rls_row[0])
            forced = bool(rls_row and rls_row[1])

            checks.append(
                _check(
                    f"{table}: RLS enabled with a policy",
                    rls_enabled and policy_count >= 1,
                    f"rls_enabled={rls_enabled}, policies={policy_count}",
                )
            )
            if table in _FORCE_EXPECTED and not forced:
                warnings.append(
                    f"{table}: clinical table lacks FORCE ROW LEVEL SECURITY "
                    "(§1.2 defense-in-depth; RLS still applies to the app role)"
                )

        # NOM-004 §5.14: final clinical documents must not be app-deletable.
        for table in sorted(_DELETE_PROTECTED):
            if table not in tenant_tables:
                continue
            app_can_delete = (
                await session.execute(
                    text("SELECT has_table_privilege('medrecord_app', :t, 'DELETE')"),
                    {"t": table},
                )
            ).scalar_one()
            checks.append(
                _check(
                    f"{table}: app role cannot DELETE (retention/integrity)",
                    not app_can_delete,
                    f"medrecord_app has DELETE={app_can_delete}",
                )
            )

    return _envelope("rls", checks, warnings=warnings)


async def _table_rls_checks(session: Any, table: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Structural RLS/force/delete checks for one tenant-scoped table (read-only)."""
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    rls_row = (
        await session.execute(
            text(
                """
                SELECT relrowsecurity, relforcerowsecurity
                FROM pg_class
                WHERE relname = :t AND relnamespace = 'public'::regnamespace
                """
            ),
            {"t": table},
        )
    ).first()
    policy_count = (
        await session.execute(
            text(
                "SELECT count(*) FROM pg_policies "
                "WHERE schemaname = 'public' AND tablename = :t"
            ),
            {"t": table},
        )
    ).scalar_one()
    rls_enabled = bool(rls_row and rls_row[0])
    forced = bool(rls_row and rls_row[1])

    checks.append(
        _check(
            f"{table}: RLS enabled with a policy",
            rls_enabled and policy_count >= 1,
            f"rls_enabled={rls_enabled}, policies={policy_count}",
        )
    )
    if table in _FORCE_EXPECTED and not forced:
        warnings.append(
            f"{table}: clinical table lacks FORCE ROW LEVEL SECURITY (§1.2 defense-in-depth)"
        )
    if table in _DELETE_PROTECTED:
        app_can_delete = (
            await session.execute(
                text("SELECT has_table_privilege('medrecord_app', :t, 'DELETE')"),
                {"t": table},
            )
        ).scalar_one()
        checks.append(
            _check(
                f"{table}: app role cannot DELETE (retention/integrity)",
                not app_can_delete,
                f"medrecord_app has DELETE={app_can_delete}",
            )
        )
    return checks, warnings


async def verify_medicos() -> dict[str, Any]:
    """Fase 1: médicos + credenciales landed with isolation, protection and backfill.

    Read-only, no PHI (structural facts + aggregate counts only). Runs against
    production after the Fase 1 deploy. Confirms:

    * ``medicos`` / ``medico_credenciales`` have RLS + policy + no app DELETE.
    * Backfill completeness: every tenant has a médico; every tenant with a cédula
      has a default-active credential.
    * ``tenants.cedula`` stays in lockstep with the default credential's normalized
      number (§1.3), so onboarding's uniqueness check and ``release_cedula`` keep working.

    Note: aggregate counts span all tenants, so this must run as the RLS-bypassing
    connection role (the same one ``verify_rls`` uses — not demoted to medrecord_app).
    """
    from app.db.session import _get_session_factory

    factory = _get_session_factory()
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    async with factory() as session, session.begin():
        for table in ("medicos", "medico_credenciales"):
            tchecks, twarn = await _table_rls_checks(session, table)
            checks.extend(tchecks)
            warnings.extend(twarn)

        counts = {
            "tenants": (
                await session.execute(text("SELECT count(*) FROM tenants"))
            ).scalar_one(),
            "medicos": (
                await session.execute(text("SELECT count(*) FROM medicos"))
            ).scalar_one(),
            "credenciales": (
                await session.execute(text("SELECT count(*) FROM medico_credenciales"))
            ).scalar_one(),
            "credenciales_predeterminadas": (
                await session.execute(
                    text(
                        "SELECT count(*) FROM medico_credenciales "
                        "WHERE es_predeterminada AND activa"
                    )
                )
            ).scalar_one(),
        }

        tenants_sin_medico = (
            await session.execute(
                text(
                    "SELECT count(*) FROM tenants t "
                    "WHERE NOT EXISTS (SELECT 1 FROM medicos m WHERE m.tenant_id = t.id)"
                )
            )
        ).scalar_one()
        checks.append(
            _check(
                "every tenant has a médico (backfill complete)",
                tenants_sin_medico == 0,
                f"tenants without médico={tenants_sin_medico}",
            )
        )

        # A tenant with a real cédula must have a default-active credential.
        cedula_sin_credencial = (
            await session.execute(
                text(
                    """
                    SELECT count(*) FROM tenants t
                    JOIN medicos m ON m.tenant_id = t.id
                    WHERE coalesce(t.cedula, '') <> ''
                      AND NOT EXISTS (
                          SELECT 1 FROM medico_credenciales c
                          WHERE c.medico_id = m.id AND c.es_predeterminada AND c.activa
                      )
                    """
                )
            )
        ).scalar_one()
        checks.append(
            _check(
                "every tenant with a cédula has a default credential",
                cedula_sin_credencial == 0,
                f"tenants missing default credential={cedula_sin_credencial}",
            )
        )

        # §1.3 sync: tenants.cedula == default credential's normalized number.
        cedula_desincronizada = (
            await session.execute(
                text(
                    """
                    SELECT count(*) FROM tenants t
                    JOIN medicos m ON m.tenant_id = t.id
                    JOIN medico_credenciales c
                      ON c.medico_id = m.id AND c.es_predeterminada AND c.activa
                    WHERE coalesce(t.cedula, '') <> ''
                      AND c.numero_normalizado
                          <> upper(regexp_replace(coalesce(t.cedula, ''), '\\s+', '', 'g'))
                    """
                )
            )
        ).scalar_one()
        checks.append(
            _check(
                "tenants.cedula in sync with default credential (§1.3)",
                cedula_desincronizada == 0,
                f"out-of-sync tenants={cedula_desincronizada}",
            )
        )

    return _envelope("medicos", checks, warnings=warnings, counts=counts)


# action name → verifier coroutine. Each phase appends one entry.
_VERIFIERS: dict[str, Callable[[], Awaitable[dict[str, Any]]]] = {
    "rls": verify_rls,
    "medicos": verify_medicos,
}


def available_actions() -> list[str]:
    return sorted(_VERIFIERS)


def run_verify(action: str) -> dict[str, Any]:
    """Sync entry point for the Lambda handler. Dispatches and runs the verifier.

    Returns the verifier's envelope, or an ``ok=False`` envelope for an unknown
    action. Never raises for an unknown action (the handler maps ``ok`` to the
    HTTP status).
    """
    verifier = _VERIFIERS.get(action)
    if verifier is None:
        return _envelope(
            action,
            [
                _check(
                    "known action",
                    False,
                    f"unknown verify action {action!r}; available: {available_actions()}",
                )
            ],
        )

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(verifier())
