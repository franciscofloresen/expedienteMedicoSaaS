import secrets
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.verification_token import VerificationToken


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
    existing = (
        await db.execute(
            select(VerificationToken).where(
                VerificationToken.tenant_id == tenant_id,
                VerificationToken.resource_type == resource_type,
                VerificationToken.resource_id == resource_id,
            )
        )
    ).scalar_one_or_none()
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
    await db.flush()
    return row, plain_token
