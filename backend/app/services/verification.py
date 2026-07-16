import secrets
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.verification_token import VerificationToken


def public_verification_url(token: str) -> str:
    """Build the public verification URL for a QR/link.

    Must point at the frontend web app (not the API host): scanning the QR opens
    the branded /verify/:token page, which then fetches the minimal metadata from
    the API. Using the API's request.base_url would (a) render raw JSON and (b)
    behind API Gateway omits the stage path, yielding {"message":"Forbidden"}.

    cors_origins[0] already carries the frontend origin in every environment
    (prod: https://<frontend_url>; dev default: http://localhost:5173).
    """
    base = settings.cors_origins[0].rstrip("/") if settings.cors_origins else ""
    return f"{base}/verify/{token}"


async def get_or_create_verification_token(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    resource_type: str,
    resource_id: uuid.UUID,
    public_metadata: dict[str, Any] | None = None,
) -> tuple[VerificationToken, str]:
    """Return the verification token for a resource, minting it once if needed.

    A signed document has exactly one verification token. Signing creates it;
    reprinting or re-previewing reuses the same row instead of inserting a new
    one, so the printed QR/URL stays stable and no orphan tokens accumulate.

    The token value is public by design (it is printed as a QR on the document),
    so it is stored in plaintext to allow the same URL to be regenerated on each
    print. It grants read access only to minimal, non-clinical metadata.
    """
    # Reuse the earliest existing token. Uses first() rather than
    # scalar_one_or_none() so pre-existing duplicate rows — left by the original
    # insert-on-every-call behaviour before this became get-or-create — resolve to
    # a single stable token instead of raising MultipleResultsFound.
    # A signing caller may already have marked its clinical row immutable in memory.
    # Do not let this lookup auto-flush that row before its token FK is attached.
    with db.no_autoflush:
        existing = (
            await db.execute(
                select(VerificationToken)
                .where(
                    VerificationToken.tenant_id == tenant_id,
                    VerificationToken.resource_type == resource_type,
                    VerificationToken.resource_id == resource_id,
                )
                .order_by(VerificationToken.created_at.asc())
                .limit(1)
            )
        ).scalars().first()
    if existing is not None:
        return existing, existing.token

    plain_token = secrets.token_urlsafe(32)
    row = VerificationToken(
        tenant_id=tenant_id,
        resource_type=resource_type,
        resource_id=resource_id,
        token=plain_token,
        public_metadata=public_metadata,
        status="active",
    )
    db.add(row)
    # Flush only the token. In signing flows the clinical document is dirty too;
    # flushing the whole session here would lock it before verification_token_id is
    # attached and recreate the historical firmar/immutability failure.
    await db.flush([row])
    return row, plain_token
