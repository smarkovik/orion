locals {
  base_env = {
    RAW_BUCKET    = aws_s3_bucket.raw.bucket
    SITE_BUCKET   = aws_s3_bucket.site.bucket
    IGNORE_ROBOTS = "false"
  }

  # From docker-compose.yml, minus the local-only variables (S3_ENDPOINT_URL, S3_AUTO_CREATE, LOGS_DIR, emulator keys).
  scrape_env = merge(local.base_env, {
    HOURS                   = "48"
    REQUEST_DELAY_S         = "2"
    MAX_ARTICLES_PER_SOURCE = "150"
    REFRESH_HOURS           = "6"
    MAX_REFRESH_PER_SOURCE  = "20"
  })

  build_env = merge(local.base_env, {
    CHANGE_MIN_RATIO     = "0.05"
    STATE_HOURS          = "48"
    WINDOW_HOURS         = "48"
    MODEL                = "intfloat/multilingual-e5-base"
    STORY_THRESHOLD      = "0.92"
    STORY_OPEN_HOURS     = "48"
    STORY_MAX_GAP_HOURS  = "18"
    STORY_MAX_SPAN_HOURS = "24"
    SITE_CACHE_SECONDS   = "300"
    TOP_LIMIT            = "60"
    LATEST_LIMIT         = "60"
    MIN_SOURCES          = "2"
    THUMBS_PER_RUN       = "80"
    SITE_FILE            = "/var/task/site.yaml"
  })
}

resource "aws_cloudwatch_log_group" "scrape" {
  name              = "/aws/lambda/${local.scrape_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "build" {
  name              = "/aws/lambda/${local.build_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "scrape" {
  function_name = local.scrape_name
  role          = aws_iam_role.scrape.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.fn["scrape"].repository_url}:${var.image_tag}"
  architectures = ["x86_64"]
  memory_size   = 512
  timeout       = 600

  environment {
    variables = local.scrape_env
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.scrape.name
  }

  depends_on = [aws_iam_role_policy.scrape]
}

resource "aws_lambda_function" "build" {
  function_name                  = local.build_name
  role                           = aws_iam_role.build.arn
  package_type                   = "Image"
  image_uri                      = "${aws_ecr_repository.fn["build"].repository_url}:${var.image_tag}"
  architectures                  = ["x86_64"]
  memory_size                    = 4096
  timeout                        = 900
  reserved_concurrent_executions = var.build_reserved_concurrency

  ephemeral_storage {
    size = 1024
  }

  environment {
    variables = local.build_env
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.build.name
  }

  depends_on = [aws_iam_role_policy.build]
}

# S3 invokes asynchronously; a throttled event (reserved concurrency 1) is retried for up to 6 hours.
resource "aws_lambda_function_event_invoke_config" "build" {
  function_name                = aws_lambda_function.build.function_name
  maximum_retry_attempts       = 2
  maximum_event_age_in_seconds = 21600
}

resource "aws_lambda_permission" "s3_invoke_build" {
  statement_id   = "s3-raw"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.build.function_name
  principal      = "s3.amazonaws.com"
  source_arn     = aws_s3_bucket.raw.arn
  source_account = local.account_id
}

resource "aws_s3_bucket_notification" "raw" {
  bucket = aws_s3_bucket.raw.id

  lambda_function {
    id                  = "build-on-manifest"
    lambda_function_arn = aws_lambda_function.build.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "runs/"
    filter_suffix       = ".json"
  }

  depends_on = [aws_lambda_permission.s3_invoke_build]
}
