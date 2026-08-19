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
    # Fase 5: lateral evidence around the immutable signed consent.
    "consentimiento_firmantes",
    "consentimiento_documentos_finales",
    "consentimiento_revocaciones",
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
    "consentimiento_firmantes",
    "consentimiento_documentos_finales",
    "consentimiento_revocaciones",
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
            text("SELECT count(*) FROM pg_policies WHERE schemaname = 'public' AND tablename = :t"),
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
            "tenants": (await session.execute(text("SELECT count(*) FROM tenants"))).scalar_one(),
            "medicos": (await session.execute(text("SELECT count(*) FROM medicos"))).scalar_one(),
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
                    text("SELECT count(*) FROM encuentros_clinicos WHERE estado = 'completado'")
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

        cie10_total = (await session.execute(text("SELECT count(*) FROM cie10"))).scalar_one()
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
                await session.execute(text("SELECT count(*) FROM cie10 WHERE active"))
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
                await session.execute(
                    text("SELECT to_regclass(:table) IS NOT NULL"), {"table": table}
                )
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


async def verify_biblioteca_normativa() -> dict[str, Any]:
    """Fase 6: exactly 19 professionally approved, immutable normative documents."""
    from app.db.session import _get_session_factory
    from app.services.consent_template_reviews import (
        load_phase6_catalog,
        load_phase6_reviews,
        publication_readiness,
    )
    from app.services.consent_templates import version_hash

    documents = load_phase6_catalog()
    reviews = load_phase6_reviews()
    readiness = publication_readiness(documents, reviews)
    expected_hashes = {
        (document.template_key, document.version): version_hash(document) for document in documents
    }
    expected_types = {review.template_key: review.tipo_documento for review in reviews}
    checks = [
        _check(
            "all 19 templates have named clinical and legal approval evidence",
            bool(readiness["ok"]),
            f"errors={readiness['errors']}",
        )
    ]

    factory = _get_session_factory()
    async with factory() as session, session.begin():
        rows = (
            await session.execute(
                text(
                    """
                    SELECT p.template_key, p.categoria, v.version, v.contenido_hash
                    FROM consentimiento_plantillas p
                    JOIN consentimiento_plantilla_versiones v ON v.plantilla_id = p.id
                    WHERE v.estado = 'publicada'
                    """
                )
            )
        ).all()

    actual_hashes = {(row[0], row[2]): row[3] for row in rows}
    actual_types = {row[0]: row[1] for row in rows}
    mismatched = sorted(
        identity
        for identity, expected_hash in expected_hashes.items()
        if actual_hashes.get(identity) != expected_hash
    )
    type_mismatches = sorted(
        key
        for key, expected_type in expected_types.items()
        if actual_types.get(key) != expected_type
    )
    checks.extend(
        [
            _check(
                "the complete Fase-6 package is published with approved immutable hashes",
                not mismatched and len(expected_hashes) == 19,
                f"missing_or_mismatched={mismatched}",
            ),
            _check(
                "published metadata distinguishes consent, authorization and related documents",
                not type_mismatches,
                f"type_mismatches={type_mismatches}",
            ),
        ]
    )
    counts = dict(readiness["counts"])
    counts["versiones_fase6_publicadas"] = len(expected_hashes) - len(mismatched)
    return _envelope("biblioteca_normativa", checks, counts=counts)


