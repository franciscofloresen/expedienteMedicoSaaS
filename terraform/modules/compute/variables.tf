
variable "clerk_issuer_url" {
  type = string
}

variable "clerk_jwks_url" {
  type = string
}

variable "app_config_secret_arn" {
  description = "ARN of app-config; Lambda receives no secret value"
  type        = string
}

variable "clerk_audience" {
  description = "Optional expected aud claim for Clerk session tokens"
  type        = string
  default     = ""
}

variable "ses_domain" {
  description = "SES identity domain used to scope SendEmail permissions"
  type        = string
}

variable "ses_sender_email" {
  type        = string
  description = "Verified SES identity used as the From address for appointment notifications. Empty disables sending."
  default     = ""
}

variable "clinical_rollout_stage" {
  description = "Ordered clinical activation stage for Fase 8"
  type        = number
}
