"""AWS Backup plan retention toggle and throwaway Backup helpers."""

from __future__ import annotations

import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import dry_run_guard, log
from harness.tags import PURPOSE_TAG_KEY, PURPOSE_TAG_VALUE, TEST_RUN_ID_TAG_KEY


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


class RecoveryPointHarness:
    """Throwaway EBS volumes + vault for BACKUP_RECOVERY_POINT_ENCRYPTED. Parked."""

    def __init__(self, test_run_id: str, region: Optional[str] = None):
        self.test_run_id = test_run_id
        self.region = region or "us-east-1"
        self.backup = boto3.client("backup", region_name=self.region)
        self.ec2 = boto3.client("ec2", region_name=self.region)
        self.sts = boto3.client("sts", region_name=self.region)
        self.iam = boto3.client("iam")
        self.account = self.sts.get_caller_identity()["Account"]
        self.vault_name = f"cfg-rp-vault-{test_run_id}"
        self.unenc_volume_id: Optional[str] = None
        self.enc_volume_id: Optional[str] = None
        self.nc_rp_arn: Optional[str] = None
        self.c_rp_arn: Optional[str] = None
        self._vault_created = False

    def _tags(self, name: str) -> list[dict]:
        return [
            {"Key": TEST_RUN_ID_TAG_KEY, "Value": self.test_run_id},
            {"Key": PURPOSE_TAG_KEY, "Value": PURPOSE_TAG_VALUE},
            {"Key": "Name", "Value": name},
            {"Key": "ManagedBy", "Value": "aws-config-test-harness"},
        ]

    def _az(self) -> str:
        resp = self.ec2.describe_availability_zones(
            Filters=[{"Name": "state", "Values": ["available"]}]
        )
        zones = resp.get("AvailabilityZones") or []
        if not zones:
            raise RuntimeError("No available AZ in " + self.region)
        return zones[0]["ZoneName"]

    def backup_role_arn(self) -> str:
        try:
            return self.iam.get_role(RoleName="AWSBackupDefaultServiceRole")["Role"]["Arn"]
        except ClientError as exc:
            raise RuntimeError(
                "IAM role AWSBackupDefaultServiceRole is missing."
            ) from exc

    def _wait_volume(self, volume_id: str, timeout: int = 180) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = self.ec2.describe_volumes(VolumeIds=[volume_id])
            state = resp["Volumes"][0]["State"]
            if state == "available":
                return
            time.sleep(3)
        raise TimeoutError(f"Volume {volume_id} not available")

    def _create_volume(self, encrypted: bool) -> str:
        label = "enc" if encrypted else "unenc"
        name = f"cfg-rp-vol-{label}-{self.test_run_id}"
        vol = self.ec2.create_volume(
            AvailabilityZone=self._az(),
            Size=1,
            VolumeType="gp3",
            Encrypted=encrypted,
            TagSpecifications=[
                {"ResourceType": "volume", "Tags": self._tags(name)}
            ],
        )["VolumeId"]
        log(f"Created {label} volume {vol}")
        self._wait_volume(vol)
        return vol

    def ensure_vault(self) -> str:
        log(f"Creating vault {self.vault_name}")
        try:
            self.backup.create_backup_vault(
                BackupVaultName=self.vault_name,
                BackupVaultTags={
                    TEST_RUN_ID_TAG_KEY: self.test_run_id,
                    PURPOSE_TAG_KEY: PURPOSE_TAG_VALUE,
                    "ManagedBy": "aws-config-test-harness",
                },
            )
            self._vault_created = True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code != "AlreadyExistsException":
                raise
        return self.vault_name

    def start_and_wait(self, volume_id: str, timeout_seconds: int = 900) -> dict:
        resource_arn = f"arn:aws:ec2:{self.region}:{self.account}:volume/{volume_id}"
        job = self.backup.start_backup_job(
            BackupVaultName=self.vault_name,
            ResourceArn=resource_arn,
            IamRoleArn=self.backup_role_arn(),
            IdempotencyToken=f"{self.test_run_id}-{volume_id[-8:]}",
            Lifecycle={"DeleteAfterDays": 1},
        )
        job_id = job["BackupJobId"]
        deadline = time.time() + timeout_seconds
        last = {}
        while time.time() < deadline:
            last = self.backup.describe_backup_job(BackupJobId=job_id)
            state = last.get("State")
            log(f"Backup job {job_id} state={state}")
            if state == "COMPLETED":
                rp = last.get("RecoveryPointArn")
                meta = self.backup.describe_recovery_point(
                    BackupVaultName=self.vault_name,
                    RecoveryPointArn=rp,
                )
                return meta
            if state in ("FAILED", "ABORTED", "EXPIRED"):
                raise RuntimeError(f"Backup job {job_id} {state}: {last.get('StatusMessage')}")
            time.sleep(15)
        raise TimeoutError(f"Backup job {job_id} not COMPLETED")

    def provision(self) -> dict:
        self.ensure_vault()
        self.unenc_volume_id = self._create_volume(encrypted=False)
        self.enc_volume_id = self._create_volume(encrypted=True)
        nc = self.start_and_wait(self.unenc_volume_id)
        c = self.start_and_wait(self.enc_volume_id)
        self.nc_rp_arn = nc["RecoveryPointArn"]
        self.c_rp_arn = c["RecoveryPointArn"]
        return {
            "vault_name": self.vault_name,
            "unenc_volume_id": self.unenc_volume_id,
            "enc_volume_id": self.enc_volume_id,
            "nc_rp_arn": self.nc_rp_arn,
            "c_rp_arn": self.c_rp_arn,
        }

    def cleanup(self) -> None:
        for arn in (self.nc_rp_arn, self.c_rp_arn):
            if not arn:
                continue
            try:
                self.backup.delete_recovery_point(
                    BackupVaultName=self.vault_name, RecoveryPointArn=arn
                )
            except ClientError as exc:
                log(f"delete_recovery_point: {exc}", style="yellow")
        for vol in (self.unenc_volume_id, self.enc_volume_id):
            if not vol:
                continue
            try:
                self.ec2.delete_volume(VolumeId=vol)
            except ClientError as exc:
                log(f"delete_volume: {exc}", style="yellow")


