# -----------------------------------------------------------------------------
# Minimal S3 bucket for Config managed-rule testing.
#
# Design goals:
# - Cheap and fast to create / destroy
# - All security “knobs” that common S3 Config rules inspect are present and
#   can be toggled by the Python harness (versioning, encryption, public
#   access block, logging, etc.)
# - Clearly tagged with test-run-id so it can never be mistaken for a
#   production resource
# -----------------------------------------------------------------------------

resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  bucket_name = lower("cfg-test-${var.test_run_id}-${random_id.suffix.hex}")
}

resource "aws_s3_bucket" "test" {
  bucket = local.bucket_name

  # Force destroy is acceptable for a pure test resource
  force_destroy = true

  tags = merge(var.tags, {
    Name          = local.bucket_name
    "test-run-id" = var.test_run_id
  })
}

# -----------------------------------------------------------------------------
# Public Access Block – start in the “locked down” (compliant for most rules)
# state. The Python harness will relax it when it needs a NON_COMPLIANT state.
# -----------------------------------------------------------------------------
resource "aws_s3_bucket_public_access_block" "test" {
  bucket = aws_s3_bucket.test.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -----------------------------------------------------------------------------
# Server-side encryption – start enabled (AES256). Many rules care about this.
# -----------------------------------------------------------------------------
resource "aws_s3_bucket_server_side_encryption_configuration" "test" {
  bucket = aws_s3_bucket.test.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# -----------------------------------------------------------------------------
# Versioning – start suspended. Rules that require versioning will see this
# as NON_COMPLIANT until the harness enables it.
# -----------------------------------------------------------------------------
resource "aws_s3_bucket_versioning" "test" {
  bucket = aws_s3_bucket.test.id

  versioning_configuration {
    status = "Suspended"
  }
}

# -----------------------------------------------------------------------------
# Ownership controls – BucketOwnerEnforced is the modern default and removes
# ACL complexity that some older rules still inspect.
# -----------------------------------------------------------------------------
resource "aws_s3_bucket_ownership_controls" "test" {
  bucket = aws_s3_bucket.test.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}
