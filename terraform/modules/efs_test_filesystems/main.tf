# Two EFS file systems plus two access points on the encrypted FS.

resource "aws_efs_file_system" "unencrypted" {
  encrypted       = false
  throughput_mode = "bursting"

  tags = merge(var.tags, {
    Name             = "cfg-efs-unenc-${var.test_run_id}"
    test-run-id      = var.test_run_id
    harness-expected = "NON_COMPLIANT"
  })
}

resource "aws_efs_file_system" "encrypted" {
  encrypted       = true
  throughput_mode = "bursting"

  tags = merge(var.tags, {
    Name             = "cfg-efs-enc-${var.test_run_id}"
    test-run-id      = var.test_run_id
    harness-expected = "COMPLIANT"
  })
}

# Path / and no PosixUser -> NC for both access-point rules
resource "aws_efs_access_point" "noncompliant" {
  file_system_id = aws_efs_file_system.encrypted.id

  root_directory {
    path = "/"
  }

  tags = merge(var.tags, {
    Name             = "cfg-efs-ap-nc-${var.test_run_id}"
    test-run-id      = var.test_run_id
    harness-expected = "NON_COMPLIANT"
  })
}

# Subdir + PosixUser -> C for both access-point rules
resource "aws_efs_access_point" "compliant" {
  file_system_id = aws_efs_file_system.encrypted.id

  posix_user {
    gid = 1000
    uid = 1000
  }

  root_directory {
    path = "/harness"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "755"
    }
  }

  tags = merge(var.tags, {
    Name             = "cfg-efs-ap-c-${var.test_run_id}"
    test-run-id      = var.test_run_id
    harness-expected = "COMPLIANT"
  })
}
