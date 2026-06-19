from typing import Any, Sequence

from fpdf import FPDF

from app.models.expediente import Expediente
from app.models.nota import Nota
from app.models.paciente import Paciente


class ExpedientePDF(FPDF):
    def __init__(self) -> None:
        super().__init__()
        # Use default Helvetica font (or we could use standard Unicode fonts if needed)
        self.set_auto_page_break(auto=True, margin=15)

    def header(self) -> None:
        self.set_font("helvetica", "B", 14)
        self.set_text_color(0, 122, 255)  # Primary blue
        self.cell(0, 10, "Expediente Clínico Electrónico", border=False, align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 5, "Documento generado automáticamente (NOM-004-SSA3-2012)", border=False, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        page_str = f"Página {self.page_no()}/{{nb}}"
        self.cell(0, 10, page_str, align="C")

    def _render_section_title(self, title: str) -> None:
        self.set_font("helvetica", "B", 12)
        self.set_text_color(0, 0, 0)
        self.set_fill_color(240, 240, 245)
        self.cell(0, 8, f" {title}", border=False, align="L", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def _render_field(self, label: str, value: Any) -> None:
        if not value:
            value = "N/D"
        self.set_font("helvetica", "B", 10)
        self.set_text_color(80, 80, 80)
        self.cell(45, 6, f"{label}:", border=False, align="L")
        self.set_font("helvetica", "", 10)
        self.set_text_color(0, 0, 0)
        self.cell(0, 6, str(value), border=False, align="L", new_x="LMARGIN", new_y="NEXT")


def generate_expediente_pdf(
    paciente: Paciente,
    expediente: Expediente,
    antecedentes: str | None,
    notas: Sequence[Nota]
) -> bytes:
    pdf = ExpedientePDF()
    pdf.add_page()

    # DATOS DEL PACIENTE
    pdf._render_section_title("Datos del Paciente")
    pdf._render_field("Nombre", paciente.nombre_completo)
    pdf._render_field("Fecha Nacimiento", paciente.fecha_nacimiento.strftime("%d/%m/%Y") if paciente.fecha_nacimiento else "")
    pdf._render_field("Sexo", paciente.sexo)
    pdf._render_field("CURP", paciente.curp)
    pdf._render_field("Ocupación", paciente.ocupacion)
    pdf._render_field("Teléfono", paciente.telefono)
    pdf._render_field("Email", paciente.email)
    pdf.ln(5)

    # DATOS DEL EXPEDIENTE
    pdf._render_section_title("Expediente")
    pdf._render_field("Folio", expediente.folio)
    pdf._render_field("Estado", expediente.estado.capitalize() if expediente.estado else "Activo")
    pdf._render_field("Fecha Creación", expediente.creado_en.strftime("%d/%m/%Y %H:%M") if expediente.creado_en else "")
    pdf.ln(5)

    if antecedentes:
        pdf._render_section_title("Antecedentes")
        pdf.set_font("helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 6, antecedentes, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

    # NOTAS CLINICAS
    pdf._render_section_title(f"Notas Clínicas ({len(notas)})")

    for nota in notas:
        pdf.set_fill_color(248, 250, 252)
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(0, 6, f"Nota de {nota.tipo_nota.capitalize()}", fill=True, new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("helvetica", "", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, f"Fecha: {nota.creado_en.strftime('%d/%m/%Y %H:%M') if nota.creado_en else 'N/A'}", new_x="LMARGIN", new_y="NEXT")

        if nota.diagnostico_cie10:
            pdf.cell(0, 5, f"CIE-10: {nota.diagnostico_cie10}", new_x="LMARGIN", new_y="NEXT")

        if nota.signos_vitales:
            sv_str = ", ".join(f"{k}: {v}" for k, v in nota.signos_vitales.items())
            pdf.cell(0, 5, f"Signos Vitales: {sv_str}", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(2)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("helvetica", "", 10)
        pdf.multi_cell(0, 5, nota.contenido, new_x="LMARGIN", new_y="NEXT")

        if not nota.es_editable and nota.firma_hash_contenido:
            pdf.ln(2)
            pdf.set_font("helvetica", "B", 8)
            pdf.set_text_color(0, 128, 0)  # Green
            firmante = nota.medico_nombre or "Médico"
            pdf.cell(0, 5, f"[FIRMADA electrónicamente por {firmante}]", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("helvetica", "", 7)
            pdf.set_text_color(150, 150, 150)
            pdf.cell(0, 4, f"Hash: {nota.firma_hash_contenido}", new_x="LMARGIN", new_y="NEXT")
            if nota.firmado_en:
                pdf.cell(0, 4, f"Firmado en: {nota.firmado_en.strftime('%d/%m/%Y %H:%M:%S')}", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(8)

    # fpdf2 .output() returns a bytearray
    return bytes(pdf.output())
