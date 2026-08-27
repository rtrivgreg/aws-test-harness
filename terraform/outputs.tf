output "test_run_id" {
  value = var.test_run_id
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

output "efs_unencrypted_id" {
  value = try(module.efs_test_filesystems[0].unencrypted_id, null)
}

output "efs_encrypted_id" {
  value = try(module.efs_test_filesystems[0].encrypted_id, null)
}

output "efs_access_point_nc_id" {
  value = try(module.efs_test_filesystems[0].access_point_nc_id, null)
}

output "efs_access_point_c_id" {
  value = try(module.efs_test_filesystems[0].access_point_c_id, null)
}
