resource "aws_scheduler_schedule" "scrape" {
  for_each = toset(var.editions)

  name                         = "${var.name_prefix}-scrape-${each.key}"
  state                        = var.schedule_enabled ? "ENABLED" : "DISABLED"
  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = var.schedule_timezone

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.scrape.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({ edition = each.key })

    retry_policy {
      maximum_retry_attempts = 2
    }
  }
}
