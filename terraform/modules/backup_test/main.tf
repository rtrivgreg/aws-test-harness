resource "aws_backup_vault" "harness" {
  name = "cfg-backup-vault-${var.test_run_id}"
  tags = merge(var.tags, {
    Name        = "cfg-backup-vault-${var.test_run_id}"
    test-run-id = var.test_run_id
  })
}

resource "aws_backup_plan" "harness" {
  name = "cfg-backup-plan-${var.test_run_id}"

  rule {
    rule_name         = "harness-daily"
    target_vault_name = aws_backup_vault.harness.name
    schedule          = "cron(0 5 ? * * *)"
    lifecycle {
      delete_after = 7
    }
  }

  tags = merge(var.tags, {
    Name        = "cfg-backup-plan-${var.test_run_id}"
    test-run-id = var.test_run_id
  })
}
