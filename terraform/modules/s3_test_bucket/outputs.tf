output "bucket_name" { value = aws_s3_bucket.test.bucket }
output "bucket_arn" { value = aws_s3_bucket.test.arn }
output "bucket_id" { value = aws_s3_bucket.test.id }
output "bucket_region" { value = aws_s3_bucket.test.region }
output "logs_bucket_name" { value = aws_s3_bucket.logs.bucket }
