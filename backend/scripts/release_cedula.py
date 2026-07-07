import argparse
import asyncio
import logging
import sys

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.session import _get_session_factory
from app.models.tenant import Tenant

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class TenantHasDataError(Exception):
    """El tenant tiene datos clínicos asociados y no debe borrarse a ciegas."""


async def release_cedula(cedula: str) -> str:
    """Libera una cédula borrando el tenant huérfano que la ocupa (idempotente).

    Seguridad: si el tenant tiene pacientes/citas/expedientes/recetas/notas,
    el DELETE viola las llaves foráneas (sin ON DELETE CASCADE) y se aborta,
    de modo que NUNCA se borran datos clínicos por accidente.
    """
    cedula = str(cedula).strip()
    factory = _get_session_factory()
    async with factory() as db:
        stmt = select(Tenant).where(Tenant.cedula == cedula)
        tenant = (await db.execute(stmt)).scalar_one_or_none()

        # Idempotente: si no existe, la cédula ya está libre.
        if tenant is None:
            msg = (
                f"La cédula {cedula} ya está libre (no existe ningún tenant). "
                "Nada que hacer."
            )
            logger.info(f"✅ {msg}")
            return msg

        logger.info(
            f"Encontrado tenant {tenant.id} "
            f"({tenant.email} / {tenant.nombre_medico}) con cédula {cedula}. Borrando..."
        )

        await db.delete(tenant)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise TenantHasDataError(
                f"El tenant con cédula {cedula} tiene datos asociados "
                "(pacientes/citas/expedientes/recetas/notas). NO se borró nada. "
                "Revísalo manualmente antes de continuar."
            )

        msg = f"Tenant con cédula {cedula} eliminado. La cédula quedó libre para re-registro."
        logger.info(f"✅ {msg}")
        return msg


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Liberar una cédula borrando el tenant huérfano que la ocupa"
    )
    parser.add_argument("cedula", help="Cédula del tenant a liberar")
    args = parser.parse_args()

    try:
        asyncio.run(release_cedula(args.cedula))
    except TenantHasDataError as e:
        logger.error(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
