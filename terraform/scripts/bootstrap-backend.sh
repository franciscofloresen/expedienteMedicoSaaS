#!/usr/bin/env bash

# bootstrap-backend.sh
# Creates the S3 bucket and DynamoDB table for Terraform remote state if they do not exist.
# Expected variables:
#   AWS_REGION
#   STATE_BUCKET_NAME (e.g. medrecord-terraform-state)
#   LOCK_TABLE_NAME (e.g. medrecord-terraform-locks)

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
STATE_BUCKET_NAME="${STATE_BUCKET_NAME:-medrecord-terraform-state}"
LOCK_TABLE_NAME="${LOCK_TABLE_NAME:-medrecord-terraform-locks}"

echo "Checking if S3 bucket $STATE_BUCKET_NAME exists..."
if aws s3api head-bucket --bucket "$STATE_BUCKET_NAME" 2>/dev/null; then
  echo "Bucket $STATE_BUCKET_NAME already exists."
else
  echo "Creating bucket $STATE_BUCKET_NAME..."
  if [ "$AWS_REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$STATE_BUCKET_NAME" --region "$AWS_REGION"
  else
    aws s3api create-bucket --bucket "$STATE_BUCKET_NAME" --region "$AWS_REGION" --create-bucket-configuration LocationConstraint="$AWS_REGION"
  fi
  
  # Enable versioning
  aws s3api put-bucket-versioning --bucket "$STATE_BUCKET_NAME" --versioning-configuration Status=Enabled
  
  # Enable encryption
  aws s3api put-bucket-encryption \
    --bucket "$STATE_BUCKET_NAME" \
    --server-side-encryption-configuration '{"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}'

  # Block public access
  aws s3api put-public-access-block \
    --bucket "$STATE_BUCKET_NAME" \
    --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
fi

echo "Checking if DynamoDB table $LOCK_TABLE_NAME exists..."
if aws dynamodb describe-table --table-name "$LOCK_TABLE_NAME" --region "$AWS_REGION" > /dev/null 2>&1; then
  echo "DynamoDB table $LOCK_TABLE_NAME already exists."
else
  echo "Creating DynamoDB table $LOCK_TABLE_NAME..."
  aws dynamodb create-table \
    --table-name "$LOCK_TABLE_NAME" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "$AWS_REGION"
  
  aws dynamodb wait table-exists --table-name "$LOCK_TABLE_NAME" --region "$AWS_REGION"
  echo "DynamoDB table created successfully."
fi

echo "Bootstrap complete."
