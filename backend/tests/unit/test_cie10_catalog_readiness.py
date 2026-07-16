from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.v1 import cie10


class _CountResult:
    def __init__(self, count: int) -> None:
        self.count = count

    def scalar_one(self) -> int:
        return self.count


class _CountSession:
    def __init__(self, count: int) -> None:
        self.count = count

    async def execute(self, _statement):
        return _CountResult(self.count)


@pytest.mark.asyncio
async def test_search_reports_catalog_not_ready_instead_of_partial_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cie10, "_search_by_description", AsyncMock(return_value=[]))

    with pytest.raises(HTTPException) as exc:
        await cie10.search_cie10("diagnostico inexistente", db=_CountSession(6))

    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "cie10_catalog_not_ready"


@pytest.mark.asyncio
async def test_search_returns_empty_for_valid_no_match_with_complete_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cie10, "_search_by_description", AsyncMock(return_value=[]))

    result = await cie10.search_cie10(
        "diagnostico inexistente",
        db=_CountSession(cie10._MIN_COMPLETE_CATALOG_ROWS),
    )

    assert result == []
