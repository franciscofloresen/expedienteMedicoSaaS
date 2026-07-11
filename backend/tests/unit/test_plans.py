from app.core.plans import BASICO, PRO, entitlement


def test_basico_entitlements():
    assert entitlement(BASICO, "max_expedientes") == 5
    assert entitlement(BASICO, "audit_log") is False
    assert entitlement(BASICO, "file_storage_quota_bytes") == 0


def test_pro_entitlements():
    assert entitlement(PRO, "max_expedientes") is None  # unlimited
    assert entitlement(PRO, "audit_log") is True
    assert entitlement(PRO, "file_storage_quota_bytes") == 15 * 1024 * 1024 * 1024


def test_unknown_plan_fails_closed_to_basico():
    assert entitlement(None, "max_expedientes") == 5
    assert entitlement("enterprise", "audit_log") is False


def test_unknown_key_falls_back_to_basico_default():
    # A key only meaningful once added; unknown keys mirror the Básico default.
    assert entitlement(PRO, "nonexistent_feature") == entitlement(BASICO, "nonexistent_feature")
