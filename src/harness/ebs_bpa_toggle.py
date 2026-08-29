"""Region EBS snapshot block-public-access toggle."""

from __future__ import annotations

from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import log


class SnapshotBpaToggle:
    def __init__(self, region: Optional[str] = None):
        self.region = region or "us-east-1"
        self.ec2 = boto3.client("ec2", region_name=self.region)

    def state(self) -> str:
        resp = self.ec2.get_snapshot_block_public_access_state()
        return str(resp.get("State") or resp.get("ManagedBy") or "unknown")

    def enable_block_all(self) -> str:
        log("Enable snapshot BPA block-all-sharing")
        resp = self.ec2.enable_snapshot_block_public_access(State="block-all-sharing")
        st = str(resp.get("State"))
        log(f"BPA state={st}")
        return st

    def disable(self) -> str:
        log("Disable snapshot BPA (unblocked)")
        try:
            resp = self.ec2.disable_snapshot_block_public_access()
            st = str(resp.get("State") or "unblocked")
        except ClientError as exc:
            log(f"disable_snapshot_block_public_access: {exc}", style="yellow")
            raise
        log(f"BPA state={st}")
        return st
