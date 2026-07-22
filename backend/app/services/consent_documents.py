"""Build and persist the one final PDF for a signed consent."""

import base64
import hashlib
import html
from dataclasses import dataclass
from io import BytesIO
from typing import Any, cast

from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.config import settings
from app.models.consentimiento import Consentimiento
from app.models.consentimiento_evidencia import ConsentimientoFirmante
from app.models.expediente import Expediente
from app.models.paciente import Paciente
from app.services.clinical_storage import get_s3_client


@dataclass(frozen=True)
class StoredConsentDocument:
    bucket: str
    key: str
    version_id: str | None
    etag: str | None
    sha256: str
    size_bytes: int


def _qr_drawing(url: str) -> Drawing:
    widget = qr.QrCodeWidget(url)
    x1, y1, x2, y2 = widget.getBounds()
    size = 30 * mm
    drawing = Drawing(size, size, transform=[size / (x2 - x1), 0, 0, size / (y2 - y1), 0, 0])
    drawing.add(widget)
    return drawing


def _signature_image(value: str) -> Image | None:
    if not value.startswith(("data:image/png;base64,", "data:image/jpeg;base64,")):
        return None
    try:
        raw = base64.b64decode(value.split(",", 1)[1], validate=True)
        return Image(BytesIO(raw), width=42 * mm, height=16 * mm, kind="proportional")
    except Exception:  # A malformed legacy image remains hashed but is not rendered.
        return None


def build_final_consent_pdf(
    *,
    consentimiento: Consentimiento,
    paciente: Paciente,
    expediente: Expediente,
    firmantes: list[ConsentimientoFirmante],
    verification_url: str,
) -> bytes:
    """Render the exact final artifact. It is called once, only during finalization."""
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Consentimiento {consentimiento.id}",
        author="CloudMedRecord",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("ConsentTitle", parent=styles["Title"], alignment=TA_CENTER)
    small = ParagraphStyle("ConsentSmall", parent=styles["BodyText"], fontSize=8, leading=10)
    body = ParagraphStyle("ConsentBody", parent=styles["BodyText"], fontSize=9.5, leading=13)
    story: list[Any] = [
        Paragraph("CloudMedRecord", title),
        Paragraph("Consentimiento informado firmado y verificable", styles["Heading2"]),
        Spacer(1, 4 * mm),
        Table(
            [
                ["Folio", f"CONS-{str(consentimiento.id)[:8].upper()}"],
                ["Paciente", paciente.nombre_completo],
                ["Expediente", expediente.folio],
                ["Procedimiento", consentimiento.procedimiento],
                ["Médico", consentimiento.medico_nombre or ""],
                [
                    "Cédula / especialidad",
                    f"{consentimiento.medico_cedula or ''} / {consentimiento.medico_especialidad or 'General'}",
                ],
                [
                    "Firmado",
                    consentimiento.firmado_medico_en.isoformat()
                    if consentimiento.firmado_medico_en
                    else "",
                ],
            ],
            colWidths=[42 * mm, 125 * mm],
            style=TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#ECEFF1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("LEADING", (0, 0), (-1, -1), 10),
                ]
            ),
        ),
        Spacer(1, 6 * mm),
        Paragraph(html.escape(consentimiento.contenido_renderizado).replace("\n", "<br/>"), body),
        Spacer(1, 7 * mm),
        Paragraph("Firmantes", styles["Heading3"]),
    ]
    signer_rows: list[list[Any]] = [["Calidad", "Nombre / relación", "Firma"]]
    for signer in sorted(firmantes, key=lambda item: (item.tipo == "testigo", item.orden)):
        relation = signer.relacion_paciente or ""
        signer_rows.append(
            [
                signer.tipo.capitalize(),
                Paragraph(
                    html.escape(f"{signer.nombre}{' — ' + relation if relation else ''}"), small
                ),
                _signature_image(signer.firma_base64)
                or Paragraph(f"Evidencia SHA-256: {signer.firma_sha256[:16]}…", small),
            ]
        )
    signer_rows.append(
        [
            "Médico",
            Paragraph(
                html.escape(
                    f"{consentimiento.medico_nombre or ''} — Cédula {consentimiento.medico_cedula or ''}"
                ),
                small,
            ),
            Paragraph("Firma digital ECDSA P-256", small),
        ]
    )
    story.extend(
        [
            Table(
                signer_rows,
                colWidths=[28 * mm, 82 * mm, 57 * mm],
                repeatRows=1,
                style=TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ECEFF1")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ]
                ),
            ),
            Spacer(1, 7 * mm),
            Table(
                [
                    [
                        _qr_drawing(verification_url),
                        Paragraph(
                            "<b>Verificación pública</b><br/>"
                            + html.escape(verification_url)
                            + "<br/><br/><b>Hash firmado SHA-256</b><br/>"
                            + html.escape(consentimiento.hash_contenido or ""),
                            small,
                        ),
                    ]
                ],
                colWidths=[38 * mm, 129 * mm],
                style=TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]),
            ),
            Spacer(1, 3 * mm),
            Paragraph(
                "El original permanece inmutable. Una revocación se registra como evento relacionado y no altera este documento.",
                small,
            ),
        ]
    )
    doc.build(story)
    return output.getvalue()


def store_final_consent_pdf(
    *, tenant_id: str, consentimiento_id: str, pdf_bytes: bytes
) -> StoredConsentDocument:
    key = f"tenants/{tenant_id}/consentimientos/{consentimiento_id}/final.pdf"
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    if settings.environment in {"development", "testing"}:
        return StoredConsentDocument(
            bucket=settings.s3_consent_bucket,
            key=key,
            version_id="local-test-version",
            etag=digest,
            sha256=digest,
            size_bytes=len(pdf_bytes),
        )
    response = get_s3_client().put_object(
        Bucket=settings.s3_consent_bucket,
        Key=key,
        Body=pdf_bytes,
        ContentType="application/pdf",
        Metadata={"sha256": digest, "document-type": "consentimiento-final"},
    )
    return StoredConsentDocument(
        bucket=settings.s3_consent_bucket,
        key=key,
        version_id=cast(str | None, response.get("VersionId")),
        etag=cast(str | None, response.get("ETag")),
        sha256=digest,
        size_bytes=len(pdf_bytes),
    )


def final_consent_download_url(*, key: str, version_id: str | None) -> str:
    if settings.environment in {"development", "testing"}:
        return f"https://local.invalid/{key}?versionId={version_id or ''}"
    params: dict[str, str] = {
        "Bucket": settings.s3_consent_bucket,
        "Key": key,
        "ResponseContentType": "application/pdf",
        "ResponseContentDisposition": 'inline; filename="consentimiento-firmado.pdf"',
    }
    if version_id:
        params["VersionId"] = version_id
    return cast(
        str,
        get_s3_client().generate_presigned_url(
            "get_object", Params=params, ExpiresIn=settings.file_signed_url_ttl_seconds
        ),
    )