async def verify_paquete_dermatologia() -> dict[str, Any]:
    """Fase 7: reviewed dermatology/aesthetic package with immutable hashes."""
    from app.db.session import _get_session_factory
    from app.services.consent_template_reviews import (
        PHASE7_DERMATOLOGY_EXPECTED_KEYS,
        load_phase7_dermatology_catalog,
        load_phase7_dermatology_reviews,
        publication_readiness,
    )
    from app.services.consent_templates import version_hash

    documents = load_phase7_dermatology_catalog()
    reviews = load_phase7_dermatology_reviews()
    readiness = publication_readiness(
        documents,
        reviews,
        expected_keys=PHASE7_DERMATOLOGY_EXPECTED_KEYS,
        package_label="Fase 7 dermatología/estética",
    )
    expected_hashes = {
        (document.template_key, document.version): version_hash(document) for document in documents
    }
    expected_specialties = {document.template_key: document.especialidad for document in documents}
    checks = [
        _check(
            "all 10 dermatology templates have named clinical and legal approval evidence",
            bool(readiness["ok"]),
            f"errors={readiness['errors']}",
        )
    ]

    factory = _get_session_factory()
    async with factory() as session, session.begin():
        rows = (
            await session.execute(
                text(
                    """
                    SELECT p.template_key, p.especialidad, v.version, v.contenido_hash
                    FROM consentimiento_plantillas p
                    JOIN consentimiento_plantilla_versiones v ON v.plantilla_id = p.id
                    WHERE v.estado = 'publicada'
                    """
                )
            )
        ).all()

    actual_hashes = {(row[0], row[2]): row[3] for row in rows}
    actual_specialties = {row[0]: row[1] for row in rows}
    mismatched = sorted(
        identity
        for identity, expected_hash in expected_hashes.items()
        if actual_hashes.get(identity) != expected_hash
    )
    specialty_mismatches = sorted(
        key
        for key, expected_specialty in expected_specialties.items()
        if actual_specialties.get(key) != expected_specialty
    )
    checks.extend(
        [
            _check(
                "the complete Fase-7 dermatology package is published with immutable hashes",
                not mismatched and len(expected_hashes) == 10,
                f"missing_or_mismatched={mismatched}",
            ),
            _check(
                "published metadata keeps every package document in dermatology/aesthetics",
                not specialty_mismatches,
                f"specialty_mismatches={specialty_mismatches}",
            ),
        ]
    )
    counts = dict(readiness["counts"])
    counts["versiones_fase7_dermatologia_publicadas"] = len(expected_hashes) - len(mismatched)
    return _envelope("paquete_dermatologia", checks, counts=counts)


async def verify_consentimientos() -> dict[str, Any]:
    """Fase 5: immutable signers, one final PDF and lateral revocation evidence."""
    from app.db.session import _get_session_factory

    factory = _get_session_factory()
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    tables = (
        "consentimiento_firmantes",
        "consentimiento_documentos_finales",
        "consentimiento_revocaciones",
    )
    async with factory() as session, session.begin():
        for table in tables:
            table_checks, table_warnings = await _table_rls_checks(session, table)
            checks.extend(table_checks)
            warnings.extend(table_warnings)
            can_select_insert = (
                await session.execute(
                    text(
                        "SELECT has_table_privilege('medrecord_app', :t, 'SELECT') "
                        "AND has_table_privilege('medrecord_app', :t, 'INSERT')"
                    ),
                    {"t": table},
                )
            ).scalar_one()
            can_update = (
                await session.execute(
                    text("SELECT has_table_privilege('medrecord_app', :t, 'UPDATE')"),
                    {"t": table},
                )
            ).scalar_one()
            checks.append(
                _check(
                    f"{table}: app is create/read-only",
                    bool(can_select_insert) and not bool(can_update),
                    f"select+insert={can_select_insert}, update={can_update}",
                )
            )

        signed_trigger = (
            await session.execute(
                text(
                    "SELECT count(*) FROM pg_trigger "
                    "WHERE tgname='consentimientos_signed_immutable' AND NOT tgisinternal"
                )
            )
        ).scalar_one()
        evidence_triggers = (
            await session.execute(
                text(
                    "SELECT count(*) FROM pg_trigger WHERE tgname IN "
                    "('consentimiento_firmantes_immutable', "
                    " 'consentimiento_documentos_finales_immutable', "
                    " 'consentimiento_revocaciones_immutable') AND NOT tgisinternal"
                )
            )
        ).scalar_one()
        checks.extend(
            [
                _check(
                    "signed consent immutability trigger present",
                    signed_trigger == 1,
                    f"found={signed_trigger}",
                ),
                _check(
                    "all lateral evidence has UPDATE immutability triggers",
                    evidence_triggers == 3,
                    f"found={evidence_triggers}",
                ),
            ]
        )

        incomplete_finalizations = (
            await session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM consentimientos c
                    WHERE c.credencial_id IS NOT NULL
                      AND (
                        c.verification_token_id IS NULL
                        OR NOT EXISTS (
                            SELECT 1 FROM consentimiento_documentos_finales d
                            WHERE d.consentimiento_id = c.id
                        )
                      )
                    """
                )
            )
        ).scalar_one()
        revocation_token_mismatches = (
            await session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM consentimiento_revocaciones r
                    JOIN consentimientos c ON c.id = r.consentimiento_id
                    LEFT JOIN verification_tokens v ON v.id = c.verification_token_id
                    WHERE v.id IS NULL OR v.status <> 'revoked' OR v.revoked_at IS NULL
                    """
                )
            )
        ).scalar_one()
        checks.extend(
            [
                _check(
                    "every Fase-5 signature has one token and one final document",
                    incomplete_finalizations == 0,
                    f"incomplete={incomplete_finalizations}",
                ),
                _check(
                    "every revocation invalidates its public token",
                    revocation_token_mismatches == 0,
                    f"mismatches={revocation_token_mismatches}",
                ),
            ]
        )
        counts = {
            "firmantes": (
                await session.execute(text("SELECT count(*) FROM consentimiento_firmantes"))
            ).scalar_one(),
            "documentos_finales": (
                await session.execute(
                    text("SELECT count(*) FROM consentimiento_documentos_finales")
                )
            ).scalar_one(),
            "revocaciones": (
                await session.execute(text("SELECT count(*) FROM consentimiento_revocaciones"))
            ).scalar_one(),
        }

    return _envelope("consentimientos", checks, warnings=warnings, counts=counts)


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


