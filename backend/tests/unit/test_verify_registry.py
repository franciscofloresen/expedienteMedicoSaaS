"""Unit tests for the unified verify_* dispatch contract (no DB needed)."""

from scripts.verify_registry import available_actions, run_verify


def test_rls_is_registered() -> None:
    assert "rls" in available_actions()


def test_unknown_action_returns_failing_envelope() -> None:
    """An unknown action must not raise — it returns an ok=False envelope so the
    Lambda handler can map it to a 500 rather than crashing."""
    result = run_verify("does_not_exist")
    assert result["ok"] is False
    assert result["action"] == "does_not_exist"
    assert any(not c["ok"] for c in result["checks"])
    # Uniform envelope shape.
    assert set(result) == {"ok", "action", "checks", "warnings", "counts"}
