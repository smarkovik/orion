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

variable "build_memory_mb" {
  type    = number
  default = 4096
}

variable "build_reserved_concurrency" {
  type    = number
  default = 1
}
