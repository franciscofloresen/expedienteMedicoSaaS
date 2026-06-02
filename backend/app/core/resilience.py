"""
Resilience Patterns — Retry + Circuit Breaker

Provides reusable decorators for AWS service calls.
Uses tenacity for retries with exponential backoff.
"""

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from botocore.exceptions import ClientError, EndpointConnectionError


# ── Retry decorators for different service profiles ──

# KMS calls: fast retry, 3 attempts
kms_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
    retry=retry_if_exception_type((ClientError, EndpointConnectionError)),
    reraise=True,
)

# S3 calls: slower retry, 3 attempts (uploads can be slow)
s3_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    retry=retry_if_exception_type((ClientError, EndpointConnectionError)),
    reraise=True,
)

# Database calls: 2 attempts only (RDS Proxy handles most retry logic)
db_retry = retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.2, min=0.2, max=1),
    reraise=True,
)
