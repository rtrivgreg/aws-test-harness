variable "aws_region" {
  description = "AWS region in which to create the test resources"
  type        = string
  default     = "us-east-1"
}

variable "test_run_id" {
  description = <<-EOT
    Unique identifier for this test run. Applied as a tag to every resource.
    Use a UUID or a short memorable value (e.g. from `uuidgen` or CI run id).
    Required so leftover resources can be identified and cleaned up safely.
  EOT
  type        = string
}

variable "environment" {
  description = "Logical environment name (dev, test, ci, ...)"
  type        = string
  default     = "test"
}

variable "enable_s3_test_bucket" {
  description = "Whether to create the minimal S3 bucket used for Config rule testing"
  type        = bool
  default     = true
}
