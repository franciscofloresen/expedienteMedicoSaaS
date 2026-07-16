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
import os
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

# A recovery point must exist and be no older than this for the 5-year archive to
# be considered healthy. The plan is monthly (~31 days), so 40 days tolerates one
# late/slow job while still catching the exact failure mode of the old incident:
# the pipeline was "alive in code" but produced zero objects for months.
_BACKUP_MAX_AGE_DAYS = 40

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
    # Fase 2: a clinical encounter is clinical evidence — RLS FORCE + never deletable.
    "encuentros_clinicos",
    # Fase 3: a structured diagnosis is clinical evidence attached to a note.
    "nota_diagnosticos",
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
    # Fase 2: an encuentro is cancelled (estado), never physically removed (§5.1).
    "encuentros_clinicos",
    # Fase 3: a diagnosis is corrected with a new version/state, never deleted (§5.3).
    "nota_diagnosticos",
}

# The full CIE-10 catalog is ~14.5k rows; require a comfortable floor so a truncated or
# never-run import is caught (the empty-catalog failure mode the search silently degrades on).
_CIE10_MIN_ROWS = 10000


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


async def verify_encuentros() -> dict[str, Any]:
    """Fase 2: encuentros_clinicos landed with isolation, delete-protection and the
    one-primera_vez invariant intact.

    Read-only, no PHI (structural facts + aggregate counts only). Runs against
    production after the Fase 2 deploy. Confirms:

    * ``encuentros_clinicos`` has RLS + policy + FORCE + no app DELETE.
    * The partial unique index ``uq_encuentro_primera_vez`` exists (the real §3
      enforcement) — a missing index would silently allow two first consultations.
    * Data invariant: at most one completed ``primera_vez`` per (tenant, paciente).

    Note: aggregate counts span all tenants, so this must run as the RLS-bypassing
    connection role (the same one ``verify_rls`` uses — not demoted to medrecord_app).
    """
    from app.db.session import _get_session_factory

    factory = _get_session_factory()
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    async with factory() as session, session.begin():
        tchecks, twarn = await _table_rls_checks(session, "encuentros_clinicos")
        checks.extend(tchecks)
        warnings.extend(twarn)

        # The partial unique index is the enforcement of "one primera_vez" (§3).
        index_exists = (
            await session.execute(
                text(
                    "SELECT count(*) FROM pg_indexes "
                    "WHERE schemaname = 'public' AND indexname = 'uq_encuentro_primera_vez'"
                )
            )
        ).scalar_one()
        checks.append(
            _check(
                "partial unique index uq_encuentro_primera_vez present (§3)",
                index_exists == 1,
                f"found={index_exists}",
            )
        )

        # Data invariant: the index must never have allowed a duplicate. Counts any
        # (tenant, paciente) with >1 completed primera_vez — should always be zero.
        duplicados = (
            await session.execute(
                text(
                    """
                    SELECT count(*) FROM (
                        SELECT tenant_id, paciente_id
                        FROM encuentros_clinicos
                        WHERE tipo = 'primera_vez' AND estado = 'completado'
                        GROUP BY tenant_id, paciente_id
                        HAVING count(*) > 1
                    ) dups
                    """
                )
            )
        ).scalar_one()
        checks.append(
            _check(
                "at most one completed primera_vez per patient (§3)",
                duplicados == 0,
                f"patients with duplicate primera_vez={duplicados}",
            )
        )

        counts = {
            "encuentros": (
                await session.execute(text("SELECT count(*) FROM encuentros_clinicos"))
            ).scalar_one(),
            "encuentros_completados": (
                await session.execute(
                    text(
                        "SELECT count(*) FROM encuentros_clinicos WHERE estado = 'completado'"
                    )
                )
            ).scalar_one(),
        }

    return _envelope("encuentros", checks, warnings=warnings, counts=counts)


