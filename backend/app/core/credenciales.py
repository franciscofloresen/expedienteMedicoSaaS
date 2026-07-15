"""Credential-number normalization, shared by the app and the Fase 1 migration.

The normalized form is what ``medico_credenciales.numero_normalizado`` stores and
what per-médico uniqueness is enforced on (§5.1). The migration backfill computes the
same value in SQL, so the rule here and there MUST stay in lockstep:

    Python:  re.sub(r"\\s+", "", numero).upper()
    SQL:     upper(regexp_replace(numero, '\\s+', '', 'g'))

Keep them identical if this ever changes.
"""

import re

_WHITESPACE = re.compile(r"\s+")


def normalize_credential_number(numero: str) -> str:
    """Return the canonical form used for duplicate detection.

    Strips all whitespace and uppercases. Cédulas are digits today, but credentials
    of ``tipo`` other than ``general`` may be alphanumeric, so uppercasing matters.
    """
    return _WHITESPACE.sub("", numero or "").upper()
