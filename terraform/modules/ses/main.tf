# ============================================================
# MedRecord SaaS — SES Module
# Domain identity + DKIM + custom MAIL FROM domain for
# transactional appointment (cita) notification emails.
#
# NOTE: DNS for cloudmedrecord.com is NOT managed by Terraform
# (no Route53 zone in this stack). This module creates the SES
# identity and outputs the DNS records you must add at your DNS
# provider to complete verification (see `dns_records` output).
# ============================================================

variable "domain" {
  type        = string
  description = "Verified sending domain (From address domain), e.g. cloudmedrecord.com"
}

variable "mail_from_domain" {
  type        = string
  description = "Custom MAIL FROM (envelope/Return-Path) subdomain, e.g. citas.cloudmedrecord.com"
}

variable "region" {
  type        = string
  default     = "us-east-1"
  description = "SES region (must match where the account left the sandbox)"
}

resource "aws_ses_domain_identity" "this" {
  domain = var.domain
}

resource "aws_ses_domain_dkim" "this" {
  domain = aws_ses_domain_identity.this.domain
}

resource "aws_ses_domain_mail_from" "this" {
  domain                 = aws_ses_domain_identity.this.domain
  mail_from_domain       = var.mail_from_domain
  behavior_on_mx_failure = "UseDefaultValue"
}

# ── DNS records to add at your DNS provider ──

output "dns_records" {
  description = "All DNS records required to verify the domain, DKIM, and custom MAIL FROM."
  value = {
    # 1) Domain ownership verification (TXT)
    domain_verification = {
      name  = "_amazonses.${var.domain}"
      type  = "TXT"
      value = aws_ses_domain_identity.this.verification_token
    }

    # 2) DKIM — three CNAME records (email authentication / DMARC alignment)
    dkim = [
      for token in aws_ses_domain_dkim.this.dkim_tokens : {
        name  = "${token}._domainkey.${var.domain}"
        type  = "CNAME"
        value = "${token}.dkim.amazonses.com"
      }
    ]

    # 3) Custom MAIL FROM — MX + SPF TXT on the subdomain
    mail_from_mx = {
      name     = var.mail_from_domain
      type     = "MX"
      value    = "feedback-smtp.${var.region}.amazonses.com"
      priority = 10
    }
    mail_from_spf = {
      name  = var.mail_from_domain
      type  = "TXT"
      value = "v=spf1 include:amazonses.com ~all"
    }
  }
}

output "domain_identity_arn" {
  value = aws_ses_domain_identity.this.arn
}
