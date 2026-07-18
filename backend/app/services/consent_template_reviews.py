"""Clinical/legal publication gates for immutable consent-template packages."""

import json
from datetime import datetime
from pathlib import Path
from typing import Literal, TypedDict

from pydantic import BaseModel, Field, model_validator

from app.services.consent_templates import ConsentTemplateDocument

_BACKEND_DIR = Path(__file__).resolve().parents[2]
PHASE6_CATALOG_PATH = _BACKEND_DIR / "app" / "data" / "consent_templates_phase6.json"
PHASE6_REVIEW_PATH = _BACKEND_DIR / "app" / "data" / "consent_template_reviews_phase6.json"
PHASE7_DERMATOLOGY_CATALOG_PATH = (
    _BACKEND_DIR / "app" / "data" / "consent_templates_phase7_dermatology.json"
)
PHASE7_DERMATOLOGY_REVIEW_PATH = (
    _BACKEND_DIR / "app" / "data" / "consent_template_reviews_phase7_dermatology.json"
)

PHASE6_EXPECTED_KEYS = frozenset(
    {
        "general_atencion",
        "ingreso_hospitalario",
        "cirugia_mayor",
        "anestesia_general_regional",
        "diagnostico_alto_riesgo",
        "terapeutico_alto_riesgo",
        "transfusion_hemoderivados",
        "salpingoclasia",
        "vasectomia",
        "donacion_trasplante",
        "investigacion_clinica",
        "necropsia",
        "procedimiento_posible_mutilacion",
        "representacion_tutor",
        "negativa_tratamiento",
        "revocacion_consentimiento",
        "egreso_voluntario",
        "fotografias_clinicas",
        "teleconsulta",
    }
)

PHASE7_DERMATOLOGY_EXPECTED_KEYS = frozenset(
    {
        "dermatologia_biopsia_piel",
        "dermatologia_crioterapia",
        "dermatologia_escision_lesion",
        "dermatologia_estetico_no_quirurgico",
        "dermatologia_laser",
        "dermatologia_microneedling",
        "dermatologia_peeling_quimico",
        "dermatologia_plasma_rico_plaquetas",
        "dermatologia_relleno_acido_hialuronico",
        "dermatologia_toxina_botulinica",
    }
)


class ReviewApproval(BaseModel):
    status: Literal["pendiente", "aprobada", "rechazada"] = "pendiente"
    responsable: str | None = Field(default=None, max_length=160)
    credencial_o_rol: str | None = Field(default=None, max_length=160)
    revisada_en: datetime | None = None
    evidencia: str | None = Field(default=None, max_length=500)
    observaciones: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def approved_review_has_evidence(self) -> "ReviewApproval":
        if self.status == "aprobada" and not all(
            (self.responsable, self.credencial_o_rol, self.revisada_en, self.evidencia)
        ):
            raise ValueError(
                "Una aprobación requiere responsable, credencial_o_rol, revisada_en y evidencia"
            )
        return self


class TemplateReview(BaseModel):
    template_key: str = Field(pattern=r"^[a-z0-9_]+$", max_length=80)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+$", max_length=20)
    tipo_documento: Literal[
        "consentimiento_informado", "autorizacion", "documento_relacionado"
    ]
    revision_clinica: ReviewApproval
    revision_juridica: ReviewApproval


class ReadinessReport(TypedDict):
    ok: bool
    counts: dict[str, int]
    errors: list[str]


def load_phase6_catalog(path: Path = PHASE6_CATALOG_PATH) -> list[ConsentTemplateDocument]:
    from app.services.consent_templates import load_catalog

    return load_catalog(path)


def _load_reviews(path: Path) -> list[TemplateReview]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("El manifiesto de revisión debe ser un arreglo JSON")
    reviews = [TemplateReview.model_validate(item) for item in raw]
    identities = [(review.template_key, review.version) for review in reviews]
    if len(identities) != len(set(identities)):
        raise ValueError("El manifiesto contiene template_key/version duplicados")
    return reviews


def load_phase6_reviews(path: Path = PHASE6_REVIEW_PATH) -> list[TemplateReview]:
    return _load_reviews(path)


def load_phase7_dermatology_catalog(
    path: Path = PHASE7_DERMATOLOGY_CATALOG_PATH,
) -> list[ConsentTemplateDocument]:
    from app.services.consent_templates import load_catalog

    return load_catalog(path)


def load_phase7_dermatology_reviews(
    path: Path = PHASE7_DERMATOLOGY_REVIEW_PATH,
) -> list[TemplateReview]:
    return _load_reviews(path)


