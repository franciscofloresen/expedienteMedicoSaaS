# ============================================================
# NOM-004 §5.14 — 5-year legal retention via AWS Backup + Vault Lock
# ------------------------------------------------------------
# Replaces the dead Parquet snapshot-export pipeline (removed:
# snapshot_export.tf). See docs/runbooks/backup_retention_5years.md.
#
# Split of concerns (do NOT merge, it only raises cost):
#   * 0–35 days  → RDS automated backups + PITR (main.tf, backup_retention_period=35). Untouched.
#   * 35d–5yr    → this file: monthly restorable snapshot, retained 1825 days,
#                  in a Vault-Lock (WORM) vault, KMS-encrypted, with failure alarms.
# ============================================================

# ── Vault holding the 5-year legal archive (immutable) ───────────────────────
resource "aws_backup_vault" "legal_5yr" {
  name        = "medrecord-legal-5yr-${var.environment}"
  kms_key_arn = var.kms_key_arn
  tags = {
    Project     = "medrecord"
    Environment = var.environment
    Purpose     = "nom004-5yr-retention"
  }
}

# ⚠️  VAULT LOCK — COMPLIANCE MODE. This makes retention WORM.
#
#     `changeable_for_days = 3` opens a 72-hour cooling-off window: during those
#     3 days the lock is still reversible (you can delete the vault / shorten
#     retention). AFTER the window closes it is IRREVERSIBLE — the vault cannot
#     be deleted, retention cannot be shortened, and recovery points cannot be
#     deleted early, not even by the account root.
#
#     Therefore: only let `terraform apply` create this AND then let 72h pass
#     AFTER you have run the on-demand backup (§5.1) and the restore drill (§5.2)
#     in the runbook. If either fails, back out inside the 72h window. If in any
#     doubt, comment out `changeable_for_days` to stay in GOVERNANCE mode (still
#     blocks casual/accidental deletes; only omits the regulatory WORM guarantee).
resource "aws_backup_vault_lock_configuration" "legal_5yr" {
  backup_vault_name   = aws_backup_vault.legal_5yr.name
  min_retention_days  = 1825
  changeable_for_days = 3 # COMPLIANCE lock after a 72h cooling-off window (see warning above)
}

# ── IAM role AWS Backup assumes to run backups and restores ──────────────────
resource "aws_iam_role" "backup" {
  name = "medrecord-backup-role-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "backup.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "backup" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

resource "aws_iam_role_policy_attachment" "restore" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores"
}

# ── Backup plan: monthly, retained 5 years, into the immutable vault ─────────
resource "aws_backup_plan" "medrecord" {
  name = "medrecord-backup-plan-${var.environment}"

  rule {
    rule_name         = "monthly-5yr-legal"
    target_vault_name = aws_backup_vault.legal_5yr.name
    schedule          = "cron(0 5 1 * ? *)" # 05:00 UTC on the 1st of each month
    start_window      = 60
    completion_window = 360
    lifecycle {
      delete_after = 1825 # 5 years. cold_storage_after does NOT apply to RDS.
    }
    recovery_point_tags = {
      Project     = "medrecord"
      Environment = var.environment
      Retention   = "nom004-5yr"
    }
  }
}

# ── Selection: the prod RDS instance ─────────────────────────────────────────
resource "aws_backup_selection" "rds" {
  name         = "medrecord-rds-${var.environment}"
  plan_id      = aws_backup_plan.medrecord.id
  iam_role_arn = aws_iam_role.backup.arn
  resources    = [aws_db_instance.main.arn]
}

# ── Anti-silent-failure: publish backup/restore failures to the alarms topic ─
# The SNS topic policy that allows backup.amazonaws.com to publish lives in
# terraform/modules/observability (aws_sns_topic_policy.alarms).
resource "aws_backup_vault_notifications" "legal_5yr" {
  backup_vault_name = aws_backup_vault.legal_5yr.name
  sns_topic_arn     = var.ops_sns_topic_arn
  backup_vault_events = [
    "BACKUP_JOB_FAILED",
    "BACKUP_JOB_EXPIRED",
    "RESTORE_JOB_FAILED",
  ]
}
