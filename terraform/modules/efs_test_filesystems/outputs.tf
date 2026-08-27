output "unencrypted_id" {
  value = aws_efs_file_system.unencrypted.id
}

output "encrypted_id" {
  value = aws_efs_file_system.encrypted.id
}

output "access_point_nc_id" {
  value = aws_efs_access_point.noncompliant.id
}

output "access_point_c_id" {
  value = aws_efs_access_point.compliant.id
}
