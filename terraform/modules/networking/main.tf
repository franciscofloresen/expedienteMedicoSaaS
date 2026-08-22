# ============================================================
# MedRecord SaaS — Networking Module
# VPC with public + private subnets across 2 AZs
# ============================================================

variable "environment" {
  type = string
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}

# ── VPC ──
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name        = "medrecord-vpc-${var.environment}"
    Environment = var.environment
    Project     = "medrecord"
  }
}

# ── Public Subnets (NAT Gateway, ALB if needed) ──
resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = false

  tags = {
    Name        = "medrecord-public-${var.availability_zones[count.index]}-${var.environment}"
    Environment = var.environment
    Tier        = "public"
  }
}

# ── Private Subnets (Lambda, RDS) ──
resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name        = "medrecord-private-${var.availability_zones[count.index]}-${var.environment}"
    Environment = var.environment
    Tier        = "private"
  }
}

# ── Internet Gateway ──
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name        = "medrecord-igw-${var.environment}"
    Environment = var.environment
  }
}

# ── Elastic IP for NAT Gateway ──
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name        = "medrecord-nat-eip-${var.environment}"
    Environment = var.environment
  }
}

# ── NAT Gateway (Lambda in private subnets needs internet for AWS APIs) ──
resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id

  tags = {
    Name        = "medrecord-nat-${var.environment}"
    Environment = var.environment
  }

  depends_on = [aws_internet_gateway.main]
}

# ── Route Tables ──
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name        = "medrecord-public-rt-${var.environment}"
    Environment = var.environment
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }

  tags = {
    Name        = "medrecord-private-rt-${var.environment}"
    Environment = var.environment
  }
}

resource "aws_route_table_association" "public" {
  count          = length(var.availability_zones)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count          = length(var.availability_zones)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# ── S3 Gateway Endpoint ──
# A gateway endpoint costs nothing and carries no hourly or per-GB charge. Without
# it every clinical-file and consent-PDF byte the Lambda reads or writes to S3 is
# billed as NAT Gateway data processing on top of the NAT's hourly rate.
#
# This is purely additive: it installs a prefix-list route in the private route
# table that takes precedence over the 0.0.0.0/0 NAT route for S3 traffic only.
# Everything else (Clerk, KMS, Secrets Manager, SES) keeps using the NAT, so the
# endpoint can be added without touching the NAT and without downtime.
data "aws_region" "current" {}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]

  tags = {
    Name        = "medrecord-s3-endpoint-${var.environment}"
    Environment = var.environment
  }
}

# ── Security Groups ──

# Lambda security group — outbound only
resource "aws_security_group" "lambda" {
  name_prefix = "medrecord-lambda-${var.environment}-"
  description = "Security group for Lambda functions"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound (AWS APIs, RDS Proxy)"
  }

  tags = {
    Name        = "medrecord-lambda-sg-${var.environment}"
    Environment = var.environment
  }

  lifecycle {
    create_before_destroy = true
  }
}

# RDS security group — only accepts from Lambda
resource "aws_security_group" "rds" {
  name_prefix = "medrecord-rds-${var.environment}-"
  description = "Security group for Aurora RDS"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
    description     = "PostgreSQL from Lambda only"
  }

  # No egress rules — RDS doesn't need outbound

  tags = {
    Name        = "medrecord-rds-sg-${var.environment}"
    Environment = var.environment
  }

  lifecycle {
    create_before_destroy = true
  }
}

# ── Outputs ──
output "vpc_id" {
  value = aws_vpc.main.id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "lambda_security_group_id" {
  value = aws_security_group.lambda.id
}

output "rds_security_group_id" {
  value = aws_security_group.rds.id
}
