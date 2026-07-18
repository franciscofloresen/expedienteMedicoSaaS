import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.consentimientos import _evidence_for_consents, templates
from app.core.clinical_rollout import ROLLOUT_STEPS, feature_enabled, rollout_summary
from app.core.config import settings
from app.main import app
from app.models.consentimiento_evidencia import (
    ConsentimientoDocumentoFinal,
    ConsentimientoFirmante,
    ConsentimientoRevocacion,
)
from scripts.verify_registry import available_actions


class _ScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalars(self) -> "_ScalarResult":
        return self

    def all(self) -> list[object]:
        return self._rows


class _FakeSession:
    def __init__(self, responses: list[list[object]]) -> None:
        self.responses = responses
        self.calls = 0

    async def execute(self, _statement: object) -> _ScalarResult:
        response = self.responses[self.calls]
        self.calls += 1
        return _ScalarResult(response)


def test_rollout_order_is_closed_and_monotonic(monkeypatch: pytest.MonkeyPatch) -> None:
    assert [step.stage for step in ROLLOUT_STEPS] == list(range(1, 10))
    monkeypatch.setattr(settings, "clinical_rollout_stage", 5)
    assert feature_enabled("cie10_catalog") is True
    assert feature_enabled("structured_diagnoses") is False
    assert feature_enabled("unknown") is False
    assert rollout_summary()["next"] == "structured_diagnoses"


@pytest.mark.asyncio
async def test_bulk_consent_evidence_is_three_queries_not_three_per_row() -> None:
    first, second = uuid.uuid4(), uuid.uuid4()
    signer = ConsentimientoFirmante(consentimiento_id=first)
    document = ConsentimientoDocumentoFinal(consentimiento_id=second)
    revocation = ConsentimientoRevocacion(consentimiento_id=first)
    session = _FakeSession([[signer], [document], [revocation]])

    result = await _evidence_for_consents(session, [first, second])  # type: ignore[arg-type]

    assert session.calls == 3
    assert result[first] == ([signer], None, revocation)
    assert result[second] == ([], document, None)


def test_fase8_verifier_is_registered() -> None:
    assert "fase8" in available_actions()


@pytest.mark.asyncio
async def test_route_rollout_fails_closed_without_blocking_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "clinical_rollout_stage", 4)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        disabled = await client.get("/api/v1/cie10?q=E11")
        health = await client.get("/health")
    assert disabled.status_code == 503
    assert disabled.json()["detail"]["feature"] == "cie10_catalog"
    assert health.status_code == 200

    monkeypatch.setattr(settings, "clinical_rollout_stage", 3)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        classification = await client.post("/api/v1/encuentros", json={})
    assert classification.status_code == 503
    assert classification.json()["detail"]["feature"] == "first_visit_evolution"


@pytest.mark.asyncio
async def test_stage_below_template_engine_uses_legacy_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "clinical_rollout_stage", 6)
    rows = await templates(db=object())  # type: ignore[arg-type]
    assert len(rows) == 5
