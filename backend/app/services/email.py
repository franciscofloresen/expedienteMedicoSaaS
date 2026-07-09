"""
Email Service — Appointment (Cita) notifications via Amazon SES.

Delivery is deferred to AFTER the database transaction commits, using a
SQLAlchemy ``after_commit`` hook: if the request rolls back, no mail is sent.
Sending itself is best-effort — a SES failure is logged but never raised, so
notification problems can never break an appointment write.

The sender address must be a verified SES identity in ``settings.aws_region``.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

import boto3
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

if TYPE_CHECKING:
    from app.models.cita import Cita

logger = logging.getLogger("medrecord")

_ses_client = None

# action -> past-participle verb used in the subject/body
_ACTIONS = {
    "creada": "creada",
    "actualizada": "actualizada",
    "cancelada": "cancelada",
}

# Attribute used to stash the per-session pending-email queue.
_QUEUE_ATTR = "_cita_email_queue"


def _get_ses_client() -> Any:
    global _ses_client
    if _ses_client is None:
        _ses_client = boto3.client("ses", region_name=settings.aws_region)
    return _ses_client


def _send(payload: dict) -> None:
    """Perform the actual SES send. Best-effort — never raises."""
    if not settings.ses_sender_email or settings.environment == "testing":
        return
    if not payload.get("to_email"):
        return

    verb = payload["verb"]
    fecha = payload["fecha_inicio"].strftime("%d/%m/%Y %H:%M")
    subject = f"Cita {verb}: {payload['titulo']}"
    # Privacy: keep to the minimum necessary. We deliberately DO NOT include
    # clinical notes (`notas`) — they can carry sensitive patient data and this
    # mail leaves our environment (SES → the doctor's external mailbox).
    body = (
        f"Hola {payload['medico']},\n\n"
        f"Tu cita «{payload['titulo']}» fue {verb}.\n\n"
        f"Fecha: {fecha}\n"
        f"Estado: {payload['estado']}\n"
        "\n—\nEste es un mensaje automático de tu expediente médico."
    )

    try:
        _get_ses_client().send_email(
            Source=settings.ses_sender_email,
            Destination={"ToAddresses": [payload["to_email"]]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
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
) -> dict:
    """Capture primitives NOW — after commit the ORM row may be gone (DELETE)."""
    # Note: `notas` is intentionally not captured — see _send (privacy).
    return {
        "to_email": to_email,
        "medico": medico or "Doctor(a)",
        "titulo": cita.titulo,
        "fecha_inicio": cita.fecha_inicio,
        "estado": cita.estado,
        "cita_id": str(cita.id),
        "action": action,
        "verb": _ACTIONS[action],
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
