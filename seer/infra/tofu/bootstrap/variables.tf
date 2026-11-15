variable "environment" {
  description = "GitHub environment this account serves: staging or production."
  type        = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "name_prefix" {
  description = "Must equal name_prefix of the matching envs/ root (for example seer-staging)."
  type        = string
}

variable "github_repo" {
  description = "owner/repo allowed to assume the deploy role."
  type        = string
  default     = "smarkovik/orion"
}

variable "region" {
  type    = string
  default = "eu-central-1"
}
