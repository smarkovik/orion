output "site_url" {
  value = module.seer.site_url
}

output "cloudfront_domain" {
  value = module.seer.cloudfront_domain
}

output "cloudfront_distribution_id" {
  value = module.seer.cloudfront_distribution_id
}

output "raw_bucket" {
  value = module.seer.raw_bucket
}

output "site_bucket" {
  value = module.seer.site_bucket
}

output "scrape_function_name" {
  value = module.seer.scrape_function_name
}

output "build_function_name" {
  value = module.seer.build_function_name
}

output "ecr_repository_urls" {
  value = module.seer.ecr_repository_urls
}
