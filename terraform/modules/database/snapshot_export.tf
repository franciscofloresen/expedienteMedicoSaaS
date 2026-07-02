data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# S3 Bucket for RDS Snapshots
resource "aws_s3_bucket" "rds_snapshots" {
  bucket        = "medrecord-rds-snapshots-${var.environment}-${data.aws_caller_identity.current.account_id}"
  force_destroy = false
}

resource "aws_s3_bucket_server_side_encryption_configuration" "rds_snapshots_enc" {
  bucket = aws_s3_bucket.rds_snapshots.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.kms_key_arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "rds_snapshots_pab" {
  bucket = aws_s3_bucket.rds_snapshots.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "rds_snapshots_lifecycle" {
  bucket = aws_s3_bucket.rds_snapshots.id
  rule {
    id     = "glacier-transition-and-expire"
    status = "Enabled"

    filter {}

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 1825
    }
  }
}

# IAM Role for RDS to write to S3
resource "aws_iam_role" "rds_export_role" {
  name = "rds-export-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "export.rds.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "rds_export_policy" {
  name = "rds-export-policy-${var.environment}"
  role = aws_iam_role.rds_export_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject*",
          "s3:ListBucket",
          "s3:GetObject*",
          "s3:DeleteObject*",
          "s3:GetBucketLocation"
        ]
        Resource = [
          aws_s3_bucket.rds_snapshots.arn,
          "${aws_s3_bucket.rds_snapshots.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:GenerateDataKey",
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:DescribeKey"
        ]
        Resource = var.kms_key_arn
      }
    ]
  })
}

# IAM Role for Lambda Orchestrator
resource "aws_iam_role" "lambda_export_role" {
  name = "lambda-export-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_export_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_export_policy" {
  name = "lambda-export-policy-${var.environment}"
  role = aws_iam_role.lambda_export_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rds:StartExportTask"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = aws_iam_role.rds_export_role.arn
      },
      {
        Effect = "Allow"
        Action = [
          "kms:DescribeKey",
          "kms:CreateGrant",
          "kms:GenerateDataKey",
          "kms:Decrypt",
          "kms:Encrypt"
        ]
        Resource = var.kms_key_arn
      }
    ]
  })
}

# Lambda Function payload
data "archive_file" "lambda_export_zip" {
  type        = "zip"
  output_path = "${path.module}/export_lambda.zip"

  source {
    content  = <<EOF
import os
import boto3
import json
import logging
import uuid
import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    
    detail = event.get('detail', {})
    
    source_arn = detail.get('SourceArn')
    if not source_arn:
        snapshot_id = detail.get('SourceIdentifier')
        if not snapshot_id:
            logger.error("No SourceIdentifier found in event.")
            return
        
        region = os.environ['AWS_REGION']
        account = os.environ['ACCOUNT_ID']
        source_arn = f"arn:aws:rds:{region}:{account}:snapshot:{snapshot_id}"
        
    s3_bucket = os.environ['S3_BUCKET_NAME']
    iam_role_arn = os.environ['IAM_ROLE_ARN']
    kms_key_id = os.environ['KMS_KEY_ID']
    
    export_id = f"export-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}"
    
    rds = boto3.client('rds')
    
    try:
        response = rds.start_export_task(
            ExportTaskIdentifier=export_id,
            SourceArn=source_arn,
            S3BucketName=s3_bucket,
            IamRoleArn=iam_role_arn,
            KmsKeyId=kms_key_id
        )
        logger.info(json.dumps({
            "event": "rds_export_task_started",
            "export_task_id": export_id,
            "snapshot_arn": source_arn
        }))
    except Exception as e:
        logger.error(f"Failed to start export task: {e}")
        raise
EOF
    filename = "main.py"
  }
}

resource "aws_lambda_function" "rds_export" {
  filename         = data.archive_file.lambda_export_zip.output_path
  function_name    = "rds-snapshot-export-${var.environment}"
  role             = aws_iam_role.lambda_export_role.arn
  handler          = "main.handler"
  runtime          = "python3.11"
  source_code_hash = data.archive_file.lambda_export_zip.output_base64sha256
  timeout          = 30

  environment {
    variables = {
      S3_BUCKET_NAME = aws_s3_bucket.rds_snapshots.bucket
      IAM_ROLE_ARN   = aws_iam_role.rds_export_role.arn
      KMS_KEY_ID     = var.kms_key_arn
      ACCOUNT_ID     = data.aws_caller_identity.current.account_id
    }
  }
}

# EventBridge Rule
resource "aws_cloudwatch_event_rule" "rds_snapshot_created" {
  name        = "rds-snapshot-created-${var.environment}"
  description = "Triggers on automated RDS snapshot creation"
  
  event_pattern = jsonencode({
    "source": ["aws.rds"],
    "detail-type": ["RDS DB Snapshot Event"],
    "detail": {
      "SourceType": ["SNAPSHOT"],
      "Message": [{
        "prefix": "Finished DB Instance snapshot"
      }]
    }
  })
}

resource "aws_cloudwatch_event_target" "lambda_export_target" {
  rule      = aws_cloudwatch_event_rule.rds_snapshot_created.name
  target_id = "TriggerLambda"
  arn       = aws_lambda_function.rds_export.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rds_export.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.rds_snapshot_created.arn
}
