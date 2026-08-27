output "trail_name" {
  value = aws_cloudtrail.harness.name
}

output "trail_arn" {
  value = aws_cloudtrail.harness.arn
}

output "log_bucket" {
  value = aws_s3_bucket.logs.id
}
