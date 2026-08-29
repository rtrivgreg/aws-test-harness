"""Throwaway EBS volume + on-demand Backup job for last-RP-created."""

from __future__ import annotations

import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import log
from harness.tags import PURPOSE_TAG_KEY, PURPOSE_TAG_VALUE, TEST_RUN_ID_TAG_KEY


class EbsLastRpHarness:
    def __init__(self, test_run_id: str, region: Optional[str] = None):
        self.test_run_id = test_run_id
        self.region = region or "us-east-1"
        self.ec2 = boto3.client("ec2", region_name=self.region)
        self.backup = boto3.client("backup", region_name=self.region)
        self.iam = boto3.client("iam")
        self.sts = boto3.client("sts")
        self.account = self.sts.get_caller_identity()["Account"]
        self.volume_id: Optional[str] = None
        self.rp_arn: Optional[str] = None
        self.vault_name = f"cfg-lastrp-vault-{test_run_id}"

    def _az(self) -> str:
        zones = self.ec2.describe_availability_zones(
            Filters=[{"Name": "state", "Values": ["available"]}]
        )["AvailabilityZones"]
        return zones[0]["ZoneName"]

    def _role_arn(self) -> str:
        return self.iam.get_role(RoleName="AWSBackupDefaultServiceRole")["Role"]["Arn"]

    def create_volume(self) -> str:
        name = f"cfg-lastrp-vol-{self.test_run_id}"
        vol = self.ec2.create_volume(
            AvailabilityZone=self._az(),
            Size=1,
            VolumeType="gp3",
            Encrypted=True,
            TagSpecifications=[
                {
                    "ResourceType": "volume",
                    "Tags": [
                        {"Key": TEST_RUN_ID_TAG_KEY, "Value": self.test_run_id},
                        {"Key": PURPOSE_TAG_KEY, "Value": PURPOSE_TAG_VALUE},
                        {"Key": "Name", "Value": name},
                        {"Key": "ManagedBy", "Value": "aws-config-test-harness"},
                    ],
                }
            ],
        )["VolumeId"]
        log(f"Created last-RP volume {vol}")
        deadline = time.time() + 180
        while time.time() < deadline:
            state = self.ec2.describe_volumes(VolumeIds=[vol])["Volumes"][0]["State"]
            if state == "available":
                self.volume_id = vol
                return vol
            time.sleep(3)
        raise TimeoutError(f"{vol} not available")

    def volume_arn(self) -> str:
        if not self.volume_id:
            raise RuntimeError("create_volume first")
        return f"arn:aws:ec2:{self.region}:{self.account}:volume/{self.volume_id}"

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
            ResourceArn=self.volume_arn(),
            IamRoleArn=self._role_arn(),
            IdempotencyToken=f"lastrp-{self.test_run_id}-{self.volume_id[-8:]}",
            Lifecycle={"DeleteAfterDays": 1},
        )
        job_id = job["BackupJobId"]
        log(f"Started backup job {job_id}")
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
        if self.rp_arn:
            try:
                self.backup.delete_recovery_point(
                    BackupVaultName=self.vault_name, RecoveryPointArn=self.rp_arn
                )
                log(f"Deleted recovery point {self.rp_arn}")
            except ClientError as exc:
                log(f"delete_recovery_point: {exc}", style="yellow")
        if self.volume_id:
            try:
                self.ec2.delete_volume(VolumeId=self.volume_id)
                log(f"Deleted volume {self.volume_id}")
            except ClientError as exc:
                log(f"delete_volume: {exc}", style="yellow")
            self.volume_id = None
