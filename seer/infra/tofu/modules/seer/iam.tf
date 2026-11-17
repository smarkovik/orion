data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ---------- scrape ----------

resource "aws_iam_role" "scrape" {
  name               = "${local.scrape_name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

data "aws_iam_policy_document" "scrape" {
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.scrape.arn}:*"]
  }

  statement {
    sid     = "RawWrite"
    actions = ["s3:PutObject"]
    resources = [
      "${aws_s3_bucket.raw.arn}/raw/*",
      "${aws_s3_bucket.raw.arn}/runs/*",
    ]
  }

  statement {
    sid       = "StateRead"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.raw.arn}/state/*"]
  }

  statement {
    sid       = "StartBuild"
    actions   = ["lambda:InvokeFunction"]
    resources = ["arn:aws:lambda:${data.aws_region.current.region}:${local.account_id}:function:${local.build_name}"]
  }

  # Without ListBucket a missing key reads as AccessDenied instead of NoSuchKey.
  statement {
    sid       = "StateList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.raw.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["state/*"]
    }
  }
}

resource "aws_iam_role_policy" "scrape" {
  name   = "scrape"
  role   = aws_iam_role.scrape.id
  policy = data.aws_iam_policy_document.scrape.json
}

# ---------- build ----------

resource "aws_iam_role" "build" {
  name               = "${local.build_name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

data "aws_iam_policy_document" "build" {
  # Hands the manifests it has no time left for to a new invocation of itself.
  statement {
    sid       = "ContinueBuild"
    actions   = ["lambda:InvokeFunction"]
    resources = ["arn:aws:lambda:${data.aws_region.current.region}:${local.account_id}:function:${local.build_name}"]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.build.arn}:*"]
  }

  statement {
    sid     = "RawRead"
    actions = ["s3:GetObject"]
    resources = [
      "${aws_s3_bucket.raw.arn}/raw/*",
      "${aws_s3_bucket.raw.arn}/runs/*",
    ]
  }

  statement {
    sid     = "RawReadWrite"
    actions = ["s3:GetObject", "s3:PutObject"]
    resources = [
      "${aws_s3_bucket.raw.arn}/state/*",
      "${aws_s3_bucket.raw.arn}/archive/*",
      "${aws_s3_bucket.raw.arn}/builds/*",
    ]
  }

  statement {
    sid       = "LogsReadDelete"
    actions   = ["s3:GetObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.raw.arn}/logs/*"]
  }

  statement {
    sid       = "RawList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.raw.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["raw/*", "runs/*", "state/*", "archive/*", "builds/*", "logs/*"]
    }
  }

  statement {
    sid       = "SiteReadWrite"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.site.arn}/*"]
  }

  statement {
    sid       = "SiteList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.site.arn]
  }
}

resource "aws_iam_role_policy" "build" {
  name   = "build"
  role   = aws_iam_role.build.id
  policy = data.aws_iam_policy_document.build.json
}

# ---------- scheduler ----------

data "aws_iam_policy_document" "scheduler_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${var.name_prefix}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_trust.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.scrape.arn, "${aws_lambda_function.scrape.arn}:*"]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "invoke-scrape"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}
