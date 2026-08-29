data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  bucket_name = lower("cfg-ct-logs-${var.test_run_id}-${random_id.suffix.hex}")
  trail_name  = "cfg-ct-${var.test_run_id}"
}

resource "aws_s3_bucket" "logs" {
  bucket        = local.bucket_name
  force_destroy = true
  tags = merge(var.tags, {
    Name        = local.bucket_name
    test-run-id = var.test_run_id
  })
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "logs" {
  bucket                  = aws_s3_bucket.logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "logs" {
  bucket = aws_s3_bucket.logs.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AWSCloudTrailAclCheck"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:GetBucketAcl"
        Resource  = aws_s3_bucket.logs.arn
      },
      {
        Sid       = "AWSCloudTrailWrite"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.logs.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
        Condition = {
          StringEquals = { "s3:x-amz-acl" = "bucket-owner-full-control" }
        }
      }
    ]
  })
}

resource "aws_cloudtrail" "harness" {
  name                          = local.trail_name
  s3_bucket_name                = aws_s3_bucket.logs.id
  include_global_service_events = false
  is_multi_region_trail         = false
  enable_log_file_validation    = false
  enable_logging                = true

  depends_on = [aws_s3_bucket_policy.logs]

  tags = merge(var.tags, {
    Name        = local.trail_name
    test-run-id = var.test_run_id
  })
  lifecycle {
    prevent_destroy = true
  }
}
