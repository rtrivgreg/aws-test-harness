output "instance_id" {
  value = aws_instance.harness.id
}
output "security_group_id" {
  value = aws_security_group.harness.id
}
