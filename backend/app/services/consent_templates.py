"""Validation, canonical hashing and deterministic rendering for consent templates."""

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

_BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = _BACKEND_DIR / "app" / "data" / "consent_templates.json"


class ConsentField(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    type: Literal["text", "textarea", "boolean"]
    required: bool = False
    max_length: int | None = Field(default=None, ge=1, le=10_000)


class ConsentContent(BaseModel):
    descripcion: str = Field(min_length=1)
    beneficios: str = Field(min_length=1)
    alternativas: str = Field(min_length=1)
    cuidados: str = Field(min_length=1)
    riesgos: str = Field(min_length=1)
    declaracion: str = Field(min_length=1)
    aviso_producto: str = Field(min_length=1)


class RequiredSignatures(BaseModel):
    paciente: bool = True
    medico: bool = True
    testigos: int = Field(default=0, ge=0, le=2)


class ConsentTemplateDocument(BaseModel):
    template_key: str = Field(pattern=r"^[a-z0-9_]+$", max_length=80)
    categoria: str = Field(min_length=1, max_length=80)
    especialidad: str | None = Field(default=None, max_length=100)
    procedimiento: str | None = Field(default=None, max_length=160)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+$", max_length=20)
    nombre: str = Field(min_length=1, max_length=200)
    contenido: ConsentContent
    campos: list[ConsentField]
    firmas_requeridas: RequiredSignatures
    referencias_normativas: list[str] = Field(default_factory=list)
    responsable_revision: str | None = Field(default=None, max_length=200)
    revisada_en: datetime | None = None

    @model_validator(mode="after")
    def validate_unique_fields(self) -> "ConsentTemplateDocument":
        keys = [field.key for field in self.campos]
        if len(keys) != len(set(keys)):
            raise ValueError("Los campos de una plantilla deben tener keys únicas")
        if "procedimiento" not in keys:
            raise ValueError("Toda plantilla debe declarar el campo procedimiento")
        return self

    def runtime_template(self) -> dict[str, Any]:
        """Backward-compatible shape consumed by the current API and renderer."""
        return {
            "nombre": self.nombre,
            "version": self.version,
            **self.contenido.model_dump(),
            "campos": [field.model_dump() for field in self.campos],
            "firmas_requeridas": self.firmas_requeridas.model_dump(),
        }


def load_catalog(path: Path = DEFAULT_CATALOG_PATH) -> list[ConsentTemplateDocument]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("El catálogo debe ser un arreglo JSON")
    documents = [ConsentTemplateDocument.model_validate(item) for item in raw]
    identities = [(doc.template_key, doc.version) for doc in documents]
    if len(identities) != len(set(identities)):
        raise ValueError("El catálogo contiene template_key/version duplicados")
    return documents


def canonical_version_payload(document: ConsentTemplateDocument) -> dict[str, Any]:
    """Return every publication field protected by the immutable SHA-256 hash."""
    return {
        "template_key": document.template_key,
        "version": document.version,
        "nombre": document.nombre,
        "contenido": document.contenido.model_dump(),
        "campos": [field.model_dump() for field in document.campos],
        "firmas_requeridas": document.firmas_requeridas.model_dump(),
        "referencias_normativas": document.referencias_normativas,
        "responsable_revision": document.responsable_revision,
        "revisada_en": document.revisada_en.isoformat() if document.revisada_en else None,
    }


def version_hash(document: ConsentTemplateDocument) -> str:
    canonical = json.dumps(
        canonical_version_payload(document),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def runtime_template_from_row(version: Any) -> dict[str, Any]:
    """Adapt an ORM version row to the legacy renderer without coupling it to SQLAlchemy."""
    content = dict(version.contenido)
    return {
        "nombre": version.nombre,
        "version": version.version,
        **content,
        "campos": list(version.campos),
        "firmas_requeridas": dict(version.firmas_requeridas),
    }


def validate_template_fields(template: dict[str, Any], values: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in template.get("campos", []):
        value = values.get(field["key"])
        if field.get("required") and (value is None or str(value).strip() == ""):
            errors.append(f"{field['label']} es obligatorio")
            continue
        max_length = field.get("max_length")
        if value is not None and max_length and len(str(value)) > int(max_length):
            errors.append(f"{field['label']} excede {max_length} caracteres")
    return errors


def render_consent_content(
    *,
    template: dict[str, Any],
    paciente_nombre: str,
    medico_nombre: str,
    medico_cedula: str,
    procedimiento: str,
    riesgos: str,
    fecha: date | None = None,
) -> str:
    """Render deterministically; this is byte-identical to the pre-Fase-4 renderer."""
    render_date = fecha or date.today()
    return (
        f"{template['nombre']}\n\n"
        f"Paciente: {paciente_nombre}\n"
        f"Procedimiento: {procedimiento}\n"
        f"Médico: {medico_nombre}\n"
        f"Cédula profesional: {medico_cedula}\n"
        f"Fecha: {render_date.isoformat()}\n\n"
        f"Descripción del procedimiento:\n{template['descripcion']}\n\n"
        f"Beneficios esperados:\n{template['beneficios']}\n\n"
        f"Alternativas:\n{template['alternativas']}\n\n"
        f"Riesgos principales:\n{riesgos}\n\n"
        f"Cuidados posteriores:\n{template['cuidados']}\n\n"
        f"{template['declaracion']}\n\n"
        f"{template['aviso_producto']}"
    )


# Temporary production fallback. It is deliberately independent from the JSON import
# artifact: equivalence tests compare both sources byte-for-byte before rollout.
_DECLARACION = (
    "El paciente declara haber recibido información suficiente sobre el procedimiento, "
    "sus beneficios, alternativas y cuidados posteriores, que resolvió sus dudas y que "
    "ningún resultado médico o estético puede garantizarse."
)
_AVISO = (
    "CloudMedRecord ayuda a documentar y generar evidencia verificable; este formato no "
    "sustituye asesoría legal ni el criterio clínico del médico tratante."
)
_FIELDS = [
    {
        "key": "procedimiento",
        "label": "Procedimiento",
        "type": "text",
        "required": True,
        "max_length": 200,
    },
    {
        "key": "riesgos_principales",
        "label": "Riesgos principales",
        "type": "textarea",
        "required": False,
        "max_length": 10_000,
    },
]
_SIGNATURES = {"paciente": True, "medico": True, "testigos": 0}

LEGACY_TEMPLATES: dict[str, dict[str, Any]] = {
    "general_atencion": {
        "nombre": "Consentimiento general de atención médica",
        "version": "1.0",
        "descripcion": "Autorización para valoración clínica, exploración física e indicación de estudios o tratamiento conforme al criterio del médico tratante.",
        "beneficios": "Diagnóstico oportuno, plan de manejo personalizado y seguimiento del padecimiento.",
        "alternativas": "No recibir atención, solicitar una segunda opinión o ser referido a otra unidad médica.",
        "cuidados": "Seguir las indicaciones entregadas, acudir a las citas de control y reportar cualquier dato de alarma.",
        "riesgos": "Molestias propias de la exploración, reacciones no previstas y necesidad de estudios o referencia.",
        "declaracion": _DECLARACION,
        "aviso_producto": _AVISO,
        "campos": _FIELDS,
        "firmas_requeridas": _SIGNATURES,
    },
    "estetico_no_quirurgico": {
        "nombre": "Procedimiento estético no quirúrgico",
        "version": "1.0",
        "descripcion": "Procedimiento estético sin cirugía (peelings, aparatología o tratamientos faciales) cuyo resultado depende de la respuesta individual de cada paciente.",
        "beneficios": "Mejoría del aspecto de la piel o de la zona tratada, sin tiempos de recuperación quirúrgicos.",
        "alternativas": "Otros tratamientos estéticos, manejo quirúrgico o no realizar el procedimiento.",
        "cuidados": "Evitar sol directo, usar protector solar, seguir la rutina indicada y no manipular la zona tratada.",
        "riesgos": "Inflamación, dolor, equimosis, asimetría, infección, reacción alérgica o resultado distinto al esperado.",
        "declaracion": _DECLARACION,
        "aviso_producto": _AVISO,
        "campos": _FIELDS,
        "firmas_requeridas": _SIGNATURES,
    },
    "toxina_botulinica": {
        "nombre": "Aplicación de toxina botulínica",
        "version": "1.0",
        "descripcion": "Aplicación de toxina botulínica tipo A mediante microinyecciones para relajar músculos y atenuar arrugas de expresión. El efecto es temporal (aprox. 3 a 6 meses).",
        "beneficios": "Suavizado de líneas de expresión y prevención de arrugas dinámicas.",
        "alternativas": "Rellenos, tratamientos con aparatología o no aplicar la toxina.",
        "cuidados": "No agacharse ni hacer ejercicio intenso las primeras horas, no masajear la zona y mantenerse erguido.",
        "riesgos": "Dolor, equimosis, cefalea, asimetría, ptosis temporal, reacción local o necesidad de retoque.",
        "declaracion": _DECLARACION,
        "aviso_producto": _AVISO,
        "campos": _FIELDS,
        "firmas_requeridas": _SIGNATURES,
    },
    "relleno_acido_hialuronico": {
        "nombre": "Relleno con ácido hialurónico",
        "version": "1.0",
        "descripcion": "Aplicación de ácido hialurónico para dar volumen, hidratar o corregir contornos faciales. Es reabsorbible y su duración varía según la zona y el producto.",
        "beneficios": "Restauración de volumen, hidratación y armonización de los rasgos faciales.",
        "alternativas": "Toxina botulínica, bioestimuladores, procedimientos quirúrgicos o no realizar el relleno.",
        "cuidados": "Aplicar frío si se indica, evitar calor extremo y ejercicio intenso, y no presionar la zona tratada.",
        "riesgos": "Inflamación, equimosis, nódulos, asimetría, infección, compromiso vascular y necesidad de disolución.",
        "declaracion": _DECLARACION,
        "aviso_producto": _AVISO,
        "campos": _FIELDS,
        "firmas_requeridas": _SIGNATURES,
    },
    "dermatologico": {
        "nombre": "Tratamiento dermatológico",
        "version": "1.0",
        "descripcion": "Indicación de tratamiento dermatológico (tópico, oral o en consultorio) para el manejo de la condición de piel diagnosticada, con seguimiento por el médico tratante.",
        "beneficios": "Control de la enfermedad cutánea, mejoría de los síntomas y del aspecto de la piel.",
        "alternativas": "Otros esquemas terapéuticos, manejo expectante o una segunda opinión dermatológica.",
        "cuidados": "Aplicar los productos según indicación, usar protector solar y reportar irritación o falta de mejoría.",
        "riesgos": "Irritación, ardor, resequedad, manchas, reacción alérgica, falta de respuesta o recaída.",
        "declaracion": _DECLARACION,
        "aviso_producto": _AVISO,
        "campos": _FIELDS,
        "firmas_requeridas": _SIGNATURES,
    },
}
