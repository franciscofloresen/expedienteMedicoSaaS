"""
Email Service — Appointment (Cita) notifications via Amazon SES.

Delivery is deferred to AFTER the database transaction commits, using a
SQLAlchemy ``after_commit`` hook: if the request rolls back, no mail is sent.
Sending itself is best-effort — a SES failure is logged but never raised, so
notification problems can never break an appointment write.

The sender address must be a verified SES identity in ``settings.aws_region``.
"""

import html
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

import boto3
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

if TYPE_CHECKING:
    from app.models.cita import Cita

logger = logging.getLogger("medrecord")

_ses_client = None

# Appointment display timezone: Mexico central time (UTC-6, no DST since 2022).
# Stored datetimes are UTC; we convert for the doctor-facing email.
try:
    from zoneinfo import ZoneInfo

    _MX_TZ: Any = ZoneInfo("America/Mexico_City")
except Exception:  # pragma: no cover - tz database unavailable on the runtime
    _MX_TZ = timezone(timedelta(hours=-6))

# Per-action presentation, in Mexican Spanish.
_ACTIONS: dict[str, dict[str, str]] = {
    "creada": {
        "label": "agendada",
        "badge": "Agendada",
        "color": "#0F9D8C",
        "headline": "Tu cita fue agendada",
        "intro": "Se registró una nueva cita en tu agenda.",
    },
    "actualizada": {
        "label": "actualizada",
        "badge": "Actualizada",
        "color": "#B8860B",
        "headline": "Tu cita fue actualizada",
        "intro": "Se modificaron los datos de una cita en tu agenda.",
    },
    "cancelada": {
        "label": "cancelada",
        "badge": "Cancelada",
        "color": "#C0392B",
        "headline": "Tu cita fue cancelada",
        "intro": "Se canceló una cita de tu agenda.",
    },
}

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _to_mx(dt: datetime) -> datetime:
    """Convert a stored datetime (naive treated as UTC) to Mexico central time."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_MX_TZ)


def _fecha_larga(dt: datetime) -> str:
    return f"{_DIAS[dt.weekday()]}, {dt.day} de {_MESES[dt.month - 1]} de {dt.year}"


def _hora(dt: datetime) -> str:
    h = dt.strftime("%I:%M").lstrip("0")
    return f"{h} {'a.m.' if dt.hour < 12 else 'p.m.'}"


# Attribute used to stash the per-session pending-email queue.
_QUEUE_ATTR = "_cita_email_queue"


def _get_ses_client() -> Any:
    global _ses_client
    if _ses_client is None:
        _ses_client = boto3.client("ses", region_name=settings.aws_region)
    return _ses_client


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_deliverable(email: Optional[str]) -> bool:
    """True only for addresses SES could actually deliver to.

    Rejects the synthetic `*.local` fallbacks the tenant middleware assigns when
    a Clerk token has no email claim — sending to those "succeeds" at the SES API
    but never reaches an inbox.
    """
    if not email:
        return False
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        return False
    domain = email.rsplit("@", 1)[-1]
    if domain.endswith((".local", ".test", ".invalid", ".localhost")):
        return False
    return True


def _build_message(payload: dict[str, Any]) -> tuple[str, str, str]:
    """Return (subject, text_body, html_body) in Mexican Spanish.

    Privacy: only the minimum necessary (título, fecha, horario, estado). Clinical
    notes are never included — the mail leaves our environment to an external inbox.
    """
    meta = _ACTIONS[payload["action"]]
    inicio = _to_mx(payload["fecha_inicio"])
    fin = _to_mx(payload["fecha_fin"]) if payload.get("fecha_fin") else None

    fecha_larga = _fecha_larga(inicio)
    horario = _hora(inicio) + (f" a {_hora(fin)}" if fin else "")
    titulo = payload["titulo"]
    estado = payload["estado"]
    medico = payload["medico"]

    subject = f"Cita {meta['label']}: {titulo}"

    text_body = (
        f"{meta['headline']}\n\n"
        f"Hola, {medico}:\n\n"
        f"{meta['intro']}\n\n"
        f"Título:  {titulo}\n"
        f"Fecha:   {fecha_larga}\n"
        f"Horario: {horario}\n"
        f"Estado:  {estado}\n\n"
        "Puedes ver y administrar tus citas en CloudMedRecord.\n\n"
        "—\n"
        "Mensaje automático, por favor no respondas a este correo.\n"
        "CloudMedRecord · Expediente Clínico"
    )

    html_body = _html_template(
        meta=meta,
        medico=medico,
        titulo=titulo,
        fecha_larga=fecha_larga,
        horario=horario,
        estado=estado,
    )
    return subject, text_body, html_body


def _html_template(
    *,
    meta: dict[str, str],
    medico: str,
    titulo: str,
    fecha_larga: str,
    horario: str,
    estado: str,
) -> str:
    color = meta["color"]
    e_medico = html.escape(medico)
    e_titulo = html.escape(titulo)
    e_estado = html.escape(estado)
    font = (
        "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,"
        "sans-serif"
    )

    def row(label: str, value: str) -> str:
        return (
            '<tr>'
            f'<td style="padding:10px 0;border-bottom:1px solid #eceff3;'
            f'color:#6b7280;font-size:13px;width:90px;vertical-align:top;">{label}</td>'
            f'<td style="padding:10px 0;border-bottom:1px solid #eceff3;'
            f'color:#111827;font-size:15px;font-weight:600;">{value}</td>'
            '</tr>'
        )

    return f"""\
