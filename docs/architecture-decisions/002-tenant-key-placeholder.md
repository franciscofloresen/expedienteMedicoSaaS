# ADR 002: Tenant Key Placeholder (tenant_key.py)

**Date**: 2026-07-06
**Status**: Accepted

## Context
During initial development, a `tenant_key.py` module was implemented with the idea of managing unique per-tenant encryption keys within the database (using `tenant_keys` table). However, as the KMS direct-call pattern was established, this table was dropped from the schema to reduce architectural complexity.

## Decision
We decided to use direct AWS KMS encryption (`encrypt_field` / `decrypt_field`) rather than a bespoke `tenant_key.py` abstraction. The `tenant_keys` table was dropped in Alembic migrations to simplify operations. The `tenant_key.py` module is no longer part of the active encryption flow.

## Consequences
- **Pros**: Reduced state in the database, relying entirely on IAM and AWS KMS for key material.
- **Cons**: KMS cost increases per call since there is no DEK cache in place yet.
