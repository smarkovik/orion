terraform {
  required_version = ">= 1.10"

  required_providers {
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.4"
    }
    aws = {
      source                = "hashicorp/aws"
      version               = ">= 6.0"
      configuration_aliases = [aws.us_east_1]
    }
  }
}
