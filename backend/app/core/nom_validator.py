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
        # TODO: Add validators for other note types (ingreso, egreso, etc.)
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
