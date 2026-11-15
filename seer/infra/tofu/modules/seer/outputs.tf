output "site_url" {
  value = local.custom_domain ? "https://${var.domain}" : "https://${aws_cloudfront_distribution.site.domain_name}"
}

output "cloudfront_domain" {
  value = aws_cloudfront_distribution.site.domain_name
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.site.id
}

output "raw_bucket" {
  value = aws_s3_bucket.raw.bucket
}

output "site_bucket" {
  value = aws_s3_bucket.site.bucket
}

output "scrape_function_name" {
  value = aws_lambda_function.scrape.function_name
}

output "build_function_name" {
  value = aws_lambda_function.build.function_name
}

output "ecr_repository_urls" {
  value = { for k, r in aws_ecr_repository.fn : k => r.repository_url }
}

output "alarm_topic_arn" {
  value = aws_sns_topic.alarms.arn
}
