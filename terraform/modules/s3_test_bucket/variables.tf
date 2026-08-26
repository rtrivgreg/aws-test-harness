variable "test_run_id" {
  description = "Unique run identifier – applied as a tag"
  type        = string
}

variable "tags" {
  description = "Additional tags to apply to the bucket"
  type        = map(string)
  default     = {}
}
