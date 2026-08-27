# Two EFS file systems. Encryption is set at create time only.

resource "aws_efs_file_system" "unencrypted" {
  encrypted  = false
  throughput_mode = "bursting"

  tags = merge(var.tags, {
    Name             = "cfg-efs-unenc-${var.test_run_id}"
    test-run-id      = var.test_run_id
    harness-expected = "NON_COMPLIANT"
  })
}

resource "aws_efs_file_system" "encrypted" {
  encrypted  = true
  throughput_mode = "bursting"

  tags = merge(var.tags, {
    Name             = "cfg-efs-enc-${var.test_run_id}"
    test-run-id      = var.test_run_id
    harness-expected = "COMPLIANT"
  })
}
