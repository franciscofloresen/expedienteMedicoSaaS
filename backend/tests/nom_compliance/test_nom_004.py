import pytest
from datetime import date
from pydantic import ValidationError

from app.core.nom_validator import PacienteNOM004, NotaEvolucionNOM004, validar_nota_nom004


def test_paciente_nom004_valid():
    """Test valid patient record against NOM-004."""
    paciente = PacienteNOM004(
        nombre_completo="Juan Perez",
        sexo="M",
        fecha_nacimiento=date(1990, 1, 1),
    )
    assert paciente.nombre_completo == "Juan Perez"


def test_paciente_nom004_invalid_sexo():
    """NOM-004 requires specific biological sex / legal gender values."""
    with pytest.raises(ValidationError):
        PacienteNOM004(
            nombre_completo="Juan Perez",
            sexo="Masculino",  # Should be M, F, or X
            fecha_nacimiento=date(1990, 1, 1),
        )


def test_paciente_nom004_future_dob():
    """Birth date cannot be in the future."""
    with pytest.raises(ValidationError):
        PacienteNOM004(
            nombre_completo="Juan Perez",
            sexo="M",
            fecha_nacimiento=date(2050, 1, 1),
        )


def test_nota_evolucion_valid():
    """Test valid evolution note against NOM-004 §6.2.1."""
    payload = {
        "tipo_nota": "evolucion",
        "evolucion_y_actualizacion_cuadro": "Paciente presenta mejoría significativa...",
        "signos_vitales": {
            "frecuencia_cardiaca": 80,
            "frecuencia_respiratoria": 16,
            "temperatura": 36.5,
            "tension_arterial": "120/80"
        },
        "diagnostico": "Faringitis aguda",
        "tratamiento": "Amoxicilina 500mg c/8h por 7 días"
    }
    
    # Should not raise
    validar_nota_nom004("evolucion", payload)


def test_nota_evolucion_missing_vitals():
    """NOM-004 mandates specific vital signs in evolution notes."""
    payload = {
        "tipo_nota": "evolucion",
        "evolucion_y_actualizacion_cuadro": "Paciente presenta mejoría significativa...",
        "signos_vitales": {
            "frecuencia_cardiaca": 80,
            # Missing others
        },
        "diagnostico": "Faringitis aguda",
        "tratamiento": "Amoxicilina 500mg c/8h por 7 días"
    }
    
    with pytest.raises(ValueError, match="Incumplimiento NOM-004"):
        validar_nota_nom004("evolucion", payload)
