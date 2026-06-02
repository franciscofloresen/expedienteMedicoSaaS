#!/usr/bin/env bash
# ============================================================
# MedRecord SaaS — Terraform Backend Bootstrap
# Creates S3 bucket + DynamoDB table for remote state locking.
# Usage: ./init.sh <bucket-name> [region]
# ============================================================
set -euo pipefail

BUCKET_NAME="${1:?Usage: ./init.sh <bucket-name> [region]}"
REGION="${2:-us-east-1}"
DYNAMO_TABLE="medrecord-terraform-locks"

echo "🔧 Bootstrapping Terraform backend..."
echo "   Bucket: ${BUCKET_NAME}"
echo "   Region: ${REGION}"
echo "   DynamoDB: ${DYNAMO_TABLE}"
echo ""

# ── S3 Bucket ──
if aws s3api head-bucket --bucket "${BUCKET_NAME}" 2>/dev/null; then
  echo "✓ S3 bucket already exists: ${BUCKET_NAME}"
else
  echo "→ Creating S3 bucket: ${BUCKET_NAME}"
  if [ "${REGION}" = "us-east-1" ]; then
    aws s3api create-bucket \
      --bucket "${BUCKET_NAME}" \
      --region "${REGION}"
  else
    aws s3api create-bucket \
      --bucket "${BUCKET_NAME}" \
      --region "${REGION}" \
      --create-bucket-configuration LocationConstraint="${REGION}"
  fi

  # Enable versioning (protects against accidental state corruption)
  aws s3api put-bucket-versioning \
    --bucket "${BUCKET_NAME}" \
    --versioning-configuration Status=Enabled

  # Enable server-side encryption (AES-256)
  aws s3api put-bucket-encryption \
    --bucket "${BUCKET_NAME}" \
    --server-side-encryption-configuration '{
      "Rules": [{
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "aws:kms"
        },
        "BucketKeyEnabled": true
      }]
    }'

  # Block all public access
  aws s3api put-public-access-block \
    --bucket "${BUCKET_NAME}" \
    --public-access-block-configuration '{
      "BlockPublicAcls": true,
      "IgnorePublicAcls": true,
      "BlockPublicPolicy": true,
      "RestrictPublicBuckets": true
    }'

  echo "✓ S3 bucket created and secured"
fi

# ── DynamoDB Table ──
if aws dynamodb describe-table --table-name "${DYNAMO_TABLE}" --region "${REGION}" 2>/dev/null | grep -q "ACTIVE"; then
  echo "✓ DynamoDB table already exists: ${DYNAMO_TABLE}"
else
  echo "→ Creating DynamoDB table: ${DYNAMO_TABLE}"
  aws dynamodb create-table \
    --table-name "${DYNAMO_TABLE}" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "${REGION}" \
    --tags Key=Project,Value=medrecord Key=ManagedBy,Value=bootstrap

  aws dynamodb wait table-exists \
    --table-name "${DYNAMO_TABLE}" \
    --region "${REGION}"

  echo "✓ DynamoDB table created"
fi

echo ""
echo "✅ Terraform backend ready!"
echo ""
echo "Add this to your Terraform configuration:"
echo ""
echo '  terraform {'
echo '    backend "s3" {'
echo "      bucket         = \"${BUCKET_NAME}\""
echo "      key            = \"<environment>/terraform.tfstate\""
echo "      region         = \"${REGION}\""
echo "      dynamodb_table = \"${DYNAMO_TABLE}\""
echo '      encrypt        = true'
echo '    }'
echo '  }'
