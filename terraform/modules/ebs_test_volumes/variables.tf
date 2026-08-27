variable "test_run_id" {
  description = "Unique run identifier – applied as a tag"
  type        = string
}

variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
}

variable "volume_size_gb" {
  description = "Size of each test volume in GiB"
  type        = number
  default     = 1
}
