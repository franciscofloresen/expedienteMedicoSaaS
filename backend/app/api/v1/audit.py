"""API v1 — Audit Log (read-only view over CloudWatch Logs Insights).

CloudWatch + pgaudit own the durable audit trail at the infrastructure level.
This endpoint only *surfaces* those logs to the frontend, scoped to the current
tenant. It performs NO writes and never creates a table or SQL row.
"""

import logging
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.core.config import settings
from app.core.plans import entitlement

logger = logging.getLogger("medrecord.audit")

router = APIRouter()


# ── Pydantic Schema ──


class AuditEntry(BaseModel):
    timestamp: datetime
    action: str  # e.g. "GET /api/v1/patients", "POST /api/v1/encounters"
    user_email: str
    ip_address: str
    status_code: int


# ── CloudWatch Logs Insights ──

_logs_client = None


def _get_logs_client() -> Any:
    import boto3

    global _logs_client
    if _logs_client is None:
        _logs_client = boto3.client("logs", region_name=settings.aws_region)
    return _logs_client


def _row_to_dict(row: list[dict[str, str]]) -> dict[str, str]:
    """CloudWatch returns each result row as a list of {field, value} pairs."""
    return {col["field"]: col["value"] for col in row}


def _parse_timestamp(value: str) -> datetime:
    # Logs Insights emits "@timestamp" as "YYYY-MM-DD HH:MM:SS.mmm".
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    # ISO-8601 fallback
    return datetime.fromisoformat(value)


def _query_cloudwatch(tenant_id: str, limit: int, offset: int) -> list[AuditEntry]:
    """Run a tenant-scoped Logs Insights query. Returns [] on any failure."""
    if not settings.cloudwatch_log_group:
        # No log group configured (e.g. local/testing) — nothing to surface.
        return []

    client = _get_logs_client()
    end_time = int(time.time())
    start_time = end_time - settings.cloudwatch_audit_window_days * 24 * 3600

    # Tenant scoping is enforced inside the query: only this tenant's rows match.
    query_string = (
        "fields @timestamp, tenant_id, action, user_email, ip_address, status_code "
        f"| filter tenant_id = '{tenant_id}' "
        "| sort @timestamp desc "
        f"| limit {offset + limit}"
    )

    start = client.start_query(
        logGroupName=settings.cloudwatch_log_group,
        startTime=start_time,
        endTime=end_time,
        queryString=query_string,
    )
    query_id = start["queryId"]

    # Poll for completion (Insights queries are asynchronous).
    deadline = time.time() + 25
    results: list[list[dict[str, str]]] = []
    while time.time() < deadline:
        response = client.get_query_results(queryId=query_id)
        status = response.get("status")
        if status == "Complete":
            results = response.get("results", [])
            break
        if status in ("Failed", "Cancelled", "Timeout"):
            logger.warning("Audit query %s ended with status %s", query_id, status)
            return []
        time.sleep(0.3)

    entries: list[AuditEntry] = []
    for row in results:
        data = _row_to_dict(row)
        try:
            entries.append(
                AuditEntry(
                    timestamp=_parse_timestamp(data["@timestamp"]),
                    action=data.get("action", ""),
                    user_email=data.get("user_email", ""),
                    ip_address=data.get("ip_address", ""),
                    status_code=int(data.get("status_code") or 0),
                )
            )
        except (KeyError, ValueError) as e:
            # Skip malformed rows rather than failing the whole request.
            logger.debug("Skipping malformed audit row: %s", e)

    # Insights has no native OFFSET — apply it after fetching offset+limit rows.
    return entries[offset : offset + limit]


# ── Endpoints ──


@router.get("/", response_model=list[AuditEntry])
async def list_audit(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[AuditEntry]:
    """Return recent audit activity for the current tenant (read-only).

    Sourced from CloudWatch Logs Insights and filtered by the JWT tenant_id.
    Returns an empty list (never 500) when there is nothing to show or the
    log backend is unavailable.
    """
    tenant_id = request.state.tenant_id

    # Pro-only feature.
    plan = getattr(request.state, "plan", "basico")
    if not entitlement(plan, "audit_log"):
        raise HTTPException(
            status_code=403,
            detail="El registro de auditoría está disponible sólo en el plan Pro.",
        )

    try:
        return _query_cloudwatch(str(tenant_id), limit, offset)
    except Exception as e:  # noqa: BLE001 — read endpoint must not 500
        logger.warning("Audit query failed for tenant %s: %s", tenant_id, e)
        return []
