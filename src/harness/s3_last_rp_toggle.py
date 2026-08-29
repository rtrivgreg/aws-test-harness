"""On-demand Backup job for the live S3 test bucket. Does not delete the bucket."""

from __future__ import annotations

import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import log
from harness.tags import PURPOSE_TAG_KEY, PURPOSE_TAG_VALUE, TEST_RUN_ID_TAG_KEY


class S3LastRpHarness:
    def __init__(self, test_run_id: str, bucket_name: str, region: Optional[str] = None):
        self.test_run_id = test_run_id
        self.bucket_name = bucket_name
        self.region = region or "us-east-1"
        self.backup = boto3.client("backup", region_name=self.region)
        self.iam = boto3.client("iam")
        self.rp_arn: Optional[str] = None
        self.vault_name = f"cfg-s3-lastrp-vault-{test_run_id}"

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

    def start_and_wait(self, timeout_seconds: int = 900) -> str:
        vault = self.ensure_vault()
        job = self.backup.start_backup_job(
            BackupVaultName=vault,
            ResourceArn=self.bucket_arn(),
            IamRoleArn=self._role_arn(),
            IdempotencyToken=f"s3-lastrp-{self.test_run_id}",
            Lifecycle={"DeleteAfterDays": 1},
        )
        job_id = job["BackupJobId"]
        log(f"Started S3 backup job {job_id}")
        deadline = time.time() + timeout_seconds
        last = {}
        while time.time() < deadline:
            last = self.backup.describe_backup_job(BackupJobId=job_id)
            state = last.get("State")
            log(f"Backup job {job_id} state={state}")
            if state == "COMPLETED":
                self.rp_arn = last.get("RecoveryPointArn")
                log(f"Recovery point {self.rp_arn}")
                return self.rp_arn or ""
            if state in ("FAILED", "ABORTED", "EXPIRED"):
                raise RuntimeError(
                    f"Backup job {job_id} {state}: {last.get('StatusMessage')}"
                )
            time.sleep(15)
        raise TimeoutError(f"Backup job {job_id} not COMPLETED")

    def cleanup(self) -> None:
        if not self.rp_arn:
            return
        try:
            self.backup.delete_recovery_point(
                BackupVaultName=self.vault_name, RecoveryPointArn=self.rp_arn
            )
            log(f"Deleted recovery point {self.rp_arn}")
        except ClientError as exc:
            log(f"delete_recovery_point: {exc}", style="yellow")
