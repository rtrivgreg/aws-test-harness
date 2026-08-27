output "instance_id" {
  value = aws_instance.harness.id
}

output "unencrypted_volume_id" {
  value = aws_ebs_volume.unencrypted.id
}

output "encrypted_volume_id" {
  value = aws_ebs_volume.encrypted.id
}