async def verify_cie10() -> dict[str, Any]:
    """Fase 3: CIE-10 catalog imported + nota_diagnosticos landed with isolation and the
    one-principal invariant intact.

    Read-only, no PHI (structural facts + aggregate counts only). Runs against production
    after the Fase 3 deploy + import. Confirms:

    * ``nota_diagnosticos`` has RLS + policy + FORCE + no app DELETE.
    * The ``pg_trgm`` GIN index over ``normalized_description`` exists (the search degrades
      to a table scan without it) and the extension is installed.
    * The catalog was actually imported: ``cie10`` row count ≥ the floor and no active row
      is missing its ``normalized_description`` (which would make it invisible to search).
    * The partial unique index ``uq_nota_diagnostico_principal`` exists, and the data
      invariant holds: at most one ``es_principal`` diagnosis per note.
    """
    from app.db.session import _get_session_factory

    factory = _get_session_factory()
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    async with factory() as session, session.begin():
        tchecks, twarn = await _table_rls_checks(session, "nota_diagnosticos")
        checks.extend(tchecks)
        warnings.extend(twarn)

        ext_present = (
            await session.execute(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'pg_trgm'")
            )
        ).scalar_one()
        checks.append(
            _check("pg_trgm extension installed", ext_present == 1, f"found={ext_present}")
        )

        trgm_index = (
            await session.execute(
                text(
                    "SELECT count(*) FROM pg_indexes "
                    "WHERE schemaname = 'public' AND indexname = 'ix_cie10_norm_desc_trgm'"
                )
            )
        ).scalar_one()
        checks.append(
            _check(
                "GIN trigram index ix_cie10_norm_desc_trgm present (§3)",
                trgm_index == 1,
                f"found={trgm_index}",
            )
        )

        cie10_total = (
            await session.execute(text("SELECT count(*) FROM cie10"))
        ).scalar_one()
        checks.append(
            _check(
                f"CIE-10 catalog imported (≥ {_CIE10_MIN_ROWS} rows)",
                cie10_total >= _CIE10_MIN_ROWS,
                f"cie10 rows={cie10_total}",
            )
        )

        # An active row without a normalized description is invisible to trigram search.
        sin_normalizar = (
            await session.execute(
                text(
                    "SELECT count(*) FROM cie10 "
                    "WHERE active AND (normalized_description IS NULL "
                    "OR normalized_description = '')"
                )
            )
        ).scalar_one()
        checks.append(
            _check(
                "every active CIE-10 row has a normalized_description",
                sin_normalizar == 0,
                f"active rows missing normalization={sin_normalizar}",
            )
        )

        principal_index = (
            await session.execute(
                text(
                    "SELECT count(*) FROM pg_indexes WHERE schemaname = 'public' "
                    "AND indexname = 'uq_nota_diagnostico_principal'"
                )
            )
        ).scalar_one()
        checks.append(
            _check(
                "partial unique index uq_nota_diagnostico_principal present (§5.3)",
                principal_index == 1,
                f"found={principal_index}",
            )
        )

        # Data invariant: the index must never have allowed a second principal per note.
        multi_principal = (
            await session.execute(
                text(
                    """
                    SELECT count(*) FROM (
                        SELECT nota_id FROM nota_diagnosticos
                        WHERE es_principal
                        GROUP BY nota_id
                        HAVING count(*) > 1
                    ) dups
                    """
                )
            )
        ).scalar_one()
        checks.append(
            _check(
                "at most one principal diagnosis per note (§5.3)",
                multi_principal == 0,
                f"notes with >1 principal={multi_principal}",
            )
        )

        counts = {
            "cie10_total": cie10_total,
            "cie10_active": (
                await session.execute(
                    text("SELECT count(*) FROM cie10 WHERE active")
                )
            ).scalar_one(),
            "nota_diagnosticos": (
                await session.execute(text("SELECT count(*) FROM nota_diagnosticos"))
            ).scalar_one(),
        }

    return _envelope("cie10", checks, warnings=warnings, counts=counts)


async def verify_plantillas() -> dict[str, Any]:
    """Fase 4: verify the shared, immutable consent-template publication catalog."""
    from app.db.session import _get_session_factory
    from app.services.consent_templates import load_catalog, version_hash

    factory = _get_session_factory()
    checks: list[dict[str, Any]] = []
    expected = {
        (document.template_key, document.version): version_hash(document)
        for document in load_catalog()
    }

    async with factory() as session, session.begin():
        table_names = ("consentimiento_plantillas", "consentimiento_plantilla_versiones")
        for table in table_names:
            exists = (
                await session.execute(text("SELECT to_regclass(:table) IS NOT NULL"), {"table": table})
            ).scalar_one()
            checks.append(_check(f"{table} exists", bool(exists)))
            can_select = (
                await session.execute(
                    text("SELECT has_table_privilege('medrecord_app', :table, 'SELECT')"),
                    {"table": table},
                )
            ).scalar_one()
            can_write = (
                await session.execute(
                    text(
                        "SELECT has_table_privilege('medrecord_app', :table, 'INSERT') "
                        "OR has_table_privilege('medrecord_app', :table, 'UPDATE') "
                        "OR has_table_privilege('medrecord_app', :table, 'DELETE')"
                    ),
                    {"table": table},
                )
            ).scalar_one()
            checks.append(
                _check(
                    f"{table}: app role is read-only",
                    bool(can_select) and not bool(can_write),
                    f"select={can_select}, write={can_write}",
                )
            )

        trigger_count = (
            await session.execute(
                text(
                    "SELECT count(*) FROM pg_trigger "
                    "WHERE tgname = 'consentimiento_plantilla_version_immutable' "
                    "AND NOT tgisinternal"
                )
            )
        ).scalar_one()
        checks.append(
            _check(
                "published-template immutability trigger present",
                trigger_count == 1,
                f"found={trigger_count}",
            )
        )

        baseline_rows = (
            await session.execute(
                text(
                    """
                    SELECT p.template_key, v.version, v.contenido_hash
                    FROM consentimiento_plantillas p
                    JOIN consentimiento_plantilla_versiones v ON v.plantilla_id = p.id
                    WHERE (p.template_key, v.version) IN (
                        ('general_atencion', '1.0'),
                        ('estetico_no_quirurgico', '1.0'),
                        ('toxina_botulinica', '1.0'),
                        ('relleno_acido_hialuronico', '1.0'),
                        ('dermatologico', '1.0')
                    )
                    """
                )
            )
        ).all()
        actual = {(row[0], row[1]): row[2] for row in baseline_rows}
        mismatches = sorted(
            key for key, expected_hash in expected.items() if actual.get(key) != expected_hash
        )
        checks.append(
            _check(
                "five legacy v1.0 templates match the reviewed artifact hash",
                not mismatches and len(actual) == 5,
                f"missing_or_mismatched={[key[0] for key in mismatches]}",
            )
        )

        multiple_current = (
            await session.execute(
                text(
                    """
                    SELECT count(*) FROM (
                        SELECT plantilla_id
                        FROM consentimiento_plantilla_versiones
                        WHERE estado = 'publicada'
                        GROUP BY plantilla_id
                        HAVING count(*) > 1
                    ) duplicates
                    """
                )
            )
        ).scalar_one()
        checks.append(
            _check(
                "at most one published version per template",
                multiple_current == 0,
                f"templates_with_multiple_published={multiple_current}",
            )
        )

        snapshot_column = (
            await session.execute(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name='consentimientos' "
                    "AND column_name='plantilla_version_id'"
                )
            )
        ).scalar_one()
        checks.append(
            _check(
                "consentimientos snapshots plantilla_version_id for new emissions",
                snapshot_column == 1,
                f"found={snapshot_column}",
            )
        )

        counts = {
            "plantillas": (
                await session.execute(text("SELECT count(*) FROM consentimiento_plantillas"))
            ).scalar_one(),
            "versiones": (
                await session.execute(
                    text("SELECT count(*) FROM consentimiento_plantilla_versiones")
                )
            ).scalar_one(),
            "publicadas": (
                await session.execute(
                    text(
                        "SELECT count(*) FROM consentimiento_plantilla_versiones "
                        "WHERE estado='publicada'"
                    )
                )
            ).scalar_one(),
        }

    return _envelope("plantillas", checks, counts=counts)


