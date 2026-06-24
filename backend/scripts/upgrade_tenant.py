import argparse
import asyncio
import logging
import sys

from sqlalchemy import select

from app.core.config import settings
from app.db.session import _get_session_factory
from app.models.tenant import Tenant

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def upgrade_tenant(email: str, plan: str = "pro") -> None:
    """Actualiza el plan de un Tenant en BD y en Clerk (idempotente)."""
    factory = _get_session_factory()
    async with factory() as db:
        stmt = select(Tenant).where(Tenant.email == email)
        result = await db.execute(stmt)
        tenant = result.scalar_one_or_none()

        if not tenant:
            logger.error(f"❌ No se encontró ningún médico con el correo: {email}")
            sys.exit(1)

        if tenant.plan == plan:
            logger.info(
                f"✅ El médico {email} ya se encuentra en el plan '{plan}'. No hay nada que hacer."
            )
            return

        logger.info(
            f"Subiendo a '{plan}' la cuenta de {tenant.nombre_medico} ({email})..."
        )

        # 1. Preparar Base de datos
        tenant.plan = plan

        # 2. Update Clerk Metadata
        if not settings.clerk_secret_key:
            logger.warning(
                "⚠️ No se encontró CLERK_SECRET_KEY, omitiendo sincronización con Clerk."
            )
            # Si no hay llave de Clerk, hacemos commit aquí y salimos
            await db.commit()
            logger.info(f"✅ Base de datos actualizada (plan={plan}).")
            return

        if not tenant.clerk_id:
            logger.warning(
                "⚠️ El tenant no tiene clerk_id asociado. No se sincronizará con Clerk."
            )
            await db.commit()
            logger.info(f"✅ Base de datos actualizada (plan={plan}).")
            return

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.patch(
                    f"https://api.clerk.com/v1/users/{tenant.clerk_id}/metadata",
                    headers={
                        "Authorization": f"Bearer {settings.clerk_secret_key}",
                        "Content-Type": "application/json",
                    },
                    json={"public_metadata": {"plan": plan}},
                )
                resp.raise_for_status()

            # 3. Clerk respondió OK, ahora sí hacemos commit en PostgreSQL
            await db.commit()
            logger.info(f"✅ Base de datos actualizada (plan={plan}).")
            logger.info("✅ Clerk public_metadata actualizado con éxito.")
            logger.info("🎉 Cuenta actualizada correctamente.")

        except Exception as e:
            logger.error(f"❌ Error actualizando Clerk: {e}")
            logger.info(
                "  -> Revierte el plan en BD si es estrictamente necesario, aunque al siguiente login intentará usar el de BD."
            )
            sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Actualizar manualmente un médico a plan Pro"
    )
    parser.add_argument("email", help="Correo electrónico del médico a actualizar")
    parser.add_argument(
        "--plan", default="pro", help="Nombre del plan (por defecto: pro)"
    )
    args = parser.parse_args()

    asyncio.run(upgrade_tenant(args.email, args.plan))


if __name__ == "__main__":
    main()
