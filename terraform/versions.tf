terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project       = "aws-config-test-harness"
      ManagedBy     = "terraform"
      # test-run-id is applied per-resource so different runs can coexist
    }
  }
}
