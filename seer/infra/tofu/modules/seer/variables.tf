variable "name_prefix" {
  description = "Prefix for every resource name, for example seer-staging."
  type        = string
}

variable "image_tag" {
  description = "Tag of the scrape and build images in ECR (the commit SHA)."
  type        = string
}

variable "editions" {
  description = "Edition codes, as in sources.yaml. One schedule and one set of site lifecycle rules each."
  type        = list(string)
  default     = ["mk", "fr"]
}

variable "schedule_expression" {
  description = "EventBridge Scheduler expression for the scrape of every edition."
  type        = string
  default     = "cron(0 8-22 * * ? *)"
}

variable "schedule_timezone" {
  description = "Time zone of the schedule expression."
  type        = string
  default     = "Europe/Skopje"
}

variable "schedule_enabled" {
  description = "Set false to pause scraping."
  type        = bool
  default     = true
}

variable "domain" {
  description = "Custom domain of the site. Empty serves the CloudFront domain only."
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Route 53 hosted zone of var.domain (certificate validation and alias records). Required when domain is set."
  type        = string
  default     = ""
}

variable "alarm_email" {
  description = "Email subscribed to the alarm topic. Empty creates no subscription."
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "CloudWatch log retention of both functions."
  type        = number
  default     = 14
}

variable "block_indexing" {
  description = "Send X-Robots-Tag: noindex, nofollow on every response (sandbox and staging)."
  type        = bool
  default     = false
}

variable "build_reserved_concurrency" {
  description = "Reserved concurrency of the build Lambda (serializes builds). -1 leaves it unreserved, for accounts with the default quota of 10."
  type        = number
  default     = 1
}