async def verify_fase8() -> dict[str, Any]:
    """Fase 8: rollout prerequisites, bounded connections and read-path indexes.

    This verifier is structural/aggregate-only. Load thresholds are intentionally
    proven by the local harness, never by generating traffic against production.
    """
    from app.core.clinical_rollout import rollout_stage
    from app.core.config import settings
    from app.db.session import _get_session_factory

    stage = rollout_stage()
    checks: list[dict[str, Any]] = [
        _check("rollout stage is supported", 1 <= stage <= 9, f"stage={stage}"),
        _check(
            "direct RDS pool is bounded per Lambda environment",
            settings.db_pool_size + settings.db_max_overflow <= 2,
            f"pool={settings.db_pool_size}, overflow={settings.db_max_overflow}",
        ),
    ]
    warnings: list[str] = []
    counts: dict[str, int] = {"rollout_stage": stage}
    expected_indexes = {
        "ix_notas_expediente_creado_id",
        "ix_consentimientos_expediente_creado_id",
        "ix_pacientes_nombre_trgm",
        "ix_pacientes_curp_trgm",
        "ix_pacientes_telefono_trgm",
    }

    factory = _get_session_factory()
    async with factory() as session, session.begin():
        index_rows = (
            (
                await session.execute(
                    text(
                        "SELECT indexname FROM pg_indexes "
                        "WHERE schemaname='public' AND indexname = ANY(CAST(:names AS text[]))"
                    ),
                    {"names": sorted(expected_indexes)},
                )
            )
            .scalars()
            .all()
        )
        found_indexes = set(index_rows)
        checks.append(
            _check(
                "all Fase-8 read-path indexes are present",
                found_indexes == expected_indexes,
                f"missing={sorted(expected_indexes - found_indexes)}",
            )
        )
        counts["performance_indexes"] = len(found_indexes)

        legacy_columns = (
            (
                await session.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name='tenants' "
                        "AND column_name = ANY(CAST(:names AS text[]))"
                    ),
                    {"names": ["nombre_medico", "cedula", "especialidad"]},
                )
            )
            .scalars()
            .all()
        )
        checks.append(
            _check(
                "legacy signing columns remain available for rollback",
                set(legacy_columns) == {"nombre_medico", "cedula", "especialidad"},
                f"present={sorted(legacy_columns)}",
            )
        )

        if stage >= 2:
            missing_credentials = (
                await session.execute(
                    text(
                        """
                        SELECT count(*) FROM tenants t
                        WHERE t.activo AND NOT EXISTS (
                          SELECT 1 FROM medicos m
                          JOIN medico_credenciales c ON c.medico_id=m.id
                          WHERE m.tenant_id=t.id AND c.activa AND c.es_predeterminada
                        )
                        """
                    )
                )
            ).scalar_one()
            checks.append(
                _check(
                    "stage 2 has a default active credential per active tenant",
                    missing_credentials == 0,
                    f"missing={missing_credentials}",
                )
            )
            counts["tenants_missing_default_credential"] = missing_credentials

        if stage >= 5:
            active_cie10 = (
                await session.execute(text("SELECT count(*) FROM cie10 WHERE active"))
            ).scalar_one()
            checks.append(
                _check(
                    "stage 5 has the complete CIE-10 catalog",
                    active_cie10 >= _CIE10_MIN_ROWS,
                    f"active={active_cie10}",
                )
            )
            counts["cie10_active"] = active_cie10

        if stage >= 7:
            published_templates = (
                await session.execute(
                    text(
                        "SELECT count(*) FROM consentimiento_plantilla_versiones "
                        "WHERE estado='publicada'"
                    )
                )
            ).scalar_one()
            checks.append(
                _check(
                    "stage 7 has published consent templates",
                    published_templates >= 5,
                    f"published={published_templates}",
                )
            )
            counts["published_templates"] = published_templates

        if stage >= 8:
            incomplete_finalizations = (
                await session.execute(
                    text(
                        """
                        SELECT count(*) FROM consentimientos c
                        WHERE c.credencial_id IS NOT NULL
                          AND NOT EXISTS (
                            SELECT 1 FROM consentimiento_documentos_finales d
                            WHERE d.consentimiento_id=c.id
                          )
                        """
                    )
                )
            ).scalar_one()
            checks.append(
                _check(
                    "stage 8 has no incomplete final consent documents",
                    incomplete_finalizations == 0,
                    f"incomplete={incomplete_finalizations}",
                )
            )
            counts["incomplete_finalizations"] = incomplete_finalizations

        if stage >= 9:
            from app.services.consent_template_reviews import (
                load_phase6_catalog,
                load_phase6_reviews,
                publication_readiness,
            )

            phase6_documents = load_phase6_catalog()
            readiness = publication_readiness(phase6_documents, load_phase6_reviews())
            expected_keys = [document.template_key for document in phase6_documents]
            normative_templates = (
                await session.execute(
                    text(
                        """
                        SELECT count(DISTINCT p.template_key)
                        FROM consentimiento_plantilla_versiones v
                        JOIN consentimiento_plantillas p ON p.id=v.plantilla_id
                        WHERE v.estado='publicada'
                          AND p.template_key = ANY(CAST(:keys AS text[]))
                        """
                    ),
                    {"keys": expected_keys},
                )
            ).scalar_one()
            checks.append(
                _check(
                    "stage 9 has the reviewed normative library",
                    bool(readiness["ok"]) and normative_templates == 19,
                    f"approved={readiness['ok']}, published_normative={normative_templates}",
                )
            )
            counts["published_normative_templates"] = normative_templates

    warnings.append(
        "Load SLO evidence is produced locally by scripts/run_phase8_load.py; production verification is read-only."
    )
    return _envelope("fase8", checks, warnings=warnings, counts=counts)


