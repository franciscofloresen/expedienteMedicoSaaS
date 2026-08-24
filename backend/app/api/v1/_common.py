"""Helpers shared by the v1 routers.

`tenant_uuid` used to be copied into five routers in two different versions: the
newer ones raised a clean 403, the older ones let the ValueError escape as an
unhandled 500. A 500 leaves the Lambda without CORS headers, so the browser
reports it as a CORS failure — the exact misdiagnosis documented as CRIT-04. The
weaker copies were in notas, recetas and consentimientos, i.e. the three signable
documents. One implementation removes that difference.
"""

import uuid

from fastapi import HTTPException, Request


def tenant_uuid(request: Request) -> uuid.UUID:
    """Return the request's tenant as a UUID.

    TenantMiddleware sets ``request.state.tenant_id`` from the validated JWT, so a
    missing or malformed value means the request never acquired a tenant context —
    a 403, never a 500.
    """
    try:
        return uuid.UUID(str(request.state.tenant_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=403, detail="Contexto de clínica inválido") from exc
