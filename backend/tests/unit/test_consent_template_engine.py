from datetime import date

from app.services.consent_templates import (
    LEGACY_TEMPLATES,
    load_catalog,
    render_consent_content,
    validate_template_fields,
    version_hash,
)


def _legacy_render(template: dict, *, fecha: date) -> str:
    """Frozen copy of the pre-Fase-4 renderer used as the byte-compatibility oracle."""
    procedimiento = "Procedimiento de prueba"
    riesgos = template["riesgos"]
    return (
        f"{template['nombre']}\n\n"
        "Paciente: Paciente Prueba\n"
        f"Procedimiento: {procedimiento}\n"
        "Médico: Dra. Prueba\n"
        "Cédula profesional: 1234567\n"
        f"Fecha: {fecha.isoformat()}\n\n"
        f"Descripción del procedimiento:\n{template['descripcion']}\n\n"
        f"Beneficios esperados:\n{template['beneficios']}\n\n"
        f"Alternativas:\n{template['alternativas']}\n\n"
        f"Riesgos principales:\n{riesgos}\n\n"
        f"Cuidados posteriores:\n{template['cuidados']}\n\n"
        "El paciente declara haber recibido información suficiente sobre el procedimiento, "
        "sus beneficios, alternativas y cuidados posteriores, que resolvió sus dudas y que "
        "ningún resultado médico o estético puede garantizarse.\n\n"
        "CloudMedRecord ayuda a documentar y generar evidencia verificable; este formato no "
        "sustituye asesoría legal ni el criterio clínico del médico tratante."
    )


def test_five_v1_templates_render_byte_identical_to_legacy_engine() -> None:
    documents = load_catalog()
    assert len(documents) == 5
    render_date = date(2026, 7, 15)

    for document in documents:
        legacy = LEGACY_TEMPLATES[document.template_key]
        runtime = document.runtime_template()
        rendered = render_consent_content(
            template=runtime,
            paciente_nombre="Paciente Prueba",
            medico_nombre="Dra. Prueba",
            medico_cedula="1234567",
            procedimiento="Procedimiento de prueba",
            riesgos=runtime["riesgos"],
            fecha=render_date,
        )
        assert runtime == legacy
        assert rendered.encode("utf-8") == _legacy_render(legacy, fecha=render_date).encode("utf-8")


def test_version_hash_is_stable_sha256() -> None:
    document = load_catalog()[0]
    assert version_hash(document) == version_hash(document)
    assert len(version_hash(document)) == 64


def test_required_and_max_length_fields_are_enforced() -> None:
    template = load_catalog()[0].runtime_template()
    assert validate_template_fields(template, {"procedimiento": ""}) == [
        "Procedimiento es obligatorio"
    ]
    errors = validate_template_fields(template, {"procedimiento": "x" * 201})
    assert errors == ["Procedimiento excede 200 caracteres"]
