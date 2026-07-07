import argparse
import asyncio
import json
import logging
import sys

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.db.session import _get_session_factory
from app.models.tenant import Tenant

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class TenantHasDataError(Exception):
    """El tenant tiene datos clínicos asociados y no debe borrarse a ciegas."""


async def _count_related_rows(db, tenant_id) -> dict[str, int]:
    """Cuenta filas de cada tabla que referencia tenants.id para este tenant.

    Descubre las FK dinámicamente (no depende de nombres hardcodeados) y fija el
    contexto RLS para que las tablas con FORCE ROW LEVEL SECURITY sean visibles.
    """
    # Fija el tenant actual para que las políticas RLS dejen ver las filas hijas.
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    fk_rows = (
        await db.execute(
            text(
                """
                SELECT tc.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON tc.constraint_name = ccu.constraint_name
                 AND tc.table_schema = ccu.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND ccu.table_name = 'tenants'
                  AND ccu.column_name = 'id'
                """
            )
        )
    ).all()

    counts: dict[str, int] = {}
    for table_name, column_name in fk_rows:
        try:
            n = (
                await db.execute(
                    # table_name/column_name vienen de information_schema (catálogo
                    # confiable), no de input del usuario → interpolación segura.
                    text(
                        f'SELECT count(*) FROM "{table_name}" WHERE "{column_name}" = :tid'  # noqa: S608
                    ),
                    {"tid": str(tenant_id)},
                )
            ).scalar_one()
        except Exception:  # noqa: BLE001 — no pudimos contar (permisos/RLS); no bloquear
            n = -1
        if n != 0:
            counts[f"{table_name}.{column_name}"] = int(n)
    return counts


async def inspect_cedula(cedula: str) -> dict:
    """Read-only: reporta identidad del tenant y datos asociados. No borra nada."""
    cedula = str(cedula).strip()
    factory = _get_session_factory()
    async with factory() as db:
        stmt = select(Tenant).where(Tenant.cedula == cedula)
        tenant = (await db.execute(stmt)).scalar_one_or_none()
        if tenant is None:
            return {"cedula": cedula, "exists": False}

        related = await _count_related_rows(db, tenant.id)
        return {
            "cedula": cedula,
            "exists": True,
            "tenant_id": str(tenant.id),
            "email": tenant.email,
            "nombre_medico": tenant.nombre_medico,
            "clerk_id": getattr(tenant, "clerk_id", None),
            "plan": getattr(tenant, "plan", None),
            "created_at": str(getattr(tenant, "created_at", None)),
            "related_rows": related,
            "has_data": bool(related),
        }


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

        tenant_id = tenant.id
        identity = f"{tenant.email} / {tenant.nombre_medico}"
        logger.info(
            f"Encontrado tenant {tenant_id} ({identity}) con cédula {cedula}. Borrando..."
        )

        await db.delete(tenant)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            related = await _count_related_rows(db, tenant_id)
            raise TenantHasDataError(
                f"El tenant con cédula {cedula} ({identity}, id={tenant_id}) tiene "
                f"datos asociados y NO se borró nada. Desglose: {related or 'desconocido'}. "
                "Revísalo manualmente antes de continuar."
            ) from None

        msg = f"Tenant con cédula {cedula} eliminado. La cédula quedó libre para re-registro."
        logger.info(f"✅ {msg}")
        return msg


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspeccionar o liberar la cédula de un tenant"
    )
    parser.add_argument("cedula", help="Cédula del tenant")
    parser.add_argument(
        "--action",
        choices=["inspect", "release"],
        default="inspect",
        help="inspect (solo lectura, por defecto) o release (borra el tenant)",
    )
    args = parser.parse_args()

    if args.action == "inspect":
        result = asyncio.run(inspect_cedula(args.cedula))
        logger.info(json.dumps(result, ensure_ascii=False, indent=2))
        return

    try:
        asyncio.run(release_cedula(args.cedula))
    except TenantHasDataError as e:
        logger.error(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
