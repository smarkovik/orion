output "deploy_role_arn" {
  description = "Set as the AWS_ROLE_ARN variable of the matching GitHub environment."
  value       = aws_iam_role.deploy.arn
}

output "account_id" {
  description = "Set as aws_account_id in the matching envs/ terraform.tfvars."
  value       = local.account_id
}

output "backend_bucket" {
  value = aws_s3_bucket.state.bucket
}

output "backend_key" {
  value = local.state_key
}

output "backend_region" {
  value = var.region
}
