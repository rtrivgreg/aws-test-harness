"""AWS Backup plan retention toggle and on-demand recovery-point harness."""

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
    """Throwaway EBS volumes + vault for BACKUP_RECOVERY_POINT_ENCRYPTED.

    EBS recovery points inherit encryption from the source volume (not the
    vault). Unencrypted volume → IsEncrypted=false → NON_COMPLIANT.
    Encrypted volume → COMPLIANT. No Terraform apply.
    """

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
        for name in ("AWSBackupDefaultServiceRole",):
            try:
                return self.iam.get_role(RoleName=name)["Role"]["Arn"]
            except ClientError:
                continue
        raise RuntimeError(
            "IAM role AWSBackupDefaultServiceRole is missing. "
            "Create the default AWS Backup service role before this test."
        )

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
        kwargs: dict = {
            "AvailabilityZone": self._az(),
            "Size": 1,
            "VolumeType": "gp3",
            "Encrypted": encrypted,
            "TagSpecifications": [
                {"ResourceType": "volume", "Tags": self._tags(name)}
            ],
        }
        vol = self.ec2.create_volume(**kwargs)["VolumeId"]
        log(f"Created {label} volume {vol}")
        self._wait_volume(vol)
        return vol

    def ensure_vault(self) -> str:
        try:
            self.backup.describe_backup_vault(BackupVaultName=self.vault_name)
            log(f"Reusing vault {self.vault_name}")
            return self.vault_name
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code not in ("ResourceNotFoundException", "AccessDeniedException"):
                # AccessDenied on missing vault is common; try create.
                if code != "ResourceNotFoundException":
                    pass
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

    def start_and_wait(
        self,
        volume_id: str,
        timeout_seconds: int = 900,
    ) -> dict:
        resource_arn = f"arn:aws:ec2:{self.region}:{self.account}:volume/{volume_id}"
        role_arn = self.backup_role_arn()
        log(f"StartBackupJob volume={volume_id} vault={self.vault_name}")
        job = self.backup.start_backup_job(
            BackupVaultName=self.vault_name,
            ResourceArn=resource_arn,
            IamRoleArn=role_arn,
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
                if not rp:
                    raise RuntimeError(f"Job {job_id} completed without RecoveryPointArn")
                meta = self.backup.describe_recovery_point(
                    BackupVaultName=self.vault_name,
                    RecoveryPointArn=rp,
                )
                log(
                    f"RP {rp} IsEncrypted={meta.get('IsEncrypted')} "
                    f"EncryptionKeyArn={meta.get('EncryptionKeyArn')}"
                )
                return meta
            if state in ("FAILED", "ABORTED", "EXPIRED"):
                raise RuntimeError(
                    f"Backup job {job_id} {state}: {last.get('StatusMessage')}"
                )
            time.sleep(15)
        raise TimeoutError(f"Backup job {job_id} not COMPLETED: {last.get('State')}")

    def provision(self) -> dict:
        self.ensure_vault()
        self.unenc_volume_id = self._create_volume(encrypted=False)
        self.enc_volume_id = self._create_volume(encrypted=True)
        nc = self.start_and_wait(self.unenc_volume_id)
        c = self.start_and_wait(self.enc_volume_id)
        self.nc_rp_arn = nc["RecoveryPointArn"]
        self.c_rp_arn = c["RecoveryPointArn"]
        if nc.get("IsEncrypted"):
            raise RuntimeError(
                f"Expected unencrypted RP from {self.unenc_volume_id}, "
                f"got IsEncrypted=True ({self.nc_rp_arn})"
            )
        if not c.get("IsEncrypted"):
            raise RuntimeError(
                f"Expected encrypted RP from {self.enc_volume_id}, "
                f"got IsEncrypted=False ({self.c_rp_arn})"
            )
        return {
            "vault_name": self.vault_name,
            "unenc_volume_id": self.unenc_volume_id,
            "enc_volume_id": self.enc_volume_id,
            "nc_rp_arn": self.nc_rp_arn,
            "c_rp_arn": self.c_rp_arn,
        }

    def _delete_rp(self, arn: Optional[str]) -> None:
        if not arn:
            return
        try:
            self.backup.delete_recovery_point(
                BackupVaultName=self.vault_name,
                RecoveryPointArn=arn,
            )
            log(f"Deleted recovery point {arn}")
        except ClientError as exc:
            log(f"delete_recovery_point {arn}: {exc}", style="yellow")

    def _delete_volume(self, volume_id: Optional[str]) -> None:
        if not volume_id:
            return
        try:
            self.ec2.delete_volume(VolumeId=volume_id)
            log(f"Deleted volume {volume_id}")
        except ClientError as exc:
            log(f"delete_volume {volume_id}: {exc}", style="yellow")

    def cleanup(self) -> None:
        self._delete_rp(self.nc_rp_arn)
        self._delete_rp(self.c_rp_arn)
        # Vault delete fails while RPs are DELETING.
        deadline = time.time() + 180
        while time.time() < deadline:
            try:
                self.backup.delete_backup_vault(BackupVaultName=self.vault_name)
                log(f"Deleted vault {self.vault_name}")
                break
            except ClientError as exc:
                log(f"delete_backup_vault: {exc}", style="yellow")
                time.sleep(10)
        self._delete_volume(self.unenc_volume_id)
        self._delete_volume(self.enc_volume_id)
