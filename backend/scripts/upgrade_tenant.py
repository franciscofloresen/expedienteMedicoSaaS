import argparse
import asyncio
import logging
import sys
from typing import Any

from sqlalchemy import select

from app.db.session import _get_session_factory
from app.models.tenant import Tenant

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def _apply_plan(db: Any, tenant: Tenant, plan: str) -> None:
    """Set a tenant's plan in the DB and sync it to Clerk (idempotent).

    Commits the DB only after Clerk succeeds when a Clerk key + clerk_id exist,
    so PostgreSQL and Clerk never diverge.
    """
    if tenant.plan == plan:
        logger.info(
            f"✅ El médico {tenant.email} ya se encuentra en el plan '{plan}'. "
            "No hay nada que hacer."
        )
        return

    logger.info(
        f"Cambiando a '{plan}' la cuenta de {tenant.nombre_medico} "
        f"({tenant.email}, id={tenant.id})..."
    )

    # 1. Prepare the database change (not committed yet).
    tenant.plan = plan

    # 2. Sync Clerk public_metadata so the next JWT carries the new plan.
    from app.core.config import get_clerk_secret_key

    clerk_secret_key = get_clerk_secret_key()
    if not clerk_secret_key:
        logger.warning("⚠️ No se encontró CLERK_SECRET_KEY, omitiendo sincronización con Clerk.")
        await db.commit()
        logger.info(f"✅ Base de datos actualizada (plan={plan}).")
        return

    if not tenant.clerk_id:
        logger.warning("⚠️ El tenant no tiene clerk_id asociado. No se sincronizará con Clerk.")
        await db.commit()
        logger.info(f"✅ Base de datos actualizada (plan={plan}).")
        return

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"https://api.clerk.com/v1/users/{tenant.clerk_id}/metadata",
                headers={
                    "Authorization": f"Bearer {clerk_secret_key}",
                    "Content-Type": "application/json",
                },
                json={"public_metadata": {"plan": plan}},
            )
            resp.raise_for_status()

        # 3. Clerk succeeded — now commit PostgreSQL.
        await db.commit()
        logger.info(f"✅ Base de datos actualizada (plan={plan}).")
        logger.info("✅ Clerk public_metadata actualizado con éxito.")
        logger.info("🎉 Cuenta actualizada correctamente.")
    except Exception as e:
        logger.error(f"❌ Error actualizando Clerk: {e}")
        sys.exit(1)


async def upgrade_tenant(email: str, plan: str = "pro") -> None:
    """Actualiza el plan de un Tenant (buscado por email) en BD y en Clerk."""
    factory = _get_session_factory()
    async with factory() as db:
        stmt = select(Tenant).where(Tenant.email == email)
        tenant = (await db.execute(stmt)).scalar_one_or_none()

        if not tenant:
            logger.error(f"❌ No se encontró ningún médico con el correo: {email}")
            sys.exit(1)

        await _apply_plan(db, tenant, plan)


async def upgrade_tenant_by_id(tenant_id: str, plan: str = "pro") -> None:
    """Actualiza el plan de un Tenant (buscado por id) en BD y en Clerk.

    Útil cuando el email del tenant es sintético ("*.local") y no se puede
    buscar por correo (p. ej. identidades duplicadas de Clerk).
    """
    factory = _get_session_factory()
    async with factory() as db:
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        tenant = (await db.execute(stmt)).scalar_one_or_none()

        if not tenant:
            logger.error(f"❌ No se encontró ningún tenant con el id: {tenant_id}")
            sys.exit(1)

        await _apply_plan(db, tenant, plan)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Actualizar manualmente el plan de un médico (por email o id)"
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("email", nargs="?", help="Correo electrónico del médico")
    target.add_argument("--tenant-id", help="ID (UUID) del tenant a actualizar")
    parser.add_argument("--plan", default="pro", help="Nombre del plan (por defecto: pro)")
    args = parser.parse_args()

    if args.tenant_id:
        asyncio.run(upgrade_tenant_by_id(args.tenant_id, args.plan))
    else:
        asyncio.run(upgrade_tenant(args.email, args.plan))


if __name__ == "__main__":
    main()
