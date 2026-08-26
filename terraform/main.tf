# -----------------------------------------------------------------------------
# Root module – provisions the minimal shared resources required by the
# Config rule test harness.
#
# Current vertical slice: S3
# Later slices will add modules for EBS, EFS, EC2, CloudTrail, Backup, etc.
# -----------------------------------------------------------------------------

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