class PlanProtectHarness:
    """One tagged EBS volume + backup plan/selection. No vault describe/delete."""

    def __init__(self, test_run_id: str, region: Optional[str] = None):
        self.test_run_id = test_run_id
        self.region = region or "us-east-1"
        self.backup = boto3.client("backup", region_name=self.region)
        self.ec2 = boto3.client("ec2", region_name=self.region)
        self.iam = boto3.client("iam")
        self.sts = boto3.client("sts")
        self.account = self.sts.get_caller_identity()["Account"]
        self.volume_id: Optional[str] = None
        self.plan_id: Optional[str] = None
        self.plan_arn: Optional[str] = None
        self.selection_id: Optional[str] = None
        self.vault_name = f"cfg-plan-vault-{test_run_id}"

    def _az(self) -> str:
        zones = self.ec2.describe_availability_zones(
            Filters=[{"Name": "state", "Values": ["available"]}]
        )["AvailabilityZones"]
        return zones[0]["ZoneName"]

    def _role_arn(self) -> str:
        return self.iam.get_role(RoleName="AWSBackupDefaultServiceRole")["Role"]["Arn"]

    def create_volume(self) -> str:
        name = f"cfg-plan-vol-{self.test_run_id}"
        vol = self.ec2.create_volume(
            AvailabilityZone=self._az(),
            Size=1,
            VolumeType="gp3",
            Encrypted=True,
            TagSpecifications=[{
                "ResourceType": "volume",
                "Tags": [
                    {"Key": TEST_RUN_ID_TAG_KEY, "Value": self.test_run_id},
                    {"Key": PURPOSE_TAG_KEY, "Value": PURPOSE_TAG_VALUE},
                    {"Key": "Name", "Value": name},
                    {"Key": "ManagedBy", "Value": "aws-config-test-harness"},
                ],
            }],
        )["VolumeId"]
        log(f"Created plan-protect volume {vol}")
        deadline = time.time() + 180
        while time.time() < deadline:
            state = self.ec2.describe_volumes(VolumeIds=[vol])["Volumes"][0]["State"]
            if state == "available":
                self.volume_id = vol
                return vol
            time.sleep(3)
        raise TimeoutError(f"Volume {vol} not available")

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
            if code == "AlreadyExistsException":
                return self.vault_name
            # Role can create jobs against an existing vault name even when
            # DescribeBackupVault is denied.
            self.vault_name = f"cfg-rp-vault-{self.test_run_id}"
            log(f"Falling back to vault name {self.vault_name}")
        return self.vault_name

    def protect(self) -> None:
        if not self.volume_id:
            raise RuntimeError("create_volume first")
        vault = self.ensure_vault()
        resource_arn = f"arn:aws:ec2:{self.region}:{self.account}:volume/{self.volume_id}"
        created = self.backup.create_backup_plan(
            BackupPlan={
                "BackupPlanName": f"cfg-plan-protect-{self.test_run_id}",
                "Rules": [{
                    "RuleName": "harness-daily",
                    "TargetBackupVaultName": vault,
                    "ScheduleExpression": "cron(0 5 ? * * *)",
                    "Lifecycle": {"DeleteAfterDays": 1},
                }],
            },
            BackupPlanTags={
                TEST_RUN_ID_TAG_KEY: self.test_run_id,
                PURPOSE_TAG_KEY: PURPOSE_TAG_VALUE,
            },
        )
        self.plan_id = created["BackupPlanId"]
        self.plan_arn = created["BackupPlanArn"]
        log(f"Created backup plan {self.plan_id}")
        sel = self.backup.create_backup_selection(
            BackupPlanId=self.plan_id,
            BackupSelection={
                "SelectionName": f"cfg-plan-sel-{self.test_run_id}",
                "IamRoleArn": self._role_arn(),
                "Resources": [resource_arn],
            },
        )
        self.selection_id = sel["SelectionId"]
        log(f"Created backup selection {self.selection_id} for {resource_arn}")

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
        if self.volume_id:
            try:
                self.ec2.delete_volume(VolumeId=self.volume_id)
                log(f"Deleted volume {self.volume_id}")
            except ClientError as exc:
                log(f"delete_volume: {exc}", style="yellow")
            self.volume_id = None