<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:{font};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{html.escape(meta['headline'])} · {e_titulo}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:24px 12px;">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border:1px solid #e6e9ef;border-radius:14px;overflow:hidden;">
<tr><td style="height:4px;background:{color};font-size:0;line-height:0;">&nbsp;</td></tr>
<tr><td style="padding:28px 32px 8px;">
<div style="font-size:18px;font-weight:700;color:#0BA99B;letter-spacing:-0.01em;">CloudMedRecord</div>
<div style="font-size:10px;font-weight:600;letter-spacing:0.14em;color:#9aa3b2;text-transform:uppercase;margin-top:2px;">Expediente Clínico</div>
</td></tr>
<tr><td style="padding:12px 32px 0;">
<span style="display:inline-block;background:{color}1a;color:{color};font-size:12px;font-weight:700;letter-spacing:0.02em;padding:5px 12px;border-radius:999px;">{meta['badge']}</span>
<h1 style="margin:14px 0 4px;font-size:22px;line-height:1.25;color:#111827;font-weight:700;">{meta['headline']}</h1>
</td></tr>
<tr><td style="padding:8px 32px 0;color:#4b5563;font-size:15px;line-height:1.6;">
Hola, <strong>{e_medico}</strong>:<br>{meta['intro']}
</td></tr>
<tr><td style="padding:20px 32px 4px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
 style="background:#f9fafb;border:1px solid #eceff3;border-radius:10px;padding:6px 18px;">
{row("Título", e_titulo)}
{row("Fecha", fecha_larga)}
{row("Horario", horario + " (hora del centro de México)")}
<tr><td style="padding:10px 0;color:#6b7280;font-size:13px;vertical-align:top;">Estado</td>
<td style="padding:10px 0;"><span style="color:{color};font-size:14px;font-weight:700;">{e_estado}</span></td></tr>
</table>
</td></tr>
<tr><td style="padding:22px 32px 30px;color:#6b7280;font-size:13px;line-height:1.6;">
Puedes ver y administrar tus citas desde tu panel en CloudMedRecord.
</td></tr>
<tr><td style="padding:18px 32px;background:#f9fafb;border-top:1px solid #eceff3;color:#9aa3b2;font-size:12px;line-height:1.6;">
Mensaje automático, por favor no respondas a este correo.<br>
© CloudMedRecord — Expediente Clínico Electrónico (NOM-004 / NOM-024).
</td></tr>
</table>
</td></tr></table>
</body></html>"""


def _send(payload: dict[str, Any]) -> None:
    """Perform the actual SES send. Best-effort — never raises."""
    if not settings.ses_sender_email or settings.environment == "testing":
        return
    if not is_deliverable(payload.get("to_email")):
        logger.warning(
            f"Cita {payload['cita_id']}: destino no entregable "
            f"({payload.get('to_email')!r}) — no se envía notificación."
        )
        return

    subject, text_body, html_body = _build_message(payload)

    try:
        _get_ses_client().send_email(
            Source=settings.ses_sender_email,
            Destination={"ToAddresses": [payload["to_email"]]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": text_body, "Charset": "UTF-8"},
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                },
            },
        )
        logger.info(
            f"Notificación de cita '{payload['action']}' enviada para "
            f"{payload['cita_id']}"
        )
    except Exception as e:  # noqa: BLE001 — best-effort, never break the write
        logger.error(f"SES send falló para cita {payload['cita_id']}: {e}")


def _snapshot(
    to_email: str, medico: Optional[str], cita: "Cita", action: str
) -> dict[str, Any]:
    """Capture primitives NOW — after commit the ORM row may be gone (DELETE)."""
    # Note: `notas` is intentionally not captured — see _send (privacy).
    return {
        "to_email": to_email,
        "medico": medico or "Doctor(a)",
        "titulo": cita.titulo,
        "fecha_inicio": cita.fecha_inicio,
        "fecha_fin": cita.fecha_fin,
        "estado": cita.estado,
        "cita_id": str(cita.id),
        "action": action,
    }


def queue_cita_notification(
    db: AsyncSession,
    to_email: str,
    medico: Optional[str],
    cita: "Cita",
    action: str,
) -> None:
    """
    Schedule a doctor notification to be sent AFTER the current transaction
    commits. If the transaction rolls back, nothing is sent.

    action: one of "creada", "actualizada", "cancelada".
    """
    if action not in _ACTIONS:
        logger.error(f"queue_cita_notification: acción desconocida '{action}'")
        return

    payload = _snapshot(to_email, medico, cita, action)

    # Events attach to the underlying sync Session; after_commit fires when the
    # request's `async with session.begin()` block commits during teardown.
    sync_session = db.sync_session
    pending = getattr(sync_session, _QUEUE_ATTR, None)
    if pending is None:
        pending = []
        setattr(sync_session, _QUEUE_ATTR, pending)

        @event.listens_for(sync_session, "after_commit")
        def _flush(session: Any) -> None:
            queued = getattr(session, _QUEUE_ATTR, [])
            setattr(session, _QUEUE_ATTR, [])
            for p in queued:
                _send(p)

    pending.append(payload)
