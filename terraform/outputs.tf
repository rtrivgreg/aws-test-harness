output "test_run_id" {
  description = "The test-run-id that was applied to all resources"
  value       = var.test_run_id
}

output "s3_test_bucket_name" {
  description = "Name of the minimal S3 bucket used for Config rule testing"
  value       = try(module.s3_test_bucket[0].bucket_name, null)
}

output "s3_test_bucket_arn" {
  description = "ARN of the minimal S3 bucket"
  value       = try(module.s3_test_bucket[0].bucket_arn, null)
}

output "s3_test_bucket_id" {
  description = "ID (same as name for S3) of the test bucket – used as ComplianceResourceId"
  value       = try(module.s3_test_bucket[0].bucket_id, null)
}
