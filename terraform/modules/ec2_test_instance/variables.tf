variable "test_run_id" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}
variable "subnet_id" {
  type    = string
  default = ""
}
