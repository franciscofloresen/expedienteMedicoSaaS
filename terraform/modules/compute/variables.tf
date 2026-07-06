
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
