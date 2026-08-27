locals {
  common_tags = {
    "test-run-id" = var.test_run_id
    "Environment" = var.environment
    "Purpose"     = "aws-config-rule-testing"
  }
}

module "s3_test_bucket" {
  source = "./modules/s3_test_bucket"
  count  = var.enable_s3_test_bucket ? 1 : 0

  test_run_id = var.test_run_id
  tags        = local.common_tags
}

module "ebs_test_volumes" {
  source = "./modules/ebs_test_volumes"
  count  = var.enable_ebs_test_volumes ? 1 : 0

  test_run_id = var.test_run_id
  tags        = local.common_tags
}
