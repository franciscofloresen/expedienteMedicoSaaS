# ============================================================
# MedRecord SaaS — Compute Module
# Lambda + API Gateway REST API
# ============================================================

variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "lambda_security_group_id" {
  type = string
}



variable "db_secret_arn" {
  type = string
}

variable "db_proxy_endpoint" {
  type = string
}

variable "encryption_key_arn" {
  type = string
}

variable "signing_key_arn" {
  type = string
}

variable "s3_expedientes_bucket" {
  type = string
}

variable "s3_audit_bucket" {
  type = string
}

variable "s3_consent_bucket" {
  type = string
}

variable "waf_acl_arn" {
  type = string
}

# ── IAM Role for Lambda ──
resource "aws_iam_role" "lambda_exec" {
  name = "medrecord-lambda-exec-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = {
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "lambda_vpc_access" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "lambda_app_permissions" {
  name = "app-permissions"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [var.db_secret_arn]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:GenerateDataKeyWithoutPlaintext"
        ]
        Resource = [var.encryption_key_arn]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Sign",
          "kms:Verify"
        ]
        Resource = [var.signing_key_arn]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.s3_expedientes_bucket}",
          "arn:aws:s3:::${var.s3_expedientes_bucket}/*",
          "arn:aws:s3:::${var.s3_audit_bucket}",
          "arn:aws:s3:::${var.s3_audit_bucket}/*",
          "arn:aws:s3:::${var.s3_consent_bucket}",
          "arn:aws:s3:::${var.s3_consent_bucket}/*"
        ]
      }
    ]
  })
}

# ── Dummy Lambda deployment package (replaced during CI) ──
data "archive_file" "dummy" {
  type        = "zip"
  output_path = "${path.module}/dummy.zip"
  source {
    content  = "def handler(event, context): return {'statusCode': 200, 'body': 'dummy'}"
    filename = "main.py"
  }
}

# ── CloudWatch Log Group ──
resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/aws/lambda/medrecord-api-${var.environment}"
  retention_in_days = 30

  tags = {
    Environment = var.environment
  }
}

# ── Lambda Function ──
resource "aws_lambda_function" "api" {
  function_name = "medrecord-api-${var.environment}"
  
  depends_on = [aws_cloudwatch_log_group.api_logs]
  role          = aws_iam_role.lambda_exec.arn
  handler       = "app.main.handler"
  runtime       = "python3.12"
  timeout       = 30
  memory_size   = 1024

  filename         = data.archive_file.dummy.output_path
  source_code_hash = data.archive_file.dummy.output_base64sha256

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.lambda_security_group_id]
  }

  environment {
    variables = {
      ENVIRONMENT           = var.environment
      DB_SECRET_ARN         = var.db_secret_arn
      DB_HOST               = var.db_proxy_endpoint
      KMS_ENCRYPTION_KEY_ID = var.encryption_key_arn
      KMS_SIGNING_KEY_ID    = var.signing_key_arn
      S3_EXPEDIENTES_BUCKET = var.s3_expedientes_bucket
      S3_AUDIT_BUCKET       = var.s3_audit_bucket
      S3_CONSENT_BUCKET     = var.s3_consent_bucket
    }
  }

  # Ignore changes to code since CI/CD updates it
  lifecycle {
    ignore_changes = [
      filename,
      source_code_hash,
      environment
    ]
  }

  tags = {
    Name        = "medrecord-api-${var.environment}"
    Environment = var.environment
  }
}

# ── API Gateway (REST API) ──
resource "aws_api_gateway_rest_api" "api" {
  name        = "medrecord-api-${var.environment}"
  description = "MedRecord REST API"
  
  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Environment = var.environment
  }
}



resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "proxy" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_method.proxy.resource_id
  http_method = aws_api_gateway_method.proxy.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api.invoke_arn
}

# Root proxy method (for /)
resource "aws_api_gateway_method" "proxy_root" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_rest_api.api.root_resource_id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda_root" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_method.proxy_root.resource_id
  http_method = aws_api_gateway_method.proxy_root.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api.invoke_arn
}

resource "aws_api_gateway_deployment" "api" {
  rest_api_id = aws_api_gateway_rest_api.api.id

  depends_on = [
    aws_api_gateway_integration.lambda,
    aws_api_gateway_integration.lambda_root,
  ]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "api" {
  deployment_id = aws_api_gateway_deployment.api.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
  stage_name    = "v1"

  tags = {
    Environment = var.environment
  }
}

resource "aws_wafv2_web_acl_association" "api" {
  resource_arn = aws_api_gateway_stage.api.arn
  web_acl_arn  = var.waf_acl_arn
}

# Allow API GW to invoke Lambda
resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"

  # The /*/* portion grants access from any method on any resource
  # within the API Gateway REST API.
  source_arn = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
}

# ── SQS DLQ for Async Lambda Invocations ──
resource "aws_sqs_queue" "lambda_dlq" {
  name                      = "medrecord-lambda-dlq-${var.environment}"
  message_retention_seconds = 1209600 # 14 days
  
  tags = {
    Environment = var.environment
  }
}

resource "aws_lambda_function_event_invoke_config" "api" {
  function_name = aws_lambda_function.api.function_name

  destination_config {
    on_failure {
      destination = aws_sqs_queue.lambda_dlq.arn
    }
  }
}

resource "aws_iam_role_policy" "lambda_sqs" {
  name = "sqs-dlq-permissions"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = [aws_sqs_queue.lambda_dlq.arn]
      }
    ]
  })
}

# ── Outputs ──
output "api_gateway_url" {
  value = aws_api_gateway_stage.api.invoke_url
}

output "api_gateway_arn" {
  value = aws_api_gateway_rest_api.api.arn
}

output "lambda_function_name" {
  value = aws_lambda_function.api.function_name
}
