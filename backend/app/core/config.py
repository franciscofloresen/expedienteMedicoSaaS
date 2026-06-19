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
    environment: str = "production"
    log_level: str = "INFO"
    aws_region: str = "us-east-1"

    # Database (resolved from Secrets Manager in prod)
    db_secret_arn: str = ""
    database_url: str = "postgresql+asyncpg://localhost:5432/medrecord"

    # KMS
    kms_encryption_key_id: str = ""
    kms_signing_key_id: str = ""

    # S3
    s3_expedientes_bucket: str = "medrecord-expedientes-dev"
    s3_audit_bucket: str = "medrecord-audit-dev"
    s3_consent_bucket: str = "medrecord-consent-dev"

    # Clerk Auth
    clerk_issuer_url: str = ""
    clerk_secret_key: str = ""
    clerk_jwks_url: str = ""

    # Cache TTLs (seconds)
    secrets_cache_ttl: int = 300  # 5 minutes
    dek_cache_ttl: int = 300      # 5 minutes

    # Local JWT (development only — NEVER hardcode secrets)
    # If empty in dev mode, an ephemeral random secret is generated per process.
    jwt_dev_secret: str = ""

    # CORS
    cors_origins: list[str] = Field(default=["http://localhost:5173"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, list[str]]) -> Union[list[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    model_config = {
        "env_file": ".env.local",
        "env_file_encoding": "utf-8",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Lazy accessor — avoids module-level instantiation that can fail
# before environment variables are set (e.g., Lambda cold start).
def _settings() -> Settings:
    return get_settings()



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
    dbname = os.environ.get("DB_NAME") or secret.get("dbname", "postgres")

    return (
        f"postgresql+asyncpg://{secret['username']}:{secret['password']}"
        f"@{host}:{port}/{dbname}"
    )


# Backward compat: some files import `settings` directly.
# This is safe as long as env vars are set before first access.
settings = get_settings()
