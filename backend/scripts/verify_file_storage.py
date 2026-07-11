"""End-to-end verification of the clinical file storage pipeline, in-place.

Runs inside the deployed Lambda (invoked with {"verify_file_storage": ...})
so it exercises the real bucket policy, KMS permissions, presigned POST
conditions and the GuardDuty malware-scan tagging flow — the parts that unit
tests can only mock.

Two phases, because GuardDuty scanning is asynchronous and the Lambda
timeout is 30s:

  {"verify_file_storage": "upload"}
      Uploads a tiny probe object under tenants/healthcheck/ via the same
      presigned POST the browser uses, then verifies the stored object's
      encryption and metadata. Returns the probe's s3_key.

  {"verify_file_storage": "check", "s3_key": "..."}
      Reads the GuardDuty scan tag for the probe. While the scan is pending
      it returns scan_status=null; once NO_THREATS_FOUND it also fetches the
      presigned download URL and confirms the content round-trips.

The caller (deploy workflow) polls the check phase. Probe objects are
expired automatically by the tenants/healthcheck/ S3 lifecycle rule — the
Lambda role deliberately has no s3:DeleteObject.
"""

import uuid
from typing import Any

import httpx

from app.services.clinical_storage import (
    create_download_url,
    create_upload_post,
    get_scan_status,
    head_uploaded_object,
)

HEALTHCHECK_PREFIX = "tenants/healthcheck/"
PROBE_BODY = b"%PDF-1.4\n% clinical storage verification probe\n%%EOF\n"
PROBE_CONTENT_TYPE = "application/pdf"


def _fail(step: str, detail: str) -> dict[str, Any]:
    return {"ok": False, "step": step, "detail": detail}


def verify_upload() -> dict[str, Any]:
    """Upload a probe through the presigned POST path and validate the object."""
    probe_id = str(uuid.uuid4())
    s3_key = f"{HEALTHCHECK_PREFIX}{probe_id}/probe.pdf"

    post = create_upload_post(
        s3_key=s3_key,
        file_id=probe_id,
        tenant_id="healthcheck",
        content_type=PROBE_CONTENT_TYPE,
        size_bytes=len(PROBE_BODY),
    )
    response = httpx.post(
        post["url"],
        data=post["fields"],
        files={"file": ("probe.pdf", PROBE_BODY, PROBE_CONTENT_TYPE)},
        timeout=20,
    )
    if response.status_code != 204:
        return _fail(
            "presigned_post",
            f"S3 returned {response.status_code}: {response.text[:500]}",
        )

    head = head_uploaded_object(s3_key)
    if head.get("ContentLength") != len(PROBE_BODY):
        return _fail("head_object", f"unexpected size {head.get('ContentLength')}")
    if head.get("ServerSideEncryption") != "aws:kms":
        return _fail("head_object", f"not KMS-encrypted: {head.get('ServerSideEncryption')}")
    metadata = head.get("Metadata", {})
    if metadata.get("file-id") != probe_id or metadata.get("tenant-id") != "healthcheck":
        return _fail("head_object", f"metadata mismatch: {metadata}")

    return {"ok": True, "step": "upload", "s3_key": s3_key}


def verify_check(s3_key: str) -> dict[str, Any]:
    """Read the GuardDuty scan tag; once clean, verify the download URL works."""
    if not s3_key.startswith(HEALTHCHECK_PREFIX):
        return _fail("check", f"refusing to check non-healthcheck key: {s3_key}")

    scan_status = get_scan_status(s3_key)
    if scan_status is None:
        return {"ok": True, "step": "check", "scan_status": None, "download_verified": False}
    if scan_status != "NO_THREATS_FOUND":
        return _fail("scan", f"scan_status={scan_status}")

    url = create_download_url(
        s3_key=s3_key,
        version_id=None,
        filename="probe.pdf",
        content_type=PROBE_CONTENT_TYPE,
    )
    response = httpx.get(url, timeout=20)
    if response.status_code != 200 or response.content != PROBE_BODY:
        return _fail(
            "download",
            f"presigned GET returned {response.status_code}, "
            f"content match={response.content == PROBE_BODY}",
        )
    return {
        "ok": True,
        "step": "check",
        "scan_status": scan_status,
        "download_verified": True,
    }


def run_phase(phase: Any, s3_key: str | None = None) -> dict[str, Any]:
    if phase == "upload":
        return verify_upload()
    if phase == "check":
        if not s3_key:
            return _fail("check", "s3_key is required for the check phase")
        return verify_check(s3_key)
    return _fail("dispatch", f"unknown phase: {phase!r}")
