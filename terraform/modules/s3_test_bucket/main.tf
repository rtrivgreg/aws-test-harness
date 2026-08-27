resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  bucket_name = lower("cfg-test-${var.test_run_id}-${random_id.suffix.hex}")
  logs_name   = lower("cfg-test-logs-${var.test_run_id}-${random_id.suffix.hex}")
}

resource "aws_s3_bucket" "test" {
  bucket        = local.bucket_name
  force_destroy = true
  tags = merge(var.tags, {
    Name          = local.bucket_name
    "test-run-id" = var.test_run_id
  })
}

resource "aws_s3_bucket_public_access_block" "test" {
  bucket                  = aws_s3_bucket.test.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "test" {
  bucket = aws_s3_bucket.test.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "test" {
  bucket = aws_s3_bucket.test.id
  versioning_configuration {
    status = "Suspended"
  }
}

resource "aws_s3_bucket_ownership_controls" "test" {
  bucket = aws_s3_bucket.test.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket" "logs" {
  bucket        = local.logs_name
  force_destroy = true
  tags = merge(var.tags, {
    Name          = local.logs_name
    "test-run-id" = var.test_run_id
    Purpose       = "s3-access-logs-target"
  })
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
    Statement = [{
      Sid    = "S3ServerAccessLogsPolicy"
      Effect = "Allow"
      Principal = { Service = "logging.s3.amazonaws.com" }
      Action   = "s3:PutObject"
      Resource = "${aws_s3_bucket.logs.arn}/*"
      Condition = {
        ArnLike = { "aws:SourceArn" = aws_s3_bucket.test.arn }
      }
    }]
  })
}
