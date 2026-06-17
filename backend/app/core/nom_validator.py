"""
NOM-004-SSA3-2012 Compliance Validator

Validates that medical records and notes contain the minimum
mandatory fields required by the Mexican official standard.
"""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PacienteNOM004(BaseModel):
    """Minimum required fields for a patient record (NOM-004 §5.3.1)."""

    nombre_completo: str = Field(..., min_length=2, max_length=200)
    sexo: str = Field(..., pattern="^(M|F|X)$")
    fecha_nacimiento: date
    domicilio_cifrado: bytes | None = None  # Cifrado con AES-GCM

    @field_validator("fecha_nacimiento")
    def validate_fecha_nacimiento(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("La fecha de nacimiento no puede ser en el futuro")
        return v


class NotaEvolucionNOM004(BaseModel):
    """Minimum fields for an evolution note (NOM-004 §6.2.1)."""

    tipo_nota: str = Field(default="evolucion", pattern="^evolucion$")
    evolucion_y_actualizacion_cuadro: str = Field(..., min_length=10)
    signos_vitales: dict[str, Any] = Field(...)
    resultados_estudios: str | None = None
    diagnostico: str = Field(..., min_length=5)
    tratamiento: str = Field(..., min_length=5)

    @field_validator("signos_vitales")
    def validate_signos_vitales(cls, v: dict[str, Any]) -> dict[str, Any]:
        """NOM-004 requires minimum vital signs."""
        required = {"frecuencia_cardiaca", "frecuencia_respiratoria", "temperatura", "tension_arterial"}
        missing = required - set(v.keys())
        if missing:
            raise ValueError(f"Faltan signos vitales obligatorios (NOM-004): {missing}")
        return v


class NotaInterconsultaNOM004(BaseModel):
    """Minimum fields for a consultation note (NOM-004 §6.3.1)."""

    tipo_nota: str = Field(default="interconsulta", pattern="^interconsulta$")
    criterio_diagnostico: str = Field(..., min_length=10)
    plan_estudios: str | None = None
    sugerencias_diagnosticas: str = Field(..., min_length=5)
    tratamiento: str = Field(..., min_length=5)
    motivo_consulta: str = Field(..., min_length=5)


class NotaIngresoNOM004(BaseModel):
    """Minimum fields for an admission note (NOM-004 §6.1)."""

    tipo_nota: str = Field(default="ingreso", pattern="^ingreso$")
    signos_vitales: dict[str, Any] = Field(...)
    resumen_interrogatorio: str = Field(..., min_length=10,
        description="Resumen del interrogatorio y exploración física")
    resultados_estudios: str | None = None
    diagnostico_ingreso: str = Field(..., min_length=5,
        description="Diagnóstico(s) de ingreso")
    plan_manejo: str = Field(..., min_length=5,
        description="Plan de manejo y tratamiento")

    @field_validator("signos_vitales")
    def validate_signos_vitales(cls, v: dict[str, Any]) -> dict[str, Any]:
        required = {"frecuencia_cardiaca", "frecuencia_respiratoria", "temperatura", "tension_arterial"}
        missing = required - set(v.keys())
        if missing:
            raise ValueError(f"Faltan signos vitales obligatorios (NOM-004 §6.1): {missing}")
        return v


class NotaEgresoNOM004(BaseModel):
    """Minimum fields for a discharge note (NOM-004 §6.4)."""

    tipo_nota: str = Field(default="egreso", pattern="^egreso$")
    motivo_egreso: str = Field(..., min_length=5,
        description="Motivo del egreso (mejoría, máximo beneficio, voluntario, defunción, etc.)")
    diagnostico_final: str = Field(..., min_length=5,
        description="Diagnóstico(s) final(es)")
    resumen_evolucion: str = Field(..., min_length=10,
        description="Resumen de la evolución y estado actual")
    plan_manejo_ambulatorio: str = Field(..., min_length=5,
        description="Plan de manejo ambulatorio, medicamentos, indicaciones")
    pronostico: str | None = Field(None,
        description="Pronóstico al egreso")


class NotaQuirurgicaNOM004(BaseModel):
    """Minimum fields for a surgical note (NOM-004 §6.5)."""

    tipo_nota: str = Field(default="quirurgica", pattern="^quirurgica$")
    diagnostico_preoperatorio: str = Field(..., min_length=5)
    operacion_planeada: str = Field(..., min_length=5,
        description="Operación planeada")
    operacion_realizada: str = Field(..., min_length=5,
        description="Operación realizada (puede diferir de la planeada)")
    hallazgos: str = Field(..., min_length=5,
        description="Hallazgos transoperatorios")
    incidentes_accidentes: str | None = Field(None,
        description="Descripción de incidentes o accidentes durante la cirugía")
    diagnostico_postoperatorio: str = Field(..., min_length=5)
    estado_postquirurgico: str = Field(..., min_length=5,
        description="Estado post-quirúrgico inmediato")
    plan_manejo: str = Field(..., min_length=5,
        description="Plan de manejo postoperatorio")


class NotaAnestesiologiaNOM004(BaseModel):
    """Minimum fields for an anesthesiology note (NOM-004)."""

    tipo_nota: str = Field(default="anestesiologia", pattern="^anestesiologia$")
    evaluacion_clinica: str = Field(..., min_length=5,
        description="Evaluación clínica del riesgo anestésico")
    tipo_anestesia: str = Field(..., min_length=5,
        description="Tipo de anestesia empleada")
    signos_vitales: dict[str, Any] = Field(...)
    incidentes_accidentes: str | None = Field(None,
        description="Incidentes o accidentes durante la anestesia")
    medicamentos_administrados: str = Field(..., min_length=5,
        description="Medicamentos administrados y dosificación")
    estado_egreso: str = Field(..., min_length=5,
        description="Estado clínico del paciente al egreso de la sala")

    @field_validator("signos_vitales")
    def validate_signos_vitales(cls, v: dict[str, Any]) -> dict[str, Any]:
        required = {"frecuencia_cardiaca", "frecuencia_respiratoria", "temperatura", "tension_arterial"}
        missing = required - set(v.keys())
        if missing:
            raise ValueError(f"Faltan signos vitales obligatorios (NOM-004): {missing}")
        return v


class NotaHistoriaClinicaNOM004(BaseModel):
    """Minimum fields for a clinical history note (NOM-004 §5.4)."""

    tipo_nota: str = Field(default="historia_clinica", pattern="^historia_clinica$")
    interrogatorio: str = Field(..., min_length=10,
        description="Interrogatorio por aparatos y sistemas")
    exploracion_fisica: str = Field(..., min_length=10,
        description="Exploración física completa")
    diagnostico: str = Field(..., min_length=5,
        description="Diagnóstico(s) presuntivo(s) o definitivo(s)")
    plan_estudio: str | None = Field(None,
        description="Plan de estudio (laboratorios, gabinete)")
    plan_tratamiento: str = Field(..., min_length=5,
        description="Plan de tratamiento")
    pronostico: str | None = Field(None,
        description="Pronóstico")


def validar_nota_nom004(tipo_nota: str, contenido: dict[str, Any]) -> None:
    """
    Validates a note payload against the corresponding NOM-004 schema.

    Args:
        tipo_nota: The type of note (e.g., 'evolucion', 'interconsulta')
        contenido: The parsed JSON content of the note

    Raises:
        ValueError: If validation fails
    """
    validators = {
        "evolucion": NotaEvolucionNOM004,
        "interconsulta": NotaInterconsultaNOM004,
        "ingreso": NotaIngresoNOM004,
        "egreso": NotaEgresoNOM004,
        "quirurgica": NotaQuirurgicaNOM004,
        "anestesiologia": NotaAnestesiologiaNOM004,
        "historia_clinica": NotaHistoriaClinicaNOM004,
    }

    validator_class = validators.get(tipo_nota)
    if not validator_class:
        # If no specific validator exists, allow generic but warn/log
        # In a real scenario, all types from NOM-004 should be implemented
        return

    try:
        validator_class.model_validate(contenido)
    except Exception as e:
        raise ValueError(f"Incumplimiento NOM-004 para nota '{tipo_nota}': {str(e)}")
