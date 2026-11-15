provider "aws" {
  region              = "eu-central-1"
  allowed_account_ids = [var.aws_account_id]

  default_tags {
    tags = { Project = "seer", Environment = "staging", ManagedBy = "opentofu" }
  }
}

# CloudFront certificates and CloudFront log delivery live in us-east-1.
provider "aws" {
  alias               = "us_east_1"
  region              = "us-east-1"
  allowed_account_ids = [var.aws_account_id]

  default_tags {
    tags = { Project = "seer", Environment = "staging", ManagedBy = "opentofu" }
  }
}

module "seer" {
  source = "../../modules/seer"

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  name_prefix         = var.name_prefix
  image_tag           = var.image_tag
  editions            = var.editions
  schedule_expression = var.schedule_expression
  schedule_enabled    = var.schedule_enabled
  domain              = var.domain
  route53_zone_id     = var.route53_zone_id
  alarm_email         = var.alarm_email

  block_indexing             = var.block_indexing
  build_reserved_concurrency = var.build_reserved_concurrency
  build_memory_mb            = var.build_memory_mb
}
