
variable "clerk_secret_key" {
  type      = string
  sensitive = true
}

variable "clerk_issuer_url" {
  type = string
}

variable "clerk_jwks_url" {
  type = string
}

variable "ses_sender_email" {
  type        = string
  description = "Verified SES identity used as the From address for appointment notifications. Empty disables sending."
  default     = ""
}
