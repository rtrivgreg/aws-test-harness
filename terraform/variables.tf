variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "test_run_id" { type = string }
variable "environment" {
  type    = string
  default = "test"
}
variable "enable_s3_test_bucket" {
  type    = bool
  default = true
}
variable "enable_ebs_test_volumes" {
  type    = bool
  default = false
}
variable "enable_efs_test_filesystems" {
  type    = bool
  default = false
}
variable "enable_cloudtrail_test" {
  type    = bool
  default = false
}
variable "enable_fsx_test" {
  type    = bool
  default = false
}
variable "enable_ec2_test" {
  type    = bool
  default = false
}
variable "ebs_subnet_id" {
  type    = string
  default = ""
}
variable "fsx_subnet_id" {
  type    = string
  default = ""
}
variable "ec2_subnet_id" {
  type    = string
  default = ""
}
