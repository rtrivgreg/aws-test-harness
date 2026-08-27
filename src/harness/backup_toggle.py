"""Update AWS Backup plan retention (delete_after days)."""

from __future__ import annotations

from typing import Optional

import boto3

from harness.dry_run import dry_run_guard, log


class BackupToggle:
    def __init__(self, plan_id: str, vault_name: str, region: Optional[str] = None):
        self.plan_id = plan_id
        self.vault_name = vault_name
        self.region = region or "us-east-1"
        self.backup = boto3.client("backup", region_name=self.region)

    @dry_run_guard("Update backup plan retention")
    def set_retention_days(self, days: int) -> None:
        log(f"Set backup plan {self.plan_id} delete_after={days}")
        self.backup.update_backup_plan(
            BackupPlanId=self.plan_id,
            BackupPlan={
                "BackupPlanName": f"cfg-backup-plan-retention-{days}",
                "Rules": [
                    {
                        "RuleName": "harness-daily",
                        "TargetBackupVaultName": self.vault_name,
                        "ScheduleExpression": "cron(0 5 ? * * *)",
                        "Lifecycle": {"DeleteAfterDays": days},
                    }
                ],
            },
        )
