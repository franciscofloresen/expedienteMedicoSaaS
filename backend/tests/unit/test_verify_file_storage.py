"""Unit tests for the deploy-time storage verification phases.

The real AWS interactions (presigned POST, GuardDuty tags) are exercised by
the verify-storage-production deploy job; here we pin the phase logic and
its failure modes.
"""

from types import SimpleNamespace

import pytest

from scripts import verify_file_storage as vfs


@pytest.fixture
def stubbed_upload(monkeypatch):
    """Stub the S3 helpers and httpx for a successful upload phase."""
    captured = {}

    def fake_create_upload_post(**kwargs):
        captured["post_kwargs"] = kwargs
        return {"url": "https://bucket.example/", "fields": {"key": kwargs["s3_key"]}}

    def fake_httpx_post(url, data=None, files=None, timeout=None):
        captured["posted"] = {"url": url, "data": data, "files": files}
        return SimpleNamespace(status_code=204, text="")

    def fake_head(s3_key):
        captured["head_key"] = s3_key
        return {
            "ContentLength": len(vfs.PROBE_BODY),
            "ServerSideEncryption": "aws:kms",
            "Metadata": {
                "file-id": captured["post_kwargs"]["file_id"],
                "tenant-id": "healthcheck",
            },
        }

    monkeypatch.setattr(vfs, "create_upload_post", fake_create_upload_post)
    monkeypatch.setattr(vfs.httpx, "post", fake_httpx_post)
    monkeypatch.setattr(vfs, "head_uploaded_object", fake_head)
    return captured


def test_upload_phase_posts_probe_under_healthcheck_prefix(stubbed_upload):
    result = vfs.verify_upload()
    assert result["ok"] is True
    assert result["s3_key"].startswith(vfs.HEALTHCHECK_PREFIX)
    assert stubbed_upload["post_kwargs"]["content_type"] == vfs.PROBE_CONTENT_TYPE
    assert stubbed_upload["post_kwargs"]["size_bytes"] == len(vfs.PROBE_BODY)
    assert stubbed_upload["head_key"] == result["s3_key"]


def test_upload_phase_fails_on_s3_rejection(stubbed_upload, monkeypatch):
    monkeypatch.setattr(
        vfs.httpx,
        "post",
        lambda *a, **kw: SimpleNamespace(status_code=403, text="AccessDenied"),
    )
    result = vfs.verify_upload()
    assert result["ok"] is False
    assert result["step"] == "presigned_post"


def test_upload_phase_fails_when_object_not_kms_encrypted(stubbed_upload, monkeypatch):
    monkeypatch.setattr(
        vfs,
        "head_uploaded_object",
        lambda s3_key: {"ContentLength": len(vfs.PROBE_BODY), "ServerSideEncryption": "AES256"},
    )
    result = vfs.verify_upload()
    assert result["ok"] is False
    assert result["step"] == "head_object"


def test_check_phase_reports_pending_before_scan_tag(monkeypatch):
    monkeypatch.setattr(vfs, "get_scan_status", lambda s3_key: None)
    result = vfs.verify_check(f"{vfs.HEALTHCHECK_PREFIX}abc/probe.pdf")
    assert result["ok"] is True
    assert result["scan_status"] is None
    assert result["download_verified"] is False


def test_check_phase_fails_on_threats_found(monkeypatch):
    monkeypatch.setattr(vfs, "get_scan_status", lambda s3_key: "THREATS_FOUND")
    result = vfs.verify_check(f"{vfs.HEALTHCHECK_PREFIX}abc/probe.pdf")
    assert result["ok"] is False
    assert result["step"] == "scan"


def test_check_phase_verifies_download_after_clean_scan(monkeypatch):
    monkeypatch.setattr(vfs, "get_scan_status", lambda s3_key: "NO_THREATS_FOUND")
    monkeypatch.setattr(vfs, "create_download_url", lambda **kw: "https://signed.example/get")
    monkeypatch.setattr(
        vfs.httpx,
        "get",
        lambda url, timeout=None: SimpleNamespace(status_code=200, content=vfs.PROBE_BODY),
    )
    result = vfs.verify_check(f"{vfs.HEALTHCHECK_PREFIX}abc/probe.pdf")
    assert result["ok"] is True
    assert result["download_verified"] is True


def test_check_phase_refuses_non_healthcheck_keys():
    result = vfs.verify_check("tenants/11111111-2222-3333-4444-555555555555/real-file")
    assert result["ok"] is False


def test_run_phase_dispatch():
    assert vfs.run_phase("bogus")["ok"] is False
    assert vfs.run_phase("check")["ok"] is False  # missing s3_key
