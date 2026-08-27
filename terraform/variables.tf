variable "aws_region" {
  description = "AWS region in which to create the test resources"
  type        = string
  default     = "us-east-1"
}

variable "test_run_id" {
  description = "Unique identifier for this test run. Applied as a tag to every resource."
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

variable "enable_ebs_test_volumes" {
  description = "Whether to create the EBS test instance + encrypted/unencrypted volumes"
  type        = bool
  default     = false
}

variable "ebs_subnet_id" {
  description = "Optional subnet for the EBS test instance"
  type        = string
  default     = ""
}
