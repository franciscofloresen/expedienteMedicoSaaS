# ============================================================
# MedRecord SaaS — Observability Module
# 5 Critical Alarms + SNS + Route53 Health Check
# ============================================================

variable "environment" {
  type = string
}

variable "alarm_email" {
  type        = string
  description = "Email for alarm notifications"
}

variable "api_name" {
  type        = string
  description = "API Gateway name for metrics"
  default     = "medrecord-api"
}

variable "lambda_function_name" {
  type        = string
  description = "Lambda function name for metrics"
  default     = "medrecord-api"
}

variable "db_cluster_id" {
  type        = string
  description = "Aurora cluster identifier for metrics"
}

variable "health_check_fqdn" {
  type        = string
  description = "FQDN for Route53 health check"
  default     = ""
}

# ── SNS Topic for Alarms ──
resource "aws_sns_topic" "alarms" {
  name = "medrecord-alarms-${var.environment}"

  tags = {
    Name        = "medrecord-alarms-${var.environment}"
    Environment = var.environment
  }
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# ── Alarm 1: Lambda Error Rate > 5% ──
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "medrecord-lambda-errors-${var.environment}"
  alarm_description   = "Lambda error rate exceeds 5%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 5
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "error_rate"
    expression  = "(errors / invocations) * 100"
    label       = "Error Rate %"
    return_data = true
  }

  metric_query {
    id = "errors"
    metric {
      metric_name = "Errors"
      namespace   = "AWS/Lambda"
      period      = 300
      stat        = "Sum"
      dimensions = {
        FunctionName = var.lambda_function_name
      }
    }
  }

  metric_query {
    id = "invocations"
    metric {
      metric_name = "Invocations"
      namespace   = "AWS/Lambda"
      period      = 300
      stat        = "Sum"
      dimensions = {
        FunctionName = var.lambda_function_name
      }
    }
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Severity    = "P1"
  }
}

# ── Alarm 2: API Gateway 5xx > 1% ──
resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "medrecord-api-5xx-${var.environment}"
  alarm_description   = "API Gateway 5xx error rate exceeds 1%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 1
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "error_rate"
    expression  = "(errors_5xx / total) * 100"
    label       = "5xx Rate %"
    return_data = true
  }

  metric_query {
    id = "errors_5xx"
    metric {
      metric_name = "5XXError"
      namespace   = "AWS/ApiGateway"
      period      = 300
      stat        = "Sum"
      dimensions = {
        ApiName = var.api_name
      }
    }
  }

  metric_query {
    id = "total"
    metric {
      metric_name = "Count"
      namespace   = "AWS/ApiGateway"
      period      = 300
      stat        = "Sum"
      dimensions = {
        ApiName = var.api_name
      }
    }
  }

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Severity    = "P1"
  }
}

# ── Alarm 3: Aurora CPU > 80% ──
resource "aws_cloudwatch_metric_alarm" "aurora_cpu" {
  alarm_name          = "medrecord-aurora-cpu-${var.environment}"
  alarm_description   = "Aurora CPU utilization exceeds 80%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBClusterIdentifier = var.db_cluster_id
  }

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Severity    = "P2"
  }
}

# ── Alarm 4: API Latency p99 > 3s ──
resource "aws_cloudwatch_metric_alarm" "api_latency" {
  alarm_name          = "medrecord-api-latency-${var.environment}"
  alarm_description   = "API Gateway p99 latency exceeds 3 seconds"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "Latency"
  namespace           = "AWS/ApiGateway"
  period              = 300
  extended_statistic  = "p99"
  threshold           = 3000 # milliseconds
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = var.api_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Severity    = "P2"
  }
}

# ── Alarm 5: DLQ Messages > 0 ──
resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  alarm_name          = "medrecord-dlq-messages-${var.environment}"
  alarm_description   = "Dead letter queue has messages — Lambda failures detected"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = "medrecord-lambda-dlq-${var.environment}"
  }

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Severity    = "P1"
  }
}

# ── Route53 Health Check (external monitoring) ──
resource "aws_route53_health_check" "api" {
  count = var.health_check_fqdn != "" ? 1 : 0

  fqdn              = var.health_check_fqdn
  port               = 443
  type               = "HTTPS"
  resource_path      = "/health"
  failure_threshold  = 3
  request_interval   = 30
  regions            = ["us-east-1", "us-west-2", "eu-west-1"]

  tags = {
    Name        = "medrecord-health-${var.environment}"
    Environment = var.environment
  }
}

# ── Outputs ──
output "sns_topic_arn" {
  value = aws_sns_topic.alarms.arn
}
