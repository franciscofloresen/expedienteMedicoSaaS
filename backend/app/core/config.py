"""
Application configuration with Secrets Manager caching.

Secrets are cached in Lambda memory with a configurable TTL to avoid
API calls on every invocation while ensuring rotated credentials
are picked up within the cache window.
"""

import json
import os
import time
from functools import lru_cache
from typing import Any, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Environment — SECURITY: defaults to 'production' (fail-closed).
    # You MUST explicitly set ENVIRONMENT=development in .env.local for local dev.
    environment: str = "prod"
    log_level: str = "INFO"
    aws_region: str = "us-east-1"

    # Database (resolved from Secrets Manager in prod)
    db_secret_arn: str = ""
    database_url: str = "postgresql+asyncpg://localhost:5432/medrecord"
    # Direct Lambda -> RDS connections. There is deliberately no RDS Proxy in
    # Terraform, so keep every warm execution environment's pool bounded.
    db_pool_size: int = Field(default=1, ge=1, le=5)
    db_max_overflow: int = Field(default=1, ge=0, le=5)
    db_pool_timeout_seconds: int = Field(default=5, ge=1, le=30)
    db_pool_recycle_seconds: int = Field(default=300, ge=60, le=1800)

    # Fase 8 gradual rollout. Values follow the fixed V1 activation order
    # (1=schema compatibility ... 9=normative library). Stage 10/legacy column
    # removal is intentionally not available until the production-cycle gate passes.
    clinical_rollout_stage: int = Field(default=9, ge=1, le=9)

    # KMS
    kms_encryption_key_id: str = ""
    kms_signing_key_id: str = ""

    # S3
    s3_expedientes_bucket: str = "medrecord-expedientes-dev"
    s3_audit_bucket: str = "medrecord-audit-dev"
    s3_consent_bucket: str = "medrecord-consent-dev"
    file_upload_max_bytes: int = 250 * 1024 * 1024
    file_signed_url_ttl_seconds: int = 300
    malware_scan_required: bool = True

    # SES (appointment notifications). Must be a VERIFIED SES identity
    # in `aws_region`. Empty disables sending (best-effort no-op).
    ses_sender_email: str = ""

    # Clerk Auth
    clerk_issuer_url: str = ""
    app_config_secret_arn: str = ""
    clerk_secret_key: str = ""
    clerk_jwks_url: str = ""
    clerk_authorized_parties: list[str] = Field(default_factory=list)
    clerk_audience: str = ""
    clerk_require_mfa: bool = True
    clerk_reauth_max_age_minutes: int = Field(default=10, ge=1, le=60)

    # Cache TTLs (seconds)
    secrets_cache_ttl: int = 300  # 5 minutes

    # Local JWT (development only — NEVER hardcode secrets)
    # If empty in dev mode, an ephemeral random secret is generated per process.
    jwt_dev_secret: str = ""

    # CORS
    cors_origins: list[str] = Field(default=["http://localhost:5173"])

    @field_validator("cors_origins", "clerk_authorized_parties", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, list[str]]) -> list[str]:
        if isinstance(v, str):
            if v.startswith("["):
                import json

                return json.loads(v)  # type: ignore
            return [i.strip() for i in v.split(",")]
        if isinstance(v, list):
            return v
        raise ValueError(v)

    model_config = {
        "env_file": ".env.local",
        "env_file_encoding": "utf-8",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


# ── Secrets Manager Cache ──

_secrets_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_sm_client = None


def _get_sm_client() -> Any:
    import boto3

    global _sm_client
    if _sm_client is None:
        _sm_client = boto3.client("secretsmanager", region_name=get_settings().aws_region)
    return _sm_client


def get_secret(secret_arn: str) -> dict[str, Any]:
    """
    Retrieve a secret from AWS Secrets Manager with in-memory caching.

    Cache TTL is configurable via SECRETS_CACHE_TTL env var (default 5 min).
    This avoids a Secrets Manager API call on every Lambda invocation
    while ensuring rotated credentials are picked up within the TTL window.
    """
    s = get_settings()
    now = time.time()

    if secret_arn in _secrets_cache:
        cached_at, value = _secrets_cache[secret_arn]
        if now - cached_at < s.secrets_cache_ttl:
            return value

    client = _get_sm_client()
    response = client.get_secret_value(SecretId=secret_arn)
    value = json.loads(response["SecretString"])
    _secrets_cache[secret_arn] = (now, value)
    return value  # type: ignore[no-any-return]


def get_database_url() -> str:
    """
    Build database URL from Secrets Manager in production,
    or use the direct DATABASE_URL env var in development.
    """
    s = get_settings()
    if s.environment in ("development", "testing"):
        return s.database_url

    secret = get_secret(s.db_secret_arn)
    host = os.environ.get("DB_HOST") or secret.get("host")
    port = os.environ.get("DB_PORT") or secret.get("port", "5432")

    # Handle case where DB_HOST already includes the port
    # (e.g., from terraform aws_db_instance.endpoint)
    if host and ":" in host:
        host, parsed_port = host.rsplit(":", 1)
        # Only override port if DB_PORT wasn't explicitly set in the environment
        if not os.environ.get("DB_PORT"):
            port = parsed_port

    dbname = os.environ.get("DB_NAME") or secret.get("dbname", "postgres")

    return f"postgresql+asyncpg://{secret['username']}:{secret['password']}@{host}:{port}/{dbname}"


def get_clerk_secret_key() -> str:
    """Resolve the Clerk backend key without exposing it in Lambda environment variables.

    Development and tests may still use ``CLERK_SECRET_KEY``. Production must receive
    only ``APP_CONFIG_SECRET_ARN`` and reads ``CLERK_SECRET_KEY`` from the JSON secret.
    """
    s = get_settings()
    if s.environment in ("development", "testing"):
        return s.clerk_secret_key
    if not s.app_config_secret_arn:
        raise RuntimeError("APP_CONFIG_SECRET_ARN no está configurado")
    secret = get_secret(s.app_config_secret_arn)
    value = secret.get("CLERK_SECRET_KEY")
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("CLERK_SECRET_KEY no está disponible en app-config")
    return value


# Backward compat: some files import `settings` directly.
# This is safe as long as env vars are set before first access.
settings = get_settings()