async def verify_backups() -> dict[str, Any]:
    """Assert the NOM-004 §5.14 5-year archive is actually producing backups.

    Read-only, no PHI: only queries AWS Backup control-plane metadata (vault
    lock state and recovery-point timestamps), never the backups' contents.

    This is the proactive half of the anti-silent-failure guard (the reactive
    half is the SNS notification on ``BACKUP_JOB_FAILED``). It catches the exact
    failure of the original incident — infrastructure present but producing no
    recovery points — by requiring at least one COMPLETED recovery point younger
    than ``_BACKUP_MAX_AGE_DAYS`` in the legal vault.
    """
    import boto3

    environment = os.environ.get("ENVIRONMENT", "prod")
    vault_name = f"medrecord-legal-5yr-{environment}"
    client = boto3.client("backup")

    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}

    # Vault exists and (once locked) is immutable. A missing lock is a warning,
    # not a hard failure: governance mode still protects, and the two-step
    # rollout is intentionally unlocked at first.
    try:
        vault = client.describe_backup_vault(BackupVaultName=vault_name)
    except client.exceptions.ResourceNotFoundException:
        checks.append(_check("legal vault exists", False, f"vault {vault_name!r} not found"))
        return _envelope("backups", checks, warnings=warnings, counts=counts)

    checks.append(_check("legal vault exists", True, vault_name))
    if not vault.get("Locked"):
        warnings.append(f"{vault_name}: Vault Lock not yet in compliance mode (WORM)")

    # Paginate recovery points; find the most recent COMPLETED one.
    paginator = client.get_paginator("list_recovery_points_by_backup_vault")
    completed = 0
    newest: datetime | None = None
    for page in paginator.paginate(BackupVaultName=vault_name):
        for rp in page.get("RecoveryPoints", []):
            if rp.get("Status") != "COMPLETED":
                continue
            completed += 1
            created = rp.get("CompletionDate") or rp.get("CreationDate")
            if created is not None and (newest is None or created > newest):
                newest = created

    counts["completed_recovery_points"] = completed

    if newest is None:
        checks.append(
            _check(
                f"recent recovery point (< {_BACKUP_MAX_AGE_DAYS}d)",
                False,
                "no COMPLETED recovery points in the legal vault",
            )
        )
    else:
        age_days = (datetime.now(timezone.utc) - newest).total_seconds() / 86400
        checks.append(
            _check(
                f"recent recovery point (< {_BACKUP_MAX_AGE_DAYS}d)",
                age_days < _BACKUP_MAX_AGE_DAYS,
                f"newest recovery point is {age_days:.1f} days old",
            )
        )

    return _envelope("backups", checks, warnings=warnings, counts=counts)


# action name → verifier coroutine. Each phase appends one entry.
_VERIFIERS: dict[str, Callable[[], Awaitable[dict[str, Any]]]] = {
    "rls": verify_rls,
    "medicos": verify_medicos,
    "encuentros": verify_encuentros,
    "cie10": verify_cie10,
    "plantillas": verify_plantillas,
    "backups": verify_backups,
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
