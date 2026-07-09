"""
DANGER — one-off environment reset ops.

Two independent, token-guarded operations, invoked via the Lambda handler
(see app.main.handler) following the project's admin-ops pattern (Lambda
script + invoke, never Alembic DELETEs):

  * wipe_all_data("WIPE-ALL-DATA")      — TRUNCATE every tenant-scoped table
  * purge_clerk_users("PURGE-CLERK-USERS") — delete every user in the Clerk
                                            instance (external API)

Both refuse to run without their exact confirmation token. Intended for
resetting an environment that only holds disposable/fake data. ALWAYS take an
RDS snapshot first.
"""

import argparse
import asyncio
import logging
from typing import Any

from sqlalchemy import text

from app.db.session import _get_session_factory

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

WIPE_CONFIRM = "WIPE-ALL-DATA"
PURGE_CONFIRM = "PURGE-CLERK-USERS"


async def wipe_all_data(confirm: str) -> dict[str, Any]:
    """TRUNCATE all tenant-scoped tables + `tenants`. Keeps seed/reference
    tables (no tenant_id column) and alembic_version untouched."""
    if confirm != WIPE_CONFIRM:
        raise ValueError(f"Confirmation phrase '{WIPE_CONFIRM}' required.")

    factory = _get_session_factory()
    async with factory() as db:
        # Every table with a tenant_id column is tenant data; add the root table.
        rows = (
            await db.execute(
                text(
                    "SELECT table_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND column_name = 'tenant_id'"
                )
            )
        ).all()
        tables = sorted({r[0] for r in rows} | {"tenants"})

        before: dict[str, int] = {}
        for t in tables:
            try:
                before[t] = (
                    await db.execute(text(f'SELECT count(*) FROM "{t}"'))  # noqa: S608
                ).scalar_one()
            except Exception:  # noqa: BLE001
                before[t] = -1

        quoted = ", ".join(f'"{t}"' for t in tables)
        # CASCADE covers any child table not caught by the tenant_id heuristic.
        await db.execute(text(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE"))  # noqa: S608
        await db.commit()

        logger.info(f"Wiped {len(tables)} tables: {tables}")
        return {"wiped_tables": tables, "rows_before": before}


async def purge_clerk_users(confirm: str) -> dict[str, Any]:
    """Delete every user in the Clerk instance via the Clerk Backend API."""
    if confirm != PURGE_CONFIRM:
        raise ValueError(f"Confirmation phrase '{PURGE_CONFIRM}' required.")

    import httpx

    from app.core.config import settings

    if not settings.clerk_secret_key:
        raise RuntimeError("CLERK_SECRET_KEY is not configured.")

    headers = {"Authorization": f"Bearer {settings.clerk_secret_key}"}
    deleted = 0
    errors: list[dict[str, str]] = []

    async with httpx.AsyncClient(timeout=30) as client:
        offset = 0
        while True:
            resp = await client.get(
                "https://api.clerk.com/v1/users",
                headers=headers,
                params={"limit": 100, "offset": offset},
            )
            resp.raise_for_status()
            users = resp.json()
            if not users:
                break
            for u in users:
                uid = u.get("id")
                try:
                    d = await client.delete(
                        f"https://api.clerk.com/v1/users/{uid}", headers=headers
                    )
                    d.raise_for_status()
                    deleted += 1
                except Exception as e:  # noqa: BLE001
                    errors.append({str(uid): str(e)})
            if len(users) < 100:
                break
            offset += len(users)

    logger.info(f"Purged {deleted} Clerk users ({len(errors)} errors).")
    return {"deleted": deleted, "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser(description="One-off environment reset ops")
    sub = parser.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("wipe-data")
    w.add_argument("--confirm", required=True)
    p = sub.add_parser("purge-clerk")
    p.add_argument("--confirm", required=True)
    args = parser.parse_args()

    if args.cmd == "wipe-data":
        print(asyncio.run(wipe_all_data(args.confirm)))
    elif args.cmd == "purge-clerk":
        print(asyncio.run(purge_clerk_users(args.confirm)))


if __name__ == "__main__":
    main()
