# Sync trigger and Lambda cost for the admin page. Reached only through CloudFront at /system/control/ (OAC signs the
# calls to the function URL, which uses AWS_IAM auth), and the handler also checks a token. Off while no token is set.
locals {
  control_enabled = var.control_token_sha256 != ""
  control_name    = "${var.name_prefix}-control"
}

data "archive_file" "control" {
  count       = local.control_enabled ? 1 : 0
  type        = "zip"
  source_file = "${path.module}/../../../../tests/cluster_prototype/lambdas/control/handler.py"
  output_path = "${path.root}/control.zip"
}

resource "aws_cloudwatch_log_group" "control" {
  count             = local.control_enabled ? 1 : 0
  name              = "/aws/lambda/${local.control_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "control" {
  count              = local.control_enabled ? 1 : 0
  name               = "${local.control_name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

data "aws_iam_policy_document" "control" {
  count = local.control_enabled ? 1 : 0

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.control[0].arn}:*"]
  }

  statement {
    sid     = "ReadFunctionLogs"
    actions = ["logs:FilterLogEvents"]
    resources = [
      aws_cloudwatch_log_group.scrape.arn,
      "${aws_cloudwatch_log_group.scrape.arn}:*",
      aws_cloudwatch_log_group.build.arn,
      "${aws_cloudwatch_log_group.build.arn}:*",
    ]
  }

  statement {
    sid       = "StartScrape"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.scrape.arn]
  }
}

resource "aws_iam_role_policy" "control" {
  count  = local.control_enabled ? 1 : 0
  name   = "control"
  role   = aws_iam_role.control[0].id
  policy = data.aws_iam_policy_document.control[0].json
}

resource "aws_lambda_function" "control" {
  count            = local.control_enabled ? 1 : 0
  function_name    = local.control_name
  role             = aws_iam_role.control[0].arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  architectures    = ["x86_64"]
  memory_size      = 256
  timeout          = 30
  filename         = data.archive_file.control[0].output_path
  source_code_hash = data.archive_file.control[0].output_base64sha256

  environment {
    variables = {
      SCRAPE_FUNCTION    = aws_lambda_function.scrape.function_name
      EDITIONS           = join(",", var.editions)
      SCRAPE_LOG_GROUP   = aws_cloudwatch_log_group.scrape.name
      BUILD_LOG_GROUP    = aws_cloudwatch_log_group.build.name
      TOKEN_SHA256       = var.control_token_sha256
      COOLDOWN_SECONDS   = tostring(var.control_cooldown_seconds)
      MAX_STARTS_PER_DAY = tostring(var.control_max_starts_per_day)
    }
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.control[0].name
  }

  depends_on = [aws_iam_role_policy.control]
}

resource "aws_lambda_function_url" "control" {
  count              = local.control_enabled ? 1 : 0
  function_name      = aws_lambda_function.control[0].function_name
  authorization_type = "AWS_IAM"
}

resource "aws_cloudfront_origin_access_control" "control" {
  count                             = local.control_enabled ? 1 : 0
  name                              = local.control_name
  description                       = "Control function URL"
  origin_access_control_origin_type = "lambda"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Function URLs need both actions for the calling principal.
resource "aws_lambda_permission" "control_url" {
  count                  = local.control_enabled ? 1 : 0
  statement_id           = "cloudfront-invoke-url"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.control[0].function_name
  principal              = "cloudfront.amazonaws.com"
  source_arn             = aws_cloudfront_distribution.site.arn
  function_url_auth_type = "AWS_IAM"
}

resource "aws_lambda_permission" "control_invoke" {
  count                    = local.control_enabled ? 1 : 0
  statement_id             = "cloudfront-invoke"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.control[0].function_name
  principal                = "cloudfront.amazonaws.com"
  source_arn               = aws_cloudfront_distribution.site.arn
  invoked_via_function_url = true
}
