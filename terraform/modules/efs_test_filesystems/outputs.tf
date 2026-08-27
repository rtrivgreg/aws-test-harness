output "unencrypted_id" {
  value = aws_efs_file_system.unencrypted.id
}

output "encrypted_id" {
  value = aws_efs_file_system.encrypted.id
}
