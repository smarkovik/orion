variable "aws_account_id" {
  description = "The only account this root may be applied to."
  type        = string
}

variable "name_prefix" {
  type = string
}

variable "image_tag" {
  description = "Image tag in ECR; the pipeline passes the commit SHA."
  type        = string
}

variable "editions" {
  type = list(string)
}

variable "schedule_expression" {
  type = string
}

variable "schedule_enabled" {
  type = bool
}

variable "domain" {
  type = string
}

variable "route53_zone_id" {
  type = string
}

variable "alarm_email" {
  type = string
}

variable "block_indexing" {
  type    = bool
  default = false
}

variable "control_token_sha256" {
  type    = string
  default = ""
}

variable "control_cooldown_seconds" {
  type    = number
  default = 900
}

variable "lambda_architecture" {
  type    = string
  default = "x86_64"
}

variable "build_memory_mb" {
  type    = number
  default = 4096
}

variable "build_reserved_concurrency" {
  type    = number
  default = 1
}
