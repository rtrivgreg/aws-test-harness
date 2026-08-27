"""Toggle EFS automatic backups (PutBackupPolicy)."""

from __future__ import annotations

import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import dry_run_guard, log


class EfsToggle:
    def __init__(self, file_system_id: str, region: Optional[str] = None):
        self.file_system_id = file_system_id
        self.region = region or "us-east-1"
        self.efs = boto3.client("efs", region_name=self.region)

    def backup_status(self) -> str:
        try:
            resp = self.efs.describe_backup_policy(FileSystemId=self.file_system_id)
            return (resp.get("BackupPolicy") or {}).get("Status", "UNKNOWN")
        except ClientError as exc:
            log(f"describe_backup_policy: {exc}", style="yellow")
            return "UNKNOWN"

    def wait_for_status(self, wanted: str, timeout_seconds: int = 60) -> None:
        deadline = time.time() + timeout_seconds
        attempt = 0
        wanted_set = {wanted, wanted.replace("ED", "ING")} if wanted in (
            "ENABLED",
            "DISABLED",
        ) else {wanted}
        # ENABLED accepts ENABLING until it settles; we wait for exact terminal.
        while time.time() < deadline:
            attempt += 1
            actual = self.backup_status()
            log(
                f"EFS {self.file_system_id} backup={actual} "
                f"(want {wanted}, attempt={attempt})"
            )
            if actual == wanted:
                return
            time.sleep(3)
        raise TimeoutError(
            f"EFS {self.file_system_id} backup={self.backup_status()} "
            f"wanted {wanted}"
        )

    @dry_run_guard("Set EFS backup policy")
    def set_automatic_backups(self, enabled: bool) -> None:
        status = "ENABLED" if enabled else "DISABLED"
        log(f"Setting automatic backups {status} on {self.file_system_id}")
        self.efs.put_backup_policy(
            FileSystemId=self.file_system_id,
            BackupPolicy={"Status": status},
        )
        self.wait_for_status(status)
