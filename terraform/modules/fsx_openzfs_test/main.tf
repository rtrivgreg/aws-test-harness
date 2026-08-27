data "aws_subnets" "available" {
  filter {
    name   = "state"
    values = ["available"]
  }
}

locals {
  subnet_id = var.subnet_id != "" ? var.subnet_id : try(data.aws_subnets.available.ids[0], "")
}

resource "aws_fsx_openzfs_file_system" "harness" {
  subnet_ids          = [local.subnet_id]
  deployment_type     = "SINGLE_AZ_1"
  storage_capacity    = 64
  throughput_capacity = 64

  copy_tags_to_backups = false
  copy_tags_to_volumes = false

  tags = merge(var.tags, {
    Name        = "cfg-fsx-${var.test_run_id}"
    test-run-id = var.test_run_id
  })
}
