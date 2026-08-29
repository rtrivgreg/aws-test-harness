"""Backup plan around an existing S3 bucket. Does not create or delete the bucket."""

from __future__ import annotations

from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import log
from harness.tags import PURPOSE_TAG_KEY, PURPOSE_TAG_VALUE, TEST_RUN_ID_TAG_KEY


class S3PlanProtectHarness:
    def __init__(self, test_run_id: str, bucket_name: str, region: Optional[str] = None):
        self.test_run_id = test_run_id
        self.bucket_name = bucket_name
        self.region = region or "us-east-1"
        self.backup = boto3.client("backup", region_name=self.region)
        self.iam = boto3.client("iam")
        self.plan_id: Optional[str] = None
        self.selection_id: Optional[str] = None
        self.vault_name = f"cfg-s3-plan-vault-{test_run_id}"

    def bucket_arn(self) -> str:
        return f"arn:aws:s3:::{self.bucket_name}"

    def _role_arn(self) -> str:
        return self.iam.get_role(RoleName="AWSBackupDefaultServiceRole")["Role"]["Arn"]

    def ensure_vault(self) -> str:
        try:
            self.backup.create_backup_vault(
                BackupVaultName=self.vault_name,
                BackupVaultTags={
                    TEST_RUN_ID_TAG_KEY: self.test_run_id,
                    PURPOSE_TAG_KEY: PURPOSE_TAG_VALUE,
                },
            )
            log(f"Created vault {self.vault_name}")
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            log(f"create_backup_vault {self.vault_name}: {exc}", style="yellow")
            if code != "AlreadyExistsException":
                self.vault_name = f"cfg-rp-vault-{self.test_run_id}"
                log(f"Falling back to vault name {self.vault_name}")
        return self.vault_name

    def protect(self) -> None:
        vault = self.ensure_vault()
        created = self.backup.create_backup_plan(
            BackupPlan={
                "BackupPlanName": f"cfg-s3-plan-{self.test_run_id}",
                "Rules": [
                    {
                        "RuleName": "harness-daily",
                        "TargetBackupVaultName": vault,
                        "ScheduleExpression": "cron(0 5 ? * * *)",
                        "Lifecycle": {"DeleteAfterDays": 1},
                    }
                ],
            },
            BackupPlanTags={
                TEST_RUN_ID_TAG_KEY: self.test_run_id,
                PURPOSE_TAG_KEY: PURPOSE_TAG_VALUE,
            },
        )
        self.plan_id = created["BackupPlanId"]
        log(f"Created backup plan {self.plan_id}")
        sel = self.backup.create_backup_selection(
            BackupPlanId=self.plan_id,
            BackupSelection={
                "SelectionName": f"cfg-s3-plan-sel-{self.test_run_id}",
                "IamRoleArn": self._role_arn(),
                "Resources": [self.bucket_arn()],
            },
        )
        self.selection_id = sel["SelectionId"]
        log(f"Created backup selection {self.selection_id} for {self.bucket_arn()}")

    def cleanup(self) -> None:
        if self.plan_id and self.selection_id:
            try:
                self.backup.delete_backup_selection(
                    BackupPlanId=self.plan_id, SelectionId=self.selection_id
                )
                log(f"Deleted selection {self.selection_id}")
            except ClientError as exc:
                log(f"delete_backup_selection: {exc}", style="yellow")
            self.selection_id = None
        if self.plan_id:
            try:
                self.backup.delete_backup_plan(BackupPlanId=self.plan_id)
                log(f"Deleted plan {self.plan_id}")
            except ClientError as exc:
                log(f"delete_backup_plan: {exc}", style="yellow")
            self.plan_id = None
