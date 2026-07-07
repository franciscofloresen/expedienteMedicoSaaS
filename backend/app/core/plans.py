"""Plan entitlements — single source of truth for what each plan unlocks.

The active plan is resolved from the Clerk JWT (`public_metadata.plan`, which is
server-write-only and therefore not user-forgeable) by the tenant middleware and
exposed as ``request.state.plan``. This module maps a plan name to its concrete
entitlements so feature gates read limits from one place instead of hardcoding
them. Adding a Pro benefit = adding a key here and reading it at the gate.

No billing logic lives here — plans are changed out-of-band via
``scripts/upgrade_tenant.py``. Unknown/missing plans fail closed to Básico.
"""

from typing import Any

# Plan name constants (avoid stringly-typed typos like "basico" vs "básico").
BASICO = "basico"
PRO = "pro"

# ``None`` means "unlimited" for numeric limits.
PLANS: dict[str, dict[str, Any]] = {
    BASICO: {
        "max_expedientes": 5,
        "audit_log": False,
    },
    PRO: {
        "max_expedientes": None,
        "audit_log": True,
    },
}

# Entitlements applied to any unknown/missing plan (fail closed to Básico).
_DEFAULT = PLANS[BASICO]


def entitlement(plan: str | None, key: str) -> Any:
    """Return the entitlement value for ``plan``/``key``, defaulting to Básico."""
    plan_map = PLANS.get(plan or BASICO, _DEFAULT)
    return plan_map.get(key, _DEFAULT.get(key))
