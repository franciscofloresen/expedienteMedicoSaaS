"""Pydantic models for the patient-data export format (portabilidad LFPDPPP).

``formato_version`` is a contract with the doctor: any breaking change to these
models requires bumping it. Raw signature bytes (``firma_digital``) are never
exported — the hash, algorithm and public verification URL are what allow an
exported document to be checked against the original.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel

FORMATO_VERSION = "1.0"


class ConsultorioExport(BaseModel):
    nombre_medico: str
    cedula: str | None = None
    especialidad: str | None = None


class PacienteExport(BaseModel):
    id: str
    nombre_completo: str
    fecha_nacimiento: date
    sexo: str
    curp: str | None = None
    entidad_nacimiento: str | None = None
    nacionalidad: str | None = None
    ocupacion: str | None = None
    telefono: str | None = None
    email: str | None = None
    aseguradora: str | None = None
    num_poliza: str | None = None
    contacto_emergencia: str | None = None
    telefono_emergencia: str | None = None
    tipo_sangre: str | None = None
    alergias: str | None = None
    creado_en: datetime | None = None


class ExpedienteExport(BaseModel):
    id: str
    folio: str
    estado: str
    antecedentes: str | None = None
    creado_en: datetime | None = None


class FirmaExport(BaseModel):
    """Verifiable signature metadata — never the raw signature bytes."""

    firmado: bool
    hash_contenido: str | None = None
    algoritmo: str | None = None
    firmado_en: datetime | None = None
    verification_url: str | None = None


class EncuentroExport(BaseModel):
    id: str
    cita_id: str | None = None
    tipo: str
    estado: str
    clasificacion_origen: str
    nota_inicial_id: str | None = None
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None
    creado_en: datetime | None = None


class DiagnosticoExport(BaseModel):
    cie10_code: str
    descripcion: str | None = None
    es_principal: bool
    certeza: str
    orden: int


class NotaExport(BaseModel):
    id: str
    encuentro_clinico_id: str | None = None
    tipo_nota: str
    estado: str
    contenido: dict[str, Any] | str | None = None
    motivo_consulta: str | None = None
    exploracion_fisica: str | None = None
    plan_tratamiento: str | None = None
    signos_vitales: dict[str, Any] | None = None
    diagnostico_cie10: str | None = None
    diagnosticos: list[DiagnosticoExport] = []
    medico_nombre: str | None = None
    medico_cedula: str | None = None
    medico_especialidad: str | None = None
    firma: FirmaExport
    creado_en: datetime | None = None


class RecetaExport(BaseModel):
    id: str
    nota_id: str
    medicamentos: list[dict[str, Any]]
    indicaciones_generales: str | None = None
    medico_nombre: str | None = None
    medico_cedula: str | None = None
    medico_especialidad: str | None = None
    firma: FirmaExport
    creado_en: datetime | None = None


class FirmanteExport(BaseModel):
    """Human-signature evidence. The stroke image itself travels only inside the
    final signed PDF (``documentos_finales``); here we export its SHA-256."""

    tipo: str
    orden: int
    nombre: str
    relacion_paciente: str | None = None
    firma_sha256: str
    firmado_en: datetime | None = None


class RevocacionExport(BaseModel):
    motivo: str
    actor_nombre: str
    actor_tipo: str
    revocado_en: datetime | None = None


class ConsentimientoExport(BaseModel):
    id: str
    template_key: str
    version: str
    procedimiento: str
    status: str
    riesgos_principales: str | None = None
    contenido_renderizado: str
    firmado_paciente_nombre: str | None = None
    firmado_paciente_en: datetime | None = None
    firmado_medico_en: datetime | None = None
    medico_nombre: str | None = None
    medico_cedula: str | None = None
    medico_especialidad: str | None = None
    firmantes: list[FirmanteExport] = []
    revocacion: RevocacionExport | None = None
    firma: FirmaExport
    creado_en: datetime | None = None


class ChecklistExport(BaseModel):
    id: str
    encuentro_id: str | None = None
    momento: str
    items: list[Any]
    observaciones: str | None = None
    creado_en: datetime | None = None
    modificado_en: datetime | None = None


class EventoAdversoExport(BaseModel):
    id: str
    encuentro_id: str | None = None
    descripcion: str
    severidad: str
    fecha: date | None = None
    manejo: str | None = None
    estado: str
    creado_en: datetime | None = None
    modificado_en: datetime | None = None


class ProcedimientosExport(BaseModel):
    checklists: list[ChecklistExport] = []
    eventos_adversos: list[EventoAdversoExport] = []


class ArchivoExport(BaseModel):
    id: str
    nombre_original: str
    content_type: str
    tamano_bytes: int
    categoria: str
    creado_en: datetime | None = None
    # A file whose antimalware state is not "available" is listed with its real
    # estado and url = null — a blocked file never gets a download URL.
    estado: str
    url: str | None = None
    url_expira_en: int | None = None


class FotografiaExport(BaseModel):
    id: str
    clinical_file_id: str
    consentimiento_id: str | None = None
    categoria: str
    lateralidad: str | None = None
    zona_anatomica: str | None = None
    fecha_toma: date | None = None
    grupo_comparacion: str | None = None
    nombre_original: str
    content_type: str
    tamano_bytes: int
    estado: str
    url: str | None = None
    url_expira_en: int | None = None


class DocumentoFinalExport(BaseModel):
    consentimiento_id: str
    content_type: str
    tamano_bytes: int
    contenido_sha256: str
    creado_en: datetime | None = None
    url: str | None = None
    url_expira_en: int | None = None


class ExportacionExpediente(BaseModel):
    formato_version: str = FORMATO_VERSION
    generado_en: datetime
    consultorio: ConsultorioExport
    paciente: PacienteExport
    expediente: ExpedienteExport
    encuentros: list[EncuentroExport] = []
    notas: list[NotaExport] = []
    recetas: list[RecetaExport] = []
    consentimientos: list[ConsentimientoExport] = []
    procedimientos: ProcedimientosExport = ProcedimientosExport()
    archivos: list[ArchivoExport] = []
    fotografias: list[FotografiaExport] = []
    documentos_finales: list[DocumentoFinalExport] = []


class IndicePacienteExport(BaseModel):
    paciente_id: str
    nombre_completo: str
    expediente_id: str
    folio: str
    conteos: dict[str, int]
    exportacion_url: str


class IndiceConsultorioExport(BaseModel):
    formato_version: str = FORMATO_VERSION
    generado_en: datetime
    consultorio: ConsultorioExport
    pacientes: list[IndicePacienteExport] = []
    # Keyset cursor: pass back as ?cursor= to fetch the next page; null = done.
    next_cursor: str | None = None
