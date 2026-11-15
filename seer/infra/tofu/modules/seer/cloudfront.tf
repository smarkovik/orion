locals {
  custom_domain = var.domain != ""

  # W3C fields of the v2 standard logs. c-ip, x-forwarded-for and cookies are left out on purpose.
  log_fields = [
    "date",
    "time",
    "x-edge-location",
    "sc-bytes",
    "cs-method",
    "cs(Host)",
    "cs-uri-stem",
    "sc-status",
    "cs(Referer)",
    "cs(User-Agent)",
    "cs-uri-query",
    "x-edge-result-type",
    "x-edge-request-id",
    "x-host-header",
    "cs-protocol",
    "cs-bytes",
    "time-taken",
    "x-edge-response-result-type",
    "cs-protocol-version",
    "time-to-first-byte",
    "x-edge-detailed-result-type",
    "sc-content-type",
    "sc-content-len",
  ]
}

data "aws_cloudfront_cache_policy" "origin_headers" {
  name = "UseOriginCacheControlHeaders"
}

resource "aws_cloudfront_origin_access_control" "site" {
  name                              = "${var.name_prefix}-site"
  description                       = "Site bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ---------- Custom domain certificate (us-east-1) ----------

resource "aws_acm_certificate" "site" {
  count    = local.custom_domain ? 1 : 0
  provider = aws.us_east_1

  domain_name       = var.domain
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
    precondition {
      condition     = var.route53_zone_id != ""
      error_message = "route53_zone_id is required when domain is set."
    }
  }
}

resource "aws_route53_record" "cert_validation" {
  for_each = local.custom_domain ? {
    for o in aws_acm_certificate.site[0].domain_validation_options : o.domain_name => {
      name   = o.resource_record_name
      type   = o.resource_record_type
      record = o.resource_record_value
    }
  } : {}

  zone_id         = var.route53_zone_id
  name            = each.value.name
  type            = each.value.type
  records         = [each.value.record]
  ttl             = 60
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "site" {
  count    = local.custom_domain ? 1 : 0
  provider = aws.us_east_1

  certificate_arn         = aws_acm_certificate.site[0].arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]
}

resource "aws_cloudfront_response_headers_policy" "noindex" {
  count = var.block_indexing ? 1 : 0

  name = "${var.name_prefix}-noindex"

  custom_headers_config {
    items {
      header   = "X-Robots-Tag"
      value    = "noindex, nofollow"
      override = true
    }
  }
}

# ---------- Distribution ----------

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  comment             = "${var.name_prefix} site"
  default_root_object = "index.html"
  http_version        = "http2and3"
  is_ipv6_enabled     = true
  price_class         = "PriceClass_100"
  aliases             = local.custom_domain ? [var.domain] : []

  origin {
    origin_id                = "site"
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  default_cache_behavior {
    target_origin_id       = "site"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    cache_policy_id        = data.aws_cloudfront_cache_policy.origin_headers.id

    response_headers_policy_id = var.block_indexing ? aws_cloudfront_response_headers_policy.noindex[0].id : null
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = local.custom_domain ? null : true
    acm_certificate_arn            = local.custom_domain ? aws_acm_certificate_validation.site[0].certificate_arn : null
    ssl_support_method             = local.custom_domain ? "sni-only" : null
    minimum_protocol_version       = local.custom_domain ? "TLSv1.2_2021" : null
  }
}

resource "aws_route53_record" "alias" {
  for_each = local.custom_domain ? toset(["A", "AAAA"]) : toset([])

  zone_id = var.route53_zone_id
  name    = var.domain
  type    = each.key

  alias {
    name                   = aws_cloudfront_distribution.site.domain_name
    zone_id                = aws_cloudfront_distribution.site.hosted_zone_id
    evaluate_target_health = false
  }
}

# ---------- Standard logging v2 -> raw bucket logs/cloudfront/ ----------

resource "aws_cloudwatch_log_delivery_source" "cloudfront" {
  provider = aws.us_east_1

  name         = "${var.name_prefix}-cloudfront"
  log_type     = "ACCESS_LOGS"
  resource_arn = aws_cloudfront_distribution.site.arn
}

resource "aws_cloudwatch_log_delivery_destination" "raw" {
  provider = aws.us_east_1

  name          = "${var.name_prefix}-raw-logs"
  output_format = "w3c"

  delivery_destination_configuration {
    destination_resource_arn = "${aws_s3_bucket.raw.arn}/${trimsuffix(local.logs_prefix, "/")}"
  }
}

resource "aws_cloudwatch_log_delivery" "cloudfront" {
  provider = aws.us_east_1

  delivery_source_name     = aws_cloudwatch_log_delivery_source.cloudfront.name
  delivery_destination_arn = aws_cloudwatch_log_delivery_destination.raw.arn
  field_delimiter          = "\t"
  record_fields            = local.log_fields

  s3_delivery_configuration {
    enable_hive_compatible_path = false
  }

  depends_on = [aws_s3_bucket_policy.raw]
}
