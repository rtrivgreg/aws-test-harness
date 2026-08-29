"""Throwaway EFS + backup plan for EFS backup-plan coverage rules. No Terraform."""

from __future__ import annotations

import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import log
from harness.tags import PURPOSE_TAG_KEY, PURPOSE_TAG_VALUE, TEST_RUN_ID_TAG_KEY


class EfsPlanProtectHarness:
    def __init__(
        self,
        test_run_id: str,
        region: Optional[str] = None,
        prefix: str = "cfg-efs-plan",
    ):
        self.test_run_id = test_run_id
        self.region = region or "us-east-1"
        self.prefix = prefix
        self.efs = boto3.client("efs", region_name=self.region)
        self.backup = boto3.client("backup", region_name=self.region)
        self.iam = boto3.client("iam")
        self.sts = boto3.client("sts")
        self.account = self.sts.get_caller_identity()["Account"]
        self.fs_id: Optional[str] = None
        self.plan_id: Optional[str] = None
        self.selection_id: Optional[str] = None
        self.vault_name = f"{prefix}-vault-{test_run_id}"

    def _tags(self, name: str) -> list[dict]:
        return [
            {"Key": TEST_RUN_ID_TAG_KEY, "Value": self.test_run_id},
            {"Key": PURPOSE_TAG_KEY, "Value": PURPOSE_TAG_VALUE},
            {"Key": "Name", "Value": name},
            {"Key": "ManagedBy", "Value": "aws-config-test-harness"},
        ]

    def _role_arn(self) -> str:
        return self.iam.get_role(RoleName="AWSBackupDefaultServiceRole")["Role"]["Arn"]

    def _wait_fs(self, fs_id: str, timeout: int = 180) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            fs = self.efs.describe_file_systems(FileSystemId=fs_id)["FileSystems"][0]
            if fs["LifeCycleState"] == "available":
                return
            time.sleep(3)
        raise TimeoutError(f"{fs_id} not available")

    def create_filesystem(self) -> str:
        name = f"{self.prefix}-{self.test_run_id}"
        created = self.efs.create_file_system(
            CreationToken=name,
            Encrypted=True,
            ThroughputMode="bursting",
            Backup=False,
            Tags=self._tags(name),
        )
        self.fs_id = created["FileSystemId"]
        log(f"Created EFS {self.fs_id}")
        self._wait_fs(self.fs_id)
        return self.fs_id

    def fs_arn(self) -> str:
        if not self.fs_id:
            raise RuntimeError("create_filesystem first")
        return (
            f"arn:aws:elasticfilesystem:{self.region}:{self.account}:"
            f"file-system/{self.fs_id}"
        )

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
                "BackupPlanName": f"{self.prefix}-{self.test_run_id}",
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
                "SelectionName": f"{self.prefix}-sel-{self.test_run_id}",
                "IamRoleArn": self._role_arn(),
                "Resources": [self.fs_arn()],
            },
        )
        self.selection_id = sel["SelectionId"]
        log(f"Created backup selection {self.selection_id} for {self.fs_arn()}")

    def unprotect(self) -> None:
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

    def cleanup(self) -> None:
        self.unprotect()
        if self.fs_id:
            try:
                self.efs.delete_file_system(FileSystemId=self.fs_id)
                log(f"Deleted EFS {self.fs_id}")
            except ClientError as exc:
                log(f"delete_file_system {self.fs_id}: {exc}", style="yellow")
            self.fs_id = None
