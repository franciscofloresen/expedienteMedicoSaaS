from datetime import datetime, timezone

from app.services.consent_template_reviews import (
    PHASE6_EXPECTED_KEYS,
    ReviewApproval,
    load_phase6_catalog,
    load_phase6_reviews,
    publication_readiness,
)
from scripts.import_consent_templates import run_import


def test_phase6_candidate_library_has_exactly_the_roadmap_package() -> None:
    documents = load_phase6_catalog()

    assert len(documents) == 19
    assert {document.template_key for document in documents} == PHASE6_EXPECTED_KEYS
    assert all(document.referencias_normativas for document in documents)
    assert all(document.contenido.aviso_producto.startswith(("BORRADOR", "DOCUMENTO", "AUTORIZACIÓN")) for document in documents)


def test_phase6_manifest_distinguishes_document_types() -> None:
    reviews = load_phase6_reviews()
    by_type: dict[str, int] = {}
    for review in reviews:
        by_type[review.tipo_documento] = by_type.get(review.tipo_documento, 0) + 1

    assert by_type == {
        "autorizacion": 1,
        "consentimiento_informado": 14,
        "documento_relacionado": 4,
    }


def test_phase6_publication_is_blocked_until_all_professional_reviews_exist() -> None:
    report = publication_readiness(load_phase6_catalog(), load_phase6_reviews())

    assert report["ok"] is False
    assert report["counts"] == {
        "templates_total": 19,
        "revisiones_clinicas_aprobadas": 0,
        "revisiones_juridicas_aprobadas": 0,
        "consentimientos_informados": 14,
        "autorizaciones": 1,
        "documentos_relacionados": 4,
    }
    # 19 draft markers + 19 clinical + 19 legal + 19 consolidated review fields.
    assert len(report["errors"]) == 76


async def test_phase6_admin_import_stops_before_database_while_reviews_are_pending() -> None:
    result = await run_import("dry-run", "fase6")

    assert result["ok"] is False
    assert result["action"] == "import_consent_templates:fase6:dry-run"
    assert result["counts"]["templates_total"] == 19
    assert any("revisión clínica pendiente" in error for error in result["errors"])


def test_phase6_gate_accepts_complete_named_evidence() -> None:
    reviewed_at = datetime(2026, 7, 16, tzinfo=timezone.utc)
    clinical = ReviewApproval(
        status="aprobada",
        responsable="Dra. Revisora Clínica",
        credencial_o_rol="Cédula verificada por el responsable de publicación",
        revisada_en=reviewed_at,
        evidencia="https://github.example/evidence/clinical",
    )
    legal = ReviewApproval(
        status="aprobada",
        responsable="Lic. Revisor Jurídico",
        credencial_o_rol="Asesoría jurídica sanitaria",
        revisada_en=reviewed_at,
        evidencia="https://github.example/evidence/legal",
    )
    documents = []
    for document in load_phase6_catalog():
        content = document.contenido.model_copy(
            update={"aviso_producto": "Contenido aprobado para publicación controlada."}
        )
        documents.append(
            document.model_copy(
                update={
                    "contenido": content,
                    "responsable_revision": "Dra. Revisora Clínica; Lic. Revisor Jurídico",
                    "revisada_en": reviewed_at,
                }
            )
        )
    reviews = [
        review.model_copy(update={"revision_clinica": clinical, "revision_juridica": legal})
        for review in load_phase6_reviews()
    ]

    report = publication_readiness(documents, reviews)

    assert report["ok"] is True
    assert report["errors"] == []
