variable "region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "clinical_rollout_stage" {
  description = "Fase 8 activation stage (1..9). Stage 10/legacy removal is deliberately unsupported."
  type        = number
  default     = 9

  validation {
    condition     = var.clinical_rollout_stage >= 1 && var.clinical_rollout_stage <= 9
    error_message = "clinical_rollout_stage must be between 1 and 9."
  }
}

variable "alarm_email" {
  type        = string
  description = "Email for alarm notifications"
}

variable "clerk_issuer_url" {
  description = "Clerk Issuer URL"
  type        = string
}

variable "clerk_jwks_url" {
  description = "Clerk JWKS URL"
  type        = string
}

variable "clerk_audience" {
  description = "Optional expected aud claim; azp is always validated"
  type        = string
  default     = ""
}

variable "ses_sender_email" {
  description = "Verified SES From address for appointment notification emails (e.g. citas@cloudmedrecord.com). Empty disables sending."
  type        = string
  default     = ""
}

variable "ses_domain" {
  description = "SES verified sending domain (From address domain)."
  type        = string
  default     = "cloudmedrecord.com"
}

variable "ses_mail_from_domain" {
  description = "SES custom MAIL FROM (envelope) subdomain for SPF/DMARC alignment."
  type        = string
  default     = "citas.cloudmedrecord.com"
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
