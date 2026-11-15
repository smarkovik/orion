provider "aws" {
  region = var.region

  default_tags {
    tags = { Project = "seer", Environment = var.environment, ManagedBy = "opentofu-bootstrap" }
  }
}

data "aws_caller_identity" "current" {}

locals {
  account_id   = data.aws_caller_identity.current.account_id
  state_bucket = "${var.name_prefix}-tfstate-${local.account_id}"
  state_key    = "seer/${var.environment}/terraform.tfstate"
}

# ---------- State bucket ----------

resource "aws_s3_bucket" "state" {
  bucket = local.state_bucket

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    id     = "noncurrent-expiry"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }

  depends_on = [aws_s3_bucket_versioning.state]
}

data "aws_iam_policy_document" "state_bucket" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = data.aws_iam_policy_document.state_bucket.json

  depends_on = [aws_s3_bucket_public_access_block.state]
}

# ---------- GitHub OIDC ----------

# One provider per account. If it already exists, import it:
#   tofu import aws_iam_openid_connect_provider.github arn:aws:iam::<account>:oidc-provider/token.actions.githubusercontent.com
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "deploy_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # The GitHub environment claim: only jobs running in this environment can deploy to this account.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:environment:${var.environment}"]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name                 = "${var.name_prefix}-deploy"
  assume_role_policy   = data.aws_iam_policy_document.deploy_trust.json
  max_session_duration = 3600
}

locals {
  p          = var.name_prefix
  acct       = local.account_id
  arn_prefix = "arn:aws"
}

data "aws_iam_policy_document" "deploy" {
  # Remote state and native lock file.
  statement {
    sid       = "StateObjects"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.state.arn}/${local.state_key}", "${aws_s3_bucket.state.arn}/${local.state_key}.tflock"]
  }
  statement {
    sid       = "StateList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.state.arn]
  }

  # Stack buckets (raw and site).
  statement {
    sid     = "StackBuckets"
    actions = ["s3:*"]
    resources = [
      "${local.arn_prefix}:s3:::${local.p}-raw-${local.acct}",
      "${local.arn_prefix}:s3:::${local.p}-site-${local.acct}",
    ]
  }

  statement {
    sid       = "EcrPush"
    actions   = ["ecr:*"]
    resources = ["${local.arn_prefix}:ecr:*:${local.acct}:repository/${local.p}-*"]
  }
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid       = "Lambda"
    actions   = ["lambda:*"]
    resources = ["${local.arn_prefix}:lambda:*:${local.acct}:function:${local.p}-*"]
  }

  statement {
    sid     = "LambdaRoles"
    actions = ["iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:UpdateRole", "iam:UpdateAssumeRolePolicy", "iam:TagRole", "iam:UntagRole", "iam:PutRolePolicy", "iam:GetRolePolicy", "iam:DeleteRolePolicy", "iam:ListRolePolicies", "iam:ListAttachedRolePolicies", "iam:ListInstanceProfilesForRole", "iam:PassRole"]
    resources = [
      "${local.arn_prefix}:iam::${local.acct}:role/${local.p}-*",
    ]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:*"]
    resources = ["${local.arn_prefix}:logs:*:${local.acct}:log-group:/aws/lambda/${local.p}-*", "${local.arn_prefix}:logs:*:${local.acct}:log-group:/aws/lambda/${local.p}-*:*"]
  }

  # CloudFront standard logging v2 (vended log delivery) has no resource-level scoping.
  statement {
    sid = "LogDelivery"
    actions = [
      "logs:CreateDelivery", "logs:GetDelivery", "logs:UpdateDeliveryConfiguration", "logs:DeleteDelivery", "logs:ListDeliveries",
      "logs:PutDeliverySource", "logs:GetDeliverySource", "logs:DeleteDeliverySource", "logs:DescribeDeliverySources",
      "logs:PutDeliveryDestination", "logs:GetDeliveryDestination", "logs:DeleteDeliveryDestination", "logs:DescribeDeliveryDestinations",
      "logs:TagResource", "logs:UntagResource", "logs:ListTagsForResource",
      "logs:DescribeLogGroups", "logs:ListTagsLogGroup",
      "cloudfront:AllowVendedLogDeliveryForResource",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "Scheduler"
    actions   = ["scheduler:*"]
    resources = ["${local.arn_prefix}:scheduler:*:${local.acct}:schedule/*/${local.p}-*"]
  }

  statement {
    sid       = "Alarms"
    actions   = ["cloudwatch:PutMetricAlarm", "cloudwatch:DeleteAlarms", "cloudwatch:DescribeAlarms", "cloudwatch:ListTagsForResource", "cloudwatch:TagResource", "cloudwatch:UntagResource"]
    resources = ["*"]
  }

  statement {
    sid       = "Sns"
    actions   = ["sns:*"]
    resources = ["${local.arn_prefix}:sns:*:${local.acct}:${local.p}-*"]
  }

  # CloudFront, ACM and Route 53 cannot be scoped by name prefix here.
  statement {
    sid       = "CloudFront"
    actions   = ["cloudfront:*"]
    resources = ["*"]
  }
  statement {
    sid       = "Acm"
    actions   = ["acm:*"]
    resources = ["*"]
  }
  statement {
    sid       = "Route53"
    actions   = ["route53:*"]
    resources = ["*"]
  }

  statement {
    sid       = "Identity"
    actions   = ["sts:GetCallerIdentity", "iam:ListAccountAliases", "ec2:DescribeRegions"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "deploy"
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}