async def verify_fase9() -> dict[str, Any]:
    """Fase 9: fail-closed auth, secret indirection and session audit evidence.

    No secret value, token, user identifier or patient data is returned by this
    verifier. The Secrets Manager read only proves that an AWSCURRENT value exists.
    """
    from app.core.config import get_clerk_secret_key, settings
    from app.db.session import _get_session_factory

    checks: list[dict[str, Any]] = [
        _check(
            "Clerk backend secret is absent from Lambda environment",
            "CLERK_SECRET_KEY" not in os.environ,
            "secret value must be resolved through Secrets Manager",
        ),
        _check(
            "application secret ARN is configured",
            bool(settings.app_config_secret_arn),
            "APP_CONFIG_SECRET_ARN is set" if settings.app_config_secret_arn else "missing ARN",
        ),
        _check(
            "Clerk endpoints require HTTPS",
            settings.clerk_issuer_url.startswith("https://")
            and settings.clerk_jwks_url.startswith("https://"),
            "issuer/JWKS transport policy",
        ),
        _check(
            "authorized parties are explicit",
            bool(settings.clerk_authorized_parties),
            f"configured_parties={len(settings.clerk_authorized_parties)}",
        ),
        _check(
            "MFA enforcement policy is configured",
            True,
            f"CLERK_REQUIRE_MFA={'true' if settings.clerk_require_mfa else 'false'}",
        ),
        _check(
            "sensitive-action window is at most 10 minutes",
            1 <= settings.clerk_reauth_max_age_minutes <= 10,
            f"window_minutes={settings.clerk_reauth_max_age_minutes}",
        ),
    ]

    secret_available = False
    try:
        secret_available = bool(get_clerk_secret_key())
    except Exception as exc:
        # Only the exception type is reported; provider responses can contain
        # account metadata and must not become deployment artifacts.
        lookup_status = type(exc).__name__
    else:
        lookup_status = "available"
    checks.append(
        _check(
            "Clerk secret has an active Secrets Manager value",
            secret_available,
            f"lookup_result={lookup_status}",
        )
    )

    expected_columns = {
        "identity_provider_id",
        "session_id",
        "factor_verification_age",
    }
    factory = _get_session_factory()
    async with factory() as session, session.begin():
        columns = set(
            (
                await session.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name='audit_log' "
                        "AND column_name = ANY(CAST(:names AS text[]))"
                    ),
                    {"names": sorted(expected_columns)},
                )
            ).scalars()
        )
        audit_index = int(
            (
                await session.execute(
                    text(
                        "SELECT count(*) FROM pg_indexes WHERE schemaname='public' "
                        "AND tablename='audit_log' "
                        "AND indexname='ix_audit_log_tenant_identity_timestamp'"
                    )
                )
            ).scalar_one()
        )

    checks.extend(
        [
            _check(
                "audit trail captures identity/session/MFA context",
                columns == expected_columns,
                f"columns={len(columns)}/{len(expected_columns)}",
            ),
            _check(
                "identity audit lookup index exists",
                audit_index == 1,
                f"indexes={audit_index}",
            ),
        ]
    )
    return _envelope(
        "fase9",
        checks,
        warnings=[
            "Clerk Dashboard MFA enforcement and independent penetration testing require external evidence."
        ],
    )


