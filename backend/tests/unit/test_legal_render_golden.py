"""Fase 11 — golden render of the medical-legal signed payload.

The canonical serialization in ``app.services.firma`` is what gets hashed and
signed for every note/consent. If its byte layout ever drifts, historical
signatures stop verifying — a medical-legal regression. These golden tests pin
the exact bytes and hash for a fixed input, and lock the two properties the
format guarantees: key-order independence and UTC timezone determinism.

If a change here is intentional, it is a format migration, not a test to relax:
existing signed documents were produced under the old bytes and must still
verify against them.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.firma import canonical_serialize, compute_content_hash

# Fixed legal payload (accented Spanish included, since UTF-8 is part of the contract).
_CONTENT = "Paciente con cefalea. Diagnóstico: migraña."
_METADATA = {
    "tenant_id": "11111111-1111-1111-1111-111111111111",
    "nota_id": "22222222-2222-2222-2222-222222222222",
    "medico_nombre": "Dra. Ana López",
    "medico_cedula": "1234567",
    "medico_especialidad": "Neurología",
    "timestamp": "2026-08-18T15:30:00+00:00",
}

_GOLDEN_BYTES = (
    '{"contenido":"Paciente con cefalea. Diagnóstico: migraña.",'
    '"metadata":{"medico_cedula":"1234567","medico_especialidad":"Neurología",'
    '"medico_nombre":"Dra. Ana López","nota_id":"22222222-2222-2222-2222-222222222222",'
    '"tenant_id":"11111111-1111-1111-1111-111111111111",'
    '"timestamp":"2026-08-18T15:30:00+00:00"}}'
).encode("utf-8")

_GOLDEN_HASH = "bcebf1d7544e00b53ec5a3174c30efd587afad9cfc48e7bdb0fe2e58fca56a3a"


def test_canonical_bytes_match_golden() -> None:
    assert canonical_serialize(_CONTENT, _METADATA) == _GOLDEN_BYTES


def test_canonical_hash_matches_golden() -> None:
    assert compute_content_hash(canonical_serialize(_CONTENT, _METADATA)) == _GOLDEN_HASH


def test_metadata_key_order_does_not_change_the_hash() -> None:
    """Two dicts with the same entries in different insertion order sign identically."""
    reordered = dict(reversed(list(_METADATA.items())))
    assert reordered != _METADATA or list(reordered) != list(_METADATA)  # order differs
    assert compute_content_hash(
        canonical_serialize(_CONTENT, reordered)
    ) == _GOLDEN_HASH


def test_same_instant_in_different_timezones_hashes_identically() -> None:
    """A signing timestamp normalized to UTC yields one hash regardless of the
    originating timezone — no drift from local-time rendering."""
    instant_utc = datetime(2026, 8, 18, 15, 30, 0, tzinfo=timezone.utc)
    # The same instant expressed in a -06:00 offset (e.g. Mexico City).
    instant_offset = instant_utc.astimezone(timezone(timedelta(hours=-6)))

    meta_utc = {**_METADATA, "timestamp": instant_utc.isoformat()}
    meta_norm = {**_METADATA, "timestamp": instant_offset.astimezone(timezone.utc).isoformat()}

    assert instant_offset.isoformat() != instant_utc.isoformat()  # different rendering
    assert compute_content_hash(canonical_serialize(_CONTENT, meta_utc)) == _GOLDEN_HASH
    assert compute_content_hash(
        canonical_serialize(_CONTENT, meta_norm)
    ) == compute_content_hash(canonical_serialize(_CONTENT, meta_utc))
