"""EBS snapshot permission toggle for public-restorable checks."""

from __future__ import annotations

import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import dry_run_guard, log


class EbsToggle:
    def __init__(self, snapshot_id: str, region: Optional[str] = None):
        self.snapshot_id = snapshot_id
        self.region = region or "us-east-1"
        self.ec2 = boto3.client("ec2", region_name=self.region)

    def is_public(self) -> bool:
        try:
            resp = self.ec2.describe_snapshot_attribute(
                SnapshotId=self.snapshot_id,
                Attribute="createVolumePermission",
            )
        except ClientError as exc:
            log(f"describe_snapshot_attribute failed: {exc}", style="yellow")
            return False
        perms = resp.get("CreateVolumePermissions") or []
        return any(p.get("Group") == "all" for p in perms)

    def wait_until_public(self, expected: bool, timeout_seconds: int = 60) -> None:
        deadline = time.time() + timeout_seconds
        attempt = 0
        while time.time() < deadline:
            attempt += 1
            actual = self.is_public()
            log(
                f"Snapshot {self.snapshot_id} public={actual} "
                f"(want {expected}, attempt={attempt})"
            )
            if actual is expected:
                return
            time.sleep(3)
        raise TimeoutError(
            f"Snapshot {self.snapshot_id} public={self.is_public()} "
            f"after {timeout_seconds}s (wanted {expected})"
        )

    @dry_run_guard("Make EBS snapshot public")
    def make_snapshot_public(self) -> None:
        log(f"Making snapshot {self.snapshot_id} publicly restorable")
        self.ec2.modify_snapshot_attribute(
            SnapshotId=self.snapshot_id,
            Attribute="createVolumePermission",
            OperationType="add",
            GroupNames=["all"],
        )
        self.wait_until_public(True)

    @dry_run_guard("Make EBS snapshot private")
    def make_snapshot_private(self) -> None:
        log(f"Removing public restore on snapshot {self.snapshot_id}")
        try:
            self.ec2.modify_snapshot_attribute(
                SnapshotId=self.snapshot_id,
                Attribute="createVolumePermission",
                OperationType="remove",
                GroupNames=["all"],
            )
        except ClientError as exc:
            log(f"modify_snapshot_attribute remove: {exc}", style="yellow")
        self.wait_until_public(False)