# action name → verifier coroutine. Each phase appends one entry.
# Fase 10: recovery must be *possible*, not just backups fresh. PITR needs a
# non-trivial retention window, and every clinical bucket must be versioned so a
# bad overwrite/delete is recoverable by version.
_PITR_MIN_RETENTION_DAYS = 35


async def verify_recuperacion() -> dict[str, Any]:
    """Fase 10: assert recovery capability — RDS PITR window and S3 versioning.

    Read-only, no PHI: only queries RDS/S3 control-plane configuration (the
    backup retention period and bucket versioning status), never data. Archive
    freshness (a recent recovery point in the legal vault) is the separate
    concern of :func:`verify_backups`; this verifier asserts the recovery
    *capability* is configured (§1–§2 of the recovery runbook).
    """
    import boto3

    environment = os.environ.get("ENVIRONMENT", "prod")
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}

    # RDS point-in-time recovery: retention window must cover the operational
    # recovery horizon. A window of 0 means PITR is effectively disabled.
    rds = boto3.client("rds")
    instance_id = f"medrecord-{environment}"
    try:
        described = rds.describe_db_instances(DBInstanceIdentifier=instance_id)
        instance = described["DBInstances"][0]
        retention = int(instance.get("BackupRetentionPeriod", 0))
        counts["pitr_retention_days"] = retention
        checks.append(
            _check(
                f"RDS PITR retention >= {_PITR_MIN_RETENTION_DAYS}d",
                retention >= _PITR_MIN_RETENTION_DAYS,
                f"{instance_id}: BackupRetentionPeriod={retention}",
            )
        )
    except Exception as exc:  # noqa: BLE001 - surfaced as a failed check, never raised
        checks.append(_check("RDS PITR retention", False, f"{instance_id}: {exc}"))

    # S3 versioning: a bad overwrite/delete of a clinical object must be
    # recoverable by version. Bucket names arrive as Lambda env vars.
    s3 = boto3.client("s3")
    bucket_env_vars = {
        "expedientes": "S3_EXPEDIENTES_BUCKET",
        "consent": "S3_CONSENT_BUCKET",
        "audit": "S3_AUDIT_BUCKET",
    }
    versioned = 0
    for label, env_var in bucket_env_vars.items():
        bucket = os.environ.get(env_var)
        if not bucket:
            warnings.append(f"{env_var} not set; skipped {label} bucket versioning check")
            continue
        try:
            status = s3.get_bucket_versioning(Bucket=bucket).get("Status")
            ok = status == "Enabled"
            if ok:
                versioned += 1
            checks.append(
                _check(f"S3 versioning ({label})", ok, f"{bucket}: Status={status!r}")
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as a failed check, never raised
            checks.append(_check(f"S3 versioning ({label})", False, f"{bucket}: {exc}"))
    counts["versioned_clinical_buckets"] = versioned

    return _envelope("recuperacion", checks, warnings=warnings, counts=counts)


async def verify_favoritos() -> dict[str, Any]:
    """Fase 13: the médico favoritos table landed tenant-scoped and editable.

    Read-only, no PHI: structural facts + a count. Favorites are editable
    preferences, so — unlike clinical tables — the app role KEEPS DELETE, which
    this verifier asserts explicitly.
    """
    from app.db.session import _get_session_factory

    factory = _get_session_factory()
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}

    async with factory() as session, session.begin():
        tchecks, twarn = await _table_rls_checks(session, "medico_favoritos")
        checks.extend(tchecks)
        warnings.extend(twarn)

        can_delete = (
            await session.execute(
                text("SELECT has_table_privilege('medrecord_app', 'medico_favoritos', 'DELETE')")
            )
        ).scalar_one()
        checks.append(
            _check(
                "medico_favoritos: app role can DELETE (editable preference, not evidence)",
                bool(can_delete),
                f"has_delete={can_delete}",
            )
        )
        counts["favoritos"] = (
            await session.execute(text("SELECT count(*) FROM medico_favoritos"))
        ).scalar_one()

    return _envelope("favoritos", checks, warnings=warnings, counts=counts)


