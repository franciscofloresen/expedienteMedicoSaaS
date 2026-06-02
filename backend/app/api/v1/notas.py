"""API v1 — Notas Médicas + Firma Digital (NOM-004 §5.8-§5.14)."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_notas(expediente_id: str | None = None):
    """List notas for an expediente (RLS filtered)."""
    return {"detail": "TODO — Week 5-6"}


@router.post("/")
async def create_nota():
    """Create a medical note (editable until signed)."""
    return {"detail": "TODO — Week 5-6"}


@router.get("/{nota_id}")
async def get_nota(nota_id: str):
    """Get nota detail with signature verification status."""
    return {"detail": "TODO — Week 5-6"}


@router.post("/{nota_id}/firmar")
async def firmar_nota(nota_id: str):
    """
    Sign a note with ECDSA P-256 via KMS.

    This action is IRREVERSIBLE:
    - Sets es_editable = FALSE
    - Stores ECDSA signature + SHA-256 hash
    - Snapshots doctor metadata (nombre, cédula, especialidad)
    - Logs to audit_log
    """
    return {"detail": "TODO — Week 5-6"}


@router.get("/{nota_id}/verificar")
async def verificar_firma(nota_id: str):
    """Verify the digital signature of a signed note."""
    return {"detail": "TODO — Week 5-6"}
