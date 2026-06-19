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
