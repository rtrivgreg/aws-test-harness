output "bucket_name" {
  description = "Name of the test bucket"
  value       = aws_s3_bucket.test.bucket
}

output "bucket_arn" {
  description = "ARN of the test bucket"
  value       = aws_s3_bucket.test.arn
}

output "bucket_id" {
  description = "ID of the test bucket (same as name for S3)"
  value       = aws_s3_bucket.test.id
}

output "bucket_region" {
  description = "Region of the test bucket"
  value       = aws_s3_bucket.test.region
}
