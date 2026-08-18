"""Fase 10 — S3 version recovery preserves signature integrity.

The recovery runbook (§2) requires that after recovering a previous S3 object
version of a signed clinical document, the signature still verifies — that is
the proof the recovery is genuine and not a silently corrupted object.

Signature verification is independent of *where* the bytes live, so this test
models a versioned object store in memory (no S3/moto needed) and asserts:

  * the recovered good version verifies, and
  * a tampered overwrite does NOT verify (hash mismatch),

so "recover the good VersionId → signature valid" is a real, tested guarantee.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from app.services.firma import sign_note, verify_signature


@dataclass
class _VersionedObject:
    """Minimal stand-in for a versioned S3 object (newest-last)."""

    versions: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def put(self, body: dict[str, Any]) -> str:
        version_id = uuid.uuid4().hex
        self.versions.append((version_id, body))
        return version_id

    def get(self, version_id: str) -> dict[str, Any]:
        for vid, body in self.versions:
            if vid == version_id:
                return body
        raise KeyError(version_id)

    @property
    def latest(self) -> dict[str, Any]:
        return self.versions[-1][1]


def _sign_document(content: str) -> dict[str, Any]:
    """Produce a self-describing signed document (what an S3 object would hold)."""
    tenant_id = str(uuid.uuid4())
    nota_id = str(uuid.uuid4())
    result = sign_note(
        content=content,
        tenant_id=tenant_id,
        nota_id=nota_id,
        medico_nombre="Dra. Ana López",
        medico_cedula="1234567",
        medico_especialidad="Dermatología",
    )
    # The verification metadata is exactly what sign_note folded into the hash.
    metadata = {
        "tenant_id": tenant_id,
        "nota_id": nota_id,
        "medico_nombre": result["medico_nombre"],
        "medico_cedula": result["medico_cedula"],
        "medico_especialidad": result["medico_especialidad"],
        "timestamp": result["firmado_en"].isoformat(),
    }
    return {
        "content": content,
        "metadata": metadata,
        "signature": result["firma_digital"],
        "stored_hash": result["firma_hash_contenido"],
        "key_id": result["firma_kms_key_id"],
    }


def _verify(doc: dict[str, Any]) -> bool:
    return verify_signature(
        content=doc["content"],
        metadata=doc["metadata"],
        signature=doc["signature"],
        stored_hash=doc["stored_hash"],
        key_id=doc["key_id"],
    )


def test_recovered_version_signature_still_verifies() -> None:
    obj = _VersionedObject()

    good = _sign_document("Nota clínica firmada — versión buena.")
    good_version_id = obj.put(good)
    assert _verify(good) is True

    # A bad overwrite (e.g. a faulty deploy or accidental corruption): same key,
    # new version, content tampered so its hash no longer matches the signature.
    corrupted = dict(good)
    corrupted["content"] = "Contenido alterado tras la firma."
    obj.put(corrupted)

    # The current (latest) object no longer verifies — this is the failure we recover from.
    assert _verify(obj.latest) is False

    # Recover the good VersionId and confirm the signature validates again.
    recovered = obj.get(good_version_id)
    assert _verify(recovered) is True


def test_tampered_signature_bytes_do_not_verify() -> None:
    doc = _sign_document("Documento firmado.")
    assert _verify(doc) is True

    tampered = dict(doc)
    tampered["signature"] = doc["signature"][:-1] + bytes([doc["signature"][-1] ^ 0x01])
    assert _verify(tampered) is False
