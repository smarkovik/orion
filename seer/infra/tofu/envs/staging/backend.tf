# Values come from the bootstrap outputs (backend_*). Backend blocks cannot use variables.
terraform {
  backend "s3" {
    bucket       = "seer-staging-tfstate-000000000000" # placeholder: the staging account id
    key          = "seer/staging/terraform.tfstate"
    region       = "eu-central-1"
    use_lockfile = true # OpenTofu native S3 locking, no DynamoDB table
    encrypt      = true
  }
}