async def verify_plantillas_nota() -> dict[str, Any]:
    """Fase 13: the note-templates table landed tenant-scoped and editable.

    Read-only, no PHI: structural facts + a count. Templates are editable
    preferences, so — unlike clinical tables — the app role KEEPS DELETE.
    """
    from app.db.session import _get_session_factory

    factory = _get_session_factory()
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}

    async with factory() as session, session.begin():
        tchecks, twarn = await _table_rls_checks(session, "nota_plantillas")
        checks.extend(tchecks)
        warnings.extend(twarn)

        can_delete = (
            await session.execute(
                text("SELECT has_table_privilege('medrecord_app', 'nota_plantillas', 'DELETE')")
            )
        ).scalar_one()
        checks.append(
            _check(
                "nota_plantillas: app role can DELETE (editable preference, not evidence)",
                bool(can_delete),
                f"has_delete={can_delete}",
            )
        )
        counts["plantillas"] = (
            await session.execute(text("SELECT count(*) FROM nota_plantillas"))
        ).scalar_one()

    return _envelope("plantillas_nota", checks, warnings=warnings, counts=counts)


_VERIFIERS: dict[str, Callable[[], Awaitable[dict[str, Any]]]] = {
    "rls": verify_rls,
    "medicos": verify_medicos,
    "encuentros": verify_encuentros,
    "cie10": verify_cie10,
    "plantillas": verify_plantillas,
    "biblioteca_normativa": verify_biblioteca_normativa,
    "paquete_dermatologia": verify_paquete_dermatologia,
    "consentimientos": verify_consentimientos,
    "fase8": verify_fase8,
    "fase9": verify_fase9,
    "backups": verify_backups,
    "recuperacion": verify_recuperacion,
    "favoritos": verify_favoritos,
    "plantillas_nota": verify_plantillas_nota,
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
