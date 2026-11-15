data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  account_id  = data.aws_caller_identity.current.account_id
  raw_bucket  = "${var.name_prefix}-raw-${local.account_id}"
  site_bucket = "${var.name_prefix}-site-${local.account_id}"
  repos       = toset(["scrape", "build"])

  scrape_name = "${var.name_prefix}-scrape"
  build_name  = "${var.name_prefix}-build"

  logs_prefix = "logs/cloudfront/"
}
