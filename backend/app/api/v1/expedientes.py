"""API v1 — Expedientes CRUD (NOM-004)."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_expedientes():
    """List expedientes for the current tenant."""
    return {"detail": "TODO — Week 5-6"}


@router.post("/")
async def create_expediente():
    """Create expediente with auto-generated folio."""
    return {"detail": "TODO — Week 5-6"}


@router.get("/{expediente_id}")
async def get_expediente(expediente_id: str):
    """Get expediente with full clinical history."""
    return {"detail": "TODO — Week 5-6"}
