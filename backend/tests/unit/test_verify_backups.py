"""Unit tests for the `backups` verifier (NOM-004 §5.14 archive health).

boto3 is mocked with a small fake client so the tests are deterministic and
offline — they exercise the verifier's decision logic (recent/stale/missing
recovery points, vault-lock warning), not AWS.
"""

from datetime import datetime, timedelta, timezone

import boto3
import pytest

from scripts.verify_registry import available_actions, run_verify


class _ResourceNotFoundError(Exception):
    pass


class _FakePaginator:
    def __init__(self, recovery_points: list[dict]) -> None:
        self._recovery_points = recovery_points

    def paginate(self, **_kwargs):  # noqa: ANN003
        # Two pages to also exercise pagination handling.
        mid = len(self._recovery_points) // 2
        yield {"RecoveryPoints": self._recovery_points[:mid]}
        yield {"RecoveryPoints": self._recovery_points[mid:]}


class _FakeBackupClient:
    def __init__(self, *, vault_exists: bool, locked: bool, recovery_points: list[dict]) -> None:
        self._vault_exists = vault_exists
        self._locked = locked
        self._recovery_points = recovery_points
        self.exceptions = type("Exc", (), {"ResourceNotFoundException": _ResourceNotFoundError})

    def describe_backup_vault(self, **_kwargs):  # noqa: ANN003
        if not self._vault_exists:
            raise self.exceptions.ResourceNotFoundException()
        return {"Locked": self._locked}

    def get_paginator(self, _name: str) -> _FakePaginator:
        return _FakePaginator(self._recovery_points)


def _rp(age_days: float, status: str = "COMPLETED") -> dict:
    return {
        "Status": status,
        "CompletionDate": datetime.now(timezone.utc) - timedelta(days=age_days),
    }


def _patch_client(monkeypatch: pytest.MonkeyPatch, client: _FakeBackupClient) -> None:
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setattr(boto3, "client", lambda service: client)


def test_backups_is_registered() -> None:
    assert "backups" in available_actions()


def test_recent_recovery_point_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(
        monkeypatch,
        _FakeBackupClient(vault_exists=True, locked=True, recovery_points=[_rp(5), _rp(40)]),
    )
    result = run_verify("backups")
    assert result["ok"] is True
    assert result["counts"]["completed_recovery_points"] == 2
    assert result["warnings"] == []


def test_stale_recovery_point_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(
        monkeypatch,
        _FakeBackupClient(vault_exists=True, locked=True, recovery_points=[_rp(60), _rp(90)]),
    )
    result = run_verify("backups")
    assert result["ok"] is False


def test_no_recovery_points_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(
        monkeypatch,
        _FakeBackupClient(vault_exists=True, locked=True, recovery_points=[]),
    )
    result = run_verify("backups")
    assert result["ok"] is False
    assert result["counts"]["completed_recovery_points"] == 0


def test_pending_recovery_point_does_not_count(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(
        monkeypatch,
        _FakeBackupClient(
            vault_exists=True, locked=True, recovery_points=[_rp(2, status="RUNNING")]
        ),
    )
    result = run_verify("backups")
    assert result["ok"] is False
    assert result["counts"]["completed_recovery_points"] == 0


def test_missing_vault_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(
        monkeypatch,
        _FakeBackupClient(vault_exists=False, locked=False, recovery_points=[]),
    )
    result = run_verify("backups")
    assert result["ok"] is False
    assert any("exists" in c["name"] and not c["ok"] for c in result["checks"])


def test_unlocked_vault_warns_but_can_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(
        monkeypatch,
        _FakeBackupClient(vault_exists=True, locked=False, recovery_points=[_rp(3)]),
    )
    result = run_verify("backups")
    assert result["ok"] is True  # warnings don't fail the gate
    assert any("compliance mode" in w for w in result["warnings"])
