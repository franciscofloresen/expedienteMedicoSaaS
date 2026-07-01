variable "region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "alarm_email" {
  type        = string
  description = "Email for alarm notifications"
}

variable "clerk_secret_key" {
  description = "Clerk API Secret Key"
  type        = string
  sensitive   = true
}

variable "clerk_issuer_url" {
  description = "Clerk Issuer URL"
  type        = string
}

variable "clerk_jwks_url" {
  description = "Clerk JWKS URL"
  type        = string
}

variable "custom_domain" {
  description = "Custom domain for the frontend application (e.g. app.cloudmedrecord.com or cloudmedrecord.com)"
  type        = string
  default     = ""
}

variable "acm_certificate_arn" {
  description = "ARN of the ACM certificate in us-east-1"
  type        = string
  default     = ""
}
