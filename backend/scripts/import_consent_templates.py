"""Idempotent Fase-4 consent-template publisher (admin Lambda payload).

Alembic creates schema only. This module validates the bundled JSON catalog, computes a
canonical SHA-256 for every immutable version and publishes it after deploy through
``{"import_consent_templates": "dry-run"|"apply"}``.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.session import _get_session_factory
from app.models.consentimiento_plantilla import (
    ConsentimientoPlantilla,
    ConsentimientoPlantillaVersion,
)
from app.services.consent_template_reviews import (
    ReadinessReport,
    load_phase6_catalog,
    load_phase6_reviews,
    publication_readiness,
)
from app.services.consent_templates import (
    ConsentTemplateDocument,
    load_catalog,
    version_hash,
)


class PublicationConflictError(ValueError):
    """The source attempts to rewrite or republish an immutable version."""


def _envelope(
    action: str,
    ok: bool,
    counts: dict[str, int],
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {"ok": ok, "action": action, "counts": counts, "errors": errors or []}


def _version_values(document: ConsentTemplateDocument) -> dict[str, Any]:
    return {
        "version": document.version,
        "nombre": document.nombre,
        "contenido": document.contenido.model_dump(),
        "campos": [field.model_dump() for field in document.campos],
        "firmas_requeridas": document.firmas_requeridas.model_dump(),
        "referencias_normativas": document.referencias_normativas,
        "responsable_revision": document.responsable_revision,
        "revisada_en": document.revisada_en,
        "contenido_hash": version_hash(document),
    }


async def _inspect(session: Any, documents: list[ConsentTemplateDocument]) -> dict[str, int]:
    counts = {
        "templates_total": len(documents),
        "templates_would_insert": 0,
        "templates_would_update": 0,
        "versions_would_insert": 0,
        "versions_unchanged": 0,
    }
    for document in documents:
        template = (
            await session.execute(
                select(ConsentimientoPlantilla).where(
                    ConsentimientoPlantilla.template_key == document.template_key
                )
            )
        ).scalar_one_or_none()
        if template is None:
            counts["templates_would_insert"] += 1
            counts["versions_would_insert"] += 1
            continue

        metadata = (template.categoria, template.especialidad, template.procedimiento)
        incoming_metadata = (document.categoria, document.especialidad, document.procedimiento)
        if metadata != incoming_metadata or template.estado != "activa":
            counts["templates_would_update"] += 1

        version = (
            await session.execute(
                select(ConsentimientoPlantillaVersion).where(
                    ConsentimientoPlantillaVersion.plantilla_id == template.id,
                    ConsentimientoPlantillaVersion.version == document.version,
                )
            )
        ).scalar_one_or_none()
        if version is None:
            counts["versions_would_insert"] += 1
        elif version.contenido_hash != version_hash(document):
            raise PublicationConflictError(
                f"{document.template_key} v{document.version} ya está publicada con otro hash; "
                "crea una versión nueva"
            )
        elif version.estado != "publicada":
            raise PublicationConflictError(
                f"{document.template_key} v{document.version} está {version.estado}; "
                "una versión retirada no se republica"
            )
        else:
            counts["versions_unchanged"] += 1
    return counts


def _load_publication_documents(
    catalog: str,
) -> tuple[list[ConsentTemplateDocument], ReadinessReport]:
    if catalog == "baseline":
        documents = load_catalog()
        return documents, {
            "ok": True,
            "counts": {"templates_total": len(documents)},
            "errors": [],
        }
    if catalog == "fase6":
        documents = load_phase6_catalog()
        readiness = publication_readiness(documents, load_phase6_reviews())
        return documents, readiness
    raise ValueError("catalog must be baseline or fase6")


async def run_import(mode: str, catalog: str = "baseline") -> dict[str, Any]:
    action = f"import_consent_templates:{catalog}:{mode}"
    if mode not in ("dry-run", "apply"):
        return _envelope(action, False, {}, ["mode must be dry-run or apply"])

    try:
        documents, readiness = _load_publication_documents(catalog)
        if not readiness["ok"]:
            return _envelope(
                action,
                False,
                dict(readiness["counts"]),
                list(readiness["errors"]),
            )
        factory = _get_session_factory()
        async with factory() as session, session.begin():
            counts = await _inspect(session, documents)
            if mode == "dry-run":
                return _envelope(action, True, counts)

            inserted_templates = 0
            updated_templates = 0
            inserted_versions = 0
            unchanged_versions = 0

            for document in documents:
                template = (
                    await session.execute(
                        select(ConsentimientoPlantilla).where(
                            ConsentimientoPlantilla.template_key == document.template_key
                        )
                    )
                ).scalar_one_or_none()
                if template is None:
                    template = ConsentimientoPlantilla(
                        template_key=document.template_key,
                        categoria=document.categoria,
                        especialidad=document.especialidad,
                        procedimiento=document.procedimiento,
                        estado="activa",
                    )
                    session.add(template)
                    await session.flush()
                    inserted_templates += 1
                else:
                    incoming_metadata = (
                        document.categoria,
                        document.especialidad,
                        document.procedimiento,
                    )
                    current_metadata = (
                        template.categoria,
                        template.especialidad,
                        template.procedimiento,
                    )
                    if current_metadata != incoming_metadata or template.estado != "activa":
                        template.categoria = document.categoria
                        template.especialidad = document.especialidad
                        template.procedimiento = document.procedimiento
                        template.estado = "activa"
                        template.actualizada_en = datetime.now(timezone.utc)
                        updated_templates += 1

                existing = (
                    await session.execute(
                        select(ConsentimientoPlantillaVersion).where(
                            ConsentimientoPlantillaVersion.plantilla_id == template.id,
                            ConsentimientoPlantillaVersion.version == document.version,
                        )
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    unchanged_versions += 1
                    continue

                current = (
                    await session.execute(
                        select(ConsentimientoPlantillaVersion).where(
                            ConsentimientoPlantillaVersion.plantilla_id == template.id,
                            ConsentimientoPlantillaVersion.estado == "publicada",
                        )
                    )
                ).scalar_one_or_none()
                if current is not None:
                    current.estado = "retirada"
                    await session.flush()

                values = _version_values(document)
                session.add(
                    ConsentimientoPlantillaVersion(
                        plantilla_id=template.id,
                        estado="publicada",
                        publicada_en=datetime.now(timezone.utc),
                        **values,
                    )
                )
                inserted_versions += 1

            counts = {
                "templates_total": len(documents),
                "templates_inserted": inserted_templates,
                "templates_updated": updated_templates,
                "versions_inserted": inserted_versions,
                "versions_unchanged": unchanged_versions,
            }
            return _envelope(action, True, counts)
    except (OSError, ValueError, PublicationConflictError) as exc:
        return _envelope(action, False, {}, [str(exc)])


def run_import_sync(mode: str, catalog: str = "baseline") -> dict[str, Any]:
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(run_import(mode, catalog))


if __name__ == "__main__":
    import json
    import sys

    mode_arg = sys.argv[1] if len(sys.argv) > 1 else "dry-run"
    print(json.dumps(run_import_sync(mode_arg), ensure_ascii=False, indent=2, default=str))
