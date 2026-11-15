# Values come from the bootstrap outputs (backend_*). Backend blocks cannot use variables.
terraform {
  backend "s3" {
    bucket       = "seer-production-tfstate-000000000000" # placeholder: the production account id
    key          = "seer/production/terraform.tfstate"
    region       = "eu-central-1"
    use_lockfile = true # OpenTofu native S3 locking, no DynamoDB table
    encrypt      = true
  }
}