def publication_readiness(
    documents: list[ConsentTemplateDocument],
    reviews: list[TemplateReview],
    *,
    expected_keys: frozenset[str] = PHASE6_EXPECTED_KEYS,
    package_label: str = "Fase 6",
) -> ReadinessReport:
    """Return a deterministic gate report; no unreviewed document may be published."""
    errors: list[str] = []
    document_map = {(document.template_key, document.version): document for document in documents}
    review_map = {(review.template_key, review.version): review for review in reviews}
    document_keys = {document.template_key for document in documents}
    review_keys = {review.template_key for review in reviews}

    if document_keys != expected_keys:
        errors.append(
            f"El catálogo {package_label} debe contener exactamente {len(expected_keys)} keys; "
            f"faltan={sorted(expected_keys - document_keys)}, "
            f"sobran={sorted(document_keys - expected_keys)}"
        )
    if review_keys != expected_keys:
        errors.append(
            f"El manifiesto {package_label} debe cubrir exactamente {len(expected_keys)} keys; "
            f"faltan={sorted(expected_keys - review_keys)}, "
            f"sobran={sorted(review_keys - expected_keys)}"
        )
    if set(document_map) != set(review_map):
        errors.append("Las identidades template_key/version del catálogo y manifiesto no coinciden")

    approved_clinical = 0
    approved_legal = 0
    document_types: dict[str, int] = {}
    for identity, document in document_map.items():
        review = review_map.get(identity)
        if review is None:
            continue
        document_types[review.tipo_documento] = document_types.get(review.tipo_documento, 0) + 1
        if document.categoria != review.tipo_documento:
            errors.append(
                f"{document.template_key} v{document.version}: categoria={document.categoria!r} "
                f"no coincide con tipo_documento={review.tipo_documento!r}"
            )
        if not document.referencias_normativas:
            errors.append(f"{document.template_key} no tiene referencias normativas")
        if "BORRADOR" in document.contenido.aviso_producto.upper():
            errors.append(
                f"{document.template_key} v{document.version}: el artefacto aún está marcado BORRADOR"
            )
        if review.revision_clinica.status == "aprobada":
            approved_clinical += 1
        else:
            errors.append(
                f"{document.template_key} v{document.version}: revisión clínica "
                f"{review.revision_clinica.status}"
            )
        if review.revision_juridica.status == "aprobada":
            approved_legal += 1
        else:
            errors.append(
                f"{document.template_key} v{document.version}: revisión jurídica "
                f"{review.revision_juridica.status}"
            )
        if not document.responsable_revision or document.revisada_en is None:
            errors.append(
                f"{document.template_key} v{document.version}: falta consolidar responsable_revision "
                "y revisada_en en el artefacto publicable"
            )
        elif (
            review.revision_clinica.status == "aprobada"
            and review.revision_juridica.status == "aprobada"
        ):
            reviewers = (
                review.revision_clinica.responsable,
                review.revision_juridica.responsable,
            )
            missing_reviewers = [
                reviewer
                for reviewer in reviewers
                if reviewer and reviewer not in document.responsable_revision
            ]
            if missing_reviewers:
                errors.append(
                    f"{document.template_key} v{document.version}: responsable_revision no "
                    f"incluye a {missing_reviewers}"
                )
            review_dates = [
                reviewed_at
                for reviewed_at in (
                    review.revision_clinica.revisada_en,
                    review.revision_juridica.revisada_en,
                )
                if reviewed_at is not None
            ]
            if review_dates and document.revisada_en < max(review_dates):
                errors.append(
                    f"{document.template_key} v{document.version}: revisada_en es anterior a una "
                    "de las aprobaciones"
                )

    counts = {
        "templates_total": len(documents),
        "revisiones_clinicas_aprobadas": approved_clinical,
        "revisiones_juridicas_aprobadas": approved_legal,
        "consentimientos_informados": document_types.get("consentimiento_informado", 0),
        "autorizaciones": document_types.get("autorizacion", 0),
        "documentos_relacionados": document_types.get("documento_relacionado", 0),
    }
    return {"ok": not errors, "counts": counts, "errors": errors}


def phase6_readiness() -> ReadinessReport:
    return publication_readiness(load_phase6_catalog(), load_phase6_reviews())


def phase7_dermatology_readiness() -> ReadinessReport:
    return publication_readiness(
        load_phase7_dermatology_catalog(),
        load_phase7_dermatology_reviews(),
        expected_keys=PHASE7_DERMATOLOGY_EXPECTED_KEYS,
        package_label="Fase 7 dermatología/estética",
    )
