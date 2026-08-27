output "test_run_id" {
  description = "The test-run-id that was applied to all resources"
  value       = var.test_run_id
}

output "s3_test_bucket_name" {
  value = try(module.s3_test_bucket[0].bucket_name, null)
}

output "s3_test_bucket_arn" {
  value = try(module.s3_test_bucket[0].bucket_arn, null)
}

output "s3_test_bucket_id" {
  value = try(module.s3_test_bucket[0].bucket_id, null)
}

output "ebs_instance_id" {
  value = try(module.ebs_test_volumes[0].instance_id, null)
}

output "ebs_unencrypted_volume_id" {
  value = try(module.ebs_test_volumes[0].unencrypted_volume_id, null)
}

output "ebs_encrypted_volume_id" {
  value = try(module.ebs_test_volumes[0].encrypted_volume_id, null)
}

output "ebs_unencrypted_snapshot_id" {
  value = try(module.ebs_test_volumes[0].unencrypted_snapshot_id, null)
}
