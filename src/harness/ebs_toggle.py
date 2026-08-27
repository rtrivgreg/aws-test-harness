"""EBS snapshot permission toggle for public-restorable checks."""

from __future__ import annotations

from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import dry_run_guard, log


class EbsToggle:
    def __init__(self, snapshot_id: str, region: Optional[str] = None):
        self.snapshot_id = snapshot_id
        self.region = region or "us-east-1"
        self.ec2 = boto3.client("ec2", region_name=self.region)

    @dry_run_guard("Make EBS snapshot public")
    def make_snapshot_public(self) -> None:
        log(f"Making snapshot {self.snapshot_id} publicly restorable")
        self.ec2.modify_snapshot_attribute(
            SnapshotId=self.snapshot_id,
            Attribute="createVolumePermission",
            OperationType="add",
            GroupNames=["all"],
        )

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
