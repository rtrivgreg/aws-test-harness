locals {
  common_tags = {
    "test-run-id" = var.test_run_id
    "Environment" = var.environment
    "Purpose"     = "aws-config-rule-testing"
  }
}

module "s3_test_bucket" {
  source      = "./modules/s3_test_bucket"
  count       = var.enable_s3_test_bucket ? 1 : 0
  test_run_id = var.test_run_id
  tags        = local.common_tags
}

module "ebs_test_volumes" {
  source      = "./modules/ebs_test_volumes"
  count       = var.enable_ebs_test_volumes ? 1 : 0
  test_run_id = var.test_run_id
  tags        = local.common_tags
  subnet_id   = var.ebs_subnet_id
}

module "efs_test_filesystems" {
  source      = "./modules/efs_test_filesystems"
  count       = var.enable_efs_test_filesystems ? 1 : 0
  test_run_id = var.test_run_id
  tags        = local.common_tags
}

module "cloudtrail_test" {
  source      = "./modules/cloudtrail_test"
  count       = var.enable_cloudtrail_test ? 1 : 0
  test_run_id = var.test_run_id
  tags        = local.common_tags
}
