"""Contract of the Lambda's administrative payload dispatcher.

The ops workflows parse the response with `jq '.statusCode'` and `.body.ok`, so
the envelope is a real contract with production tooling. The dispatcher had no
behavioural coverage before it was reduced from a 236-line if-chain to a table.
"""

from typing import Any

import pytest

from app import main


def test_every_payload_key_is_unique() -> None:
    keys = [key for key, _ in main._ADMIN_PAYLOADS]
    assert len(keys) == len(set(keys))


def test_known_payload_keys() -> None:
    """Pinned so removing a payload the ops workflows invoke is a failing test."""
    assert {key for key, _ in main._ADMIN_PAYLOADS} == {
        "run_migrations",
        "verify",
        "import_cie10",
        "import_consent_templates",
        "extract_legacy_diagnosticos",
        "verify_file_storage",
        "upgrade_tenant",
        "upgrade_tenant_id",
        "inspect_cedula",
        "release_cedula",
        "inspect_email",
        "release_email",
    }


def test_payload_is_dispatched_to_its_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake(event: dict[str, Any]) -> dict[str, Any]:
        seen["event"] = event
        return {"statusCode": 200, "body": {"ok": True}}

    monkeypatch.setattr(main, "_ADMIN_PAYLOADS", (("verify", fake),))

    response = main.handler({"verify": "rls"}, None)

    assert response == {"statusCode": 200, "body": {"ok": True}}
    assert seen["event"] == {"verify": "rls"}


def test_failing_payload_returns_500_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A crash must reach the workflow as a parseable envelope, not a stack trace."""

    def boom(event: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("no database")

    monkeypatch.setattr(main, "_ADMIN_PAYLOADS", (("verify", boom),))

    response = main.handler({"verify": "rls"}, None)

    assert response["statusCode"] == 500
    assert "verify failed" in response["body"]
    assert "no database" in response["body"]


def test_falsy_payload_value_is_not_dispatched(monkeypatch: pytest.MonkeyPatch) -> None:
    """{"run_migrations": false} must fall through to HTTP, as it always did."""
    called = False

    def fake(event: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover - must not run
        nonlocal called
        called = True
        return {"statusCode": 200, "body": "x"}

    monkeypatch.setattr(main, "_ADMIN_PAYLOADS", (("run_migrations", fake),))
    monkeypatch.setattr(main, "_asgi_handler", lambda event, context: {"statusCode": 404})

    response = main.handler({"run_migrations": False}, None)

    assert called is False
    assert response == {"statusCode": 404}


def test_non_dict_event_goes_to_the_asgi_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "_asgi_handler", lambda event, context: {"statusCode": 200})

    assert main.handler([], None) == {"statusCode": 200}  # type: ignore[arg-type]


def test_release_payloads_report_409_when_the_tenant_has_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The safety guard that refuses to delete a tenant with clinical data."""
    from scripts.release_cedula import TenantHasDataError

    async def refuse(_value: str) -> dict[str, Any]:
        raise TenantHasDataError("el tenant tiene 3 notas")

    import scripts.release_cedula as release_module

    monkeypatch.setattr(release_module, "release_cedula", refuse)
    monkeypatch.setattr(release_module, "release_email", refuse)

    for key, value in (("release_cedula", "12345678"), ("release_email", "a@b.com")):
        response = main.handler({key: value}, None)
        assert response["statusCode"] == 409, key
        assert "3 notas" in response["body"], key
