from datetime import datetime, timezone

from app.services.consent_template_reviews import (
    PHASE7_DERMATOLOGY_EXPECTED_KEYS,
    ReadinessReport,
    ReviewApproval,
    TemplateReview,
    load_phase7_dermatology_catalog,
    load_phase7_dermatology_reviews,
    publication_readiness,
)
from app.services.consent_templates import ConsentTemplateDocument
from scripts.import_consent_templates import run_import


def _readiness(
    documents: list[ConsentTemplateDocument] | None = None,
    reviews: list[TemplateReview] | None = None,
) -> ReadinessReport:
    return publication_readiness(
        load_phase7_dermatology_catalog() if documents is None else documents,
        load_phase7_dermatology_reviews() if reviews is None else reviews,
        expected_keys=PHASE7_DERMATOLOGY_EXPECTED_KEYS,
        package_label="Fase 7 dermatología/estética",
    )


def test_phase7_candidate_has_the_first_roadmap_specialty_package() -> None:
    documents = load_phase7_dermatology_catalog()

    assert len(documents) == 10
    assert {document.template_key for document in documents} == (PHASE7_DERMATOLOGY_EXPECTED_KEYS)
    assert {document.especialidad for document in documents} == {"Dermatología y medicina estética"}
    assert all(document.categoria == "consentimiento_informado" for document in documents)
    assert all(document.referencias_normativas for document in documents)
    assert all("BORRADOR" in document.contenido.aviso_producto for document in documents)


def test_phase7_review_manifest_covers_every_version_once() -> None:
    reviews = load_phase7_dermatology_reviews()

    assert len(reviews) == 10
    assert {review.template_key for review in reviews} == PHASE7_DERMATOLOGY_EXPECTED_KEYS
    assert all(review.tipo_documento == "consentimiento_informado" for review in reviews)


def test_phase7_publication_is_blocked_until_professional_reviews_exist() -> None:
    report = _readiness()

    assert report["ok"] is False
    assert report["counts"] == {
        "templates_total": 10,
        "revisiones_clinicas_aprobadas": 0,
        "revisiones_juridicas_aprobadas": 0,
        "consentimientos_informados": 10,
        "autorizaciones": 0,
        "documentos_relacionados": 0,
    }
    # Ten draft markers + ten clinical + ten legal + ten consolidated review fields.
    assert len(report["errors"]) == 40


async def test_phase7_admin_import_stops_before_database_while_reviews_are_pending() -> None:
    result = await run_import("dry-run", "fase7_dermatologia")

    assert result["ok"] is False
    assert result["action"] == "import_consent_templates:fase7_dermatologia:dry-run"
    assert result["counts"]["templates_total"] == 10
    assert any("revisión clínica pendiente" in error for error in result["errors"])


def test_phase7_gate_accepts_complete_named_evidence() -> None:
    reviewed_at = datetime(2026, 7, 17, tzinfo=timezone.utc)
    clinical = ReviewApproval(
        status="aprobada",
        responsable="Dra. Revisora Dermatóloga",
        credencial_o_rol="Especialista con cédula verificada",
        revisada_en=reviewed_at,
        evidencia="https://github.example/evidence/dermatology-clinical",
    )
    legal = ReviewApproval(
        status="aprobada",
        responsable="Lic. Revisor Jurídico",
        credencial_o_rol="Asesoría jurídica sanitaria",
        revisada_en=reviewed_at,
        evidencia="https://github.example/evidence/dermatology-legal",
    )
    documents = []
    for document in load_phase7_dermatology_catalog():
        content = document.contenido.model_copy(
            update={"aviso_producto": "Contenido aprobado para publicación controlada."}
        )
        documents.append(
            document.model_copy(
                update={
                    "contenido": content,
                    "responsable_revision": ("Dra. Revisora Dermatóloga; Lic. Revisor Jurídico"),
                    "revisada_en": reviewed_at,
                }
            )
        )
    reviews = [
        review.model_copy(update={"revision_clinica": clinical, "revision_juridica": legal})
        for review in load_phase7_dermatology_reviews()
    ]

    report = _readiness(documents, reviews)

    assert report["ok"] is True
    assert report["errors"] == []
